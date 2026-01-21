#!/usr/bin/env python3
"""
TLF Configuration Generator v2.0
================================
Enhanced generator for oncology TLF shell specifications.

Features:
- Modular configuration system (core + study type + AESI + design)
- Automatic template expansion
- Multi-study support
- Interactive study setup wizard
- Markdown and JSON output

Usage:
    # Generate shells for existing study
    python tlf_config_generator_v2.py --study ct_p16 --output shells.md

    # Create new study from templates
    python tlf_config_generator_v2.py --new-study MY_STUDY --wizard

    # List available templates
    python tlf_config_generator_v2.py --list-templates
"""

import yaml
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from copy import deepcopy
import re


@dataclass
class StudyConfig:
    """Study configuration parameters."""
    study_id: str
    study_type: str  # biosimilar, immuno_oncology, targeted_therapy, chemotherapy
    indication: str
    drug_class: List[str]  # References to AESI library
    study_design: str  # induction_maintenance, continuous, adjuvant, etc.
    treatment_arms: Dict[str, str]
    design_parameters: Dict[str, Any] = field(default_factory=dict)
    review_types: List[str] = field(default_factory=list)  # central, local
    populations: List[str] = field(default_factory=list)
    biomarkers: List[str] = field(default_factory=list)


class TLFConfigGeneratorV2:
    """Enhanced TLF Configuration Generator with modular templates."""

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize generator with configuration directory."""
        self.config_dir = config_dir or Path(__file__).parent / "tlf_configs"
        self.core_dir = self.config_dir / "core"

        # Cache for loaded configs
        self._cache: Dict[str, Dict] = {}

    def load_yaml(self, filepath: Path) -> Dict:
        """Load and cache YAML configuration."""
        key = str(filepath)
        if key not in self._cache:
            with open(filepath, 'r', encoding='utf-8') as f:
                self._cache[key] = yaml.safe_load(f)
        return deepcopy(self._cache[key])

    # =========================================================================
    # TEMPLATE LOADING
    # =========================================================================

    def load_core_base(self) -> Dict:
        """Load core oncology base configuration."""
        return self.load_yaml(self.core_dir / "base_oncology.yaml")

    def load_aesi_library(self) -> Dict:
        """Load AESI library."""
        return self.load_yaml(self.core_dir / "aesi_library.yaml")

    def load_study_designs(self) -> Dict:
        """Load study design templates."""
        return self.load_yaml(self.core_dir / "study_designs.yaml")

    def load_study_type_base(self, study_type: str) -> Dict:
        """Load study-type specific base configuration."""
        type_map = {
            'biosimilar': 'base_biosimilar.yaml',
            'immuno_oncology': 'base_immuno_oncology.yaml',
            'targeted_therapy': 'base_targeted_therapy.yaml',
        }
        if study_type not in type_map:
            raise ValueError(f"Unknown study type: {study_type}. Available: {list(type_map.keys())}")
        return self.load_yaml(self.core_dir / type_map[study_type])

    def get_aesi_for_drug_class(self, drug_classes: List[str]) -> List[Dict]:
        """Get combined AESI categories for specified drug classes."""
        library = self.load_aesi_library()
        aesi_categories = []

        for drug_class in drug_classes:
            if drug_class in library:
                class_info = library[drug_class]
                if 'aesi_categories' in class_info:
                    aesi_categories.extend(class_info['aesi_categories'])

        return aesi_categories

    def get_study_design(self, design_name: str) -> Dict:
        """Get specific study design template."""
        designs = self.load_study_designs()
        if design_name not in designs:
            raise ValueError(f"Unknown study design: {design_name}. Available: {list(designs.keys())}")
        return designs[design_name]

    # =========================================================================
    # STUDY CONFIGURATION
    # =========================================================================

    def load_study_configs(self, study: str, priority: Optional[int] = None) -> List[Dict]:
        """Load all configuration files for a study."""
        study_dir = self.config_dir / study.lower()
        if not study_dir.exists():
            raise ValueError(f"Study directory not found: {study_dir}")

        configs = []
        pattern = f"priority_{priority}_*.yaml" if priority else "priority_*.yaml"

        for config_file in sorted(study_dir.glob(pattern)):
            config = self.load_yaml(config_file)
            config['_source_file'] = config_file.name
            configs.append(config)

        return configs

    def list_available_studies(self) -> List[str]:
        """List all available studies."""
        studies = []
        for d in self.config_dir.iterdir():
            if d.is_dir() and d.name != 'core' and not d.name.startswith('.'):
                studies.append(d.name)
        return sorted(studies)

    def list_available_templates(self) -> Dict[str, List[str]]:
        """List all available templates."""
        return {
            'study_types': ['biosimilar', 'immuno_oncology', 'targeted_therapy'],
            'drug_classes': list(self.load_aesi_library().keys()),
            'study_designs': list(self.load_study_designs().keys()),
        }

    # =========================================================================
    # TEMPLATE EXPANSION
    # =========================================================================

    def expand_template(self, template: str, variables: Dict[str, str]) -> str:
        """Expand template variables like {ARM1}, {BIOSIMILAR}, etc."""
        result = template
        for key, value in variables.items():
            result = result.replace(f"{{{key}}}", value)
        return result

    def expand_config(self, config: Dict, variables: Dict[str, str]) -> Dict:
        """Recursively expand all template variables in a config."""
        if isinstance(config, str):
            return self.expand_template(config, variables)
        elif isinstance(config, list):
            return [self.expand_config(item, variables) for item in config]
        elif isinstance(config, dict):
            return {k: self.expand_config(v, variables) for k, v in config.items()}
        return config

    # =========================================================================
    # SHELL GENERATION
    # =========================================================================

    def generate_aesi_table(self, study_config: StudyConfig, period: str = "Whole") -> Dict:
        """Generate AESI table shell based on drug class."""
        aesi_categories = self.get_aesi_for_drug_class(study_config.drug_class)

        stub_rows = [
            {"level": 0, "label": "Subjects with Any AESI", "bold": True, "row_type": "total"},
            {"level": 0, "label": "", "bold": False, "row_type": "spacer"},
        ]

        for category in aesi_categories:
            stub_rows.append({
                "level": 0,
                "label": category['category'],
                "bold": True,
                "row_type": "header"
            })
            if 'preferred_terms' in category:
                for pt in category['preferred_terms'][:5]:  # Limit to top 5
                    stub_rows.append({
                        "level": 1,
                        "label": pt,
                        "bold": False,
                        "row_type": "data"
                    })
            stub_rows.append({"level": 0, "label": "", "bold": False, "row_type": "spacer"})

        # Get arm names
        arm1 = list(study_config.treatment_arms.values())[0]
        arm2 = list(study_config.treatment_arms.values())[1] if len(study_config.treatment_arms) > 1 else "Control"

        table = {
            "number": "14.3.2.x",
            "title": f"Adverse Events of Special Interest - {period} Study Period (Safety Population)",
            "tlf_type": "TABLE",
            "population": "Safety Population",
            "study_period": period,
            "orientation": "PORTRAIT",
            "columns": [
                {"header": "AESI Category / Preferred Term", "width": 4.0, "alignment": "L"},
                {"header": f"{arm1}\n(N=xxx)\nn (%)", "width": 1.3, "alignment": "C", "format": "xxx (xx.x)"},
                {"header": f"{arm2}\n(N=xxx)\nn (%)", "width": 1.3, "alignment": "C", "format": "xxx (xx.x)"},
                {"header": "Total\n(N=xxx)\nn (%)", "width": 1.3, "alignment": "C", "format": "xxx (xx.x)"},
            ],
            "stub_rows": stub_rows,
            "footnotes": [
                {"symbol": "", "text": "Safety Population."},
                {"symbol": "a", "text": f"AESI defined based on {', '.join(study_config.drug_class)} drug class."},
                {"symbol": "b", "text": "A subject is counted once per category and once per preferred term."},
            ],
            "source_dataset": "ADAE",
            "filter_condition": f"SAFFL = 'Y' and AESSION = '{period.upper()}'",
            "programming_notes": [
                f"AESI categories for: {', '.join(study_config.drug_class)}",
                "Query SMQs or custom AESI definitions",
            ]
        }

        return table

    def generate_response_table(self, study_config: StudyConfig,
                                population: str = "ITT",
                                review_type: str = "Central") -> Dict:
        """Generate response rate table shell."""
        arm1 = list(study_config.treatment_arms.values())[0]
        arm2 = list(study_config.treatment_arms.values())[1] if len(study_config.treatment_arms) > 1 else "Control"

        # Get response criteria from core
        core = self.load_core_base()
        recist = core['response_criteria']['recist_1_1']

        stub_rows = [
            {"level": 0, "label": "Evaluable Subjects", "bold": True, "row_type": "data"},
            {"level": 0, "label": "", "bold": False, "row_type": "spacer"},
            {"level": 0, "label": "Best Overall Response", "bold": True, "row_type": "header"},
        ]

        for cat in recist['categories']:
            stub_rows.append({
                "level": 1,
                "label": f"{cat['label']} ({cat['code']})",
                "bold": False,
                "row_type": "data"
            })

        stub_rows.extend([
            {"level": 0, "label": "", "bold": False, "row_type": "spacer"},
            {"level": 0, "label": "Objective Response Rate (CR+PR)", "bold": True, "row_type": "data"},
            {"level": 1, "label": "n (%)", "bold": False, "row_type": "data"},
            {"level": 1, "label": "95% CI", "bold": False, "row_type": "data"},
        ])

        # Add comparison statistics based on study type
        if study_config.study_type == 'biosimilar':
            stub_rows.extend([
                {"level": 0, "label": "", "bold": False, "row_type": "spacer"},
                {"level": 0, "label": "Treatment Comparison", "bold": True, "row_type": "header"},
                {"level": 1, "label": "Risk Ratio [90% CI]", "bold": False, "row_type": "data"},
                {"level": 1, "label": "Risk Difference [90% CI]", "bold": False, "row_type": "data"},
            ])
        else:
            stub_rows.extend([
                {"level": 0, "label": "", "bold": False, "row_type": "spacer"},
                {"level": 0, "label": "Treatment Comparison", "bold": True, "row_type": "header"},
                {"level": 1, "label": "Odds Ratio [95% CI]", "bold": False, "row_type": "data"},
                {"level": 1, "label": "P-value", "bold": False, "row_type": "data"},
            ])

        footnotes = [
            {"symbol": "", "text": f"{population} Population."},
            {"symbol": "a", "text": f"Response assessed per RECIST 1.1 by {review_type} Review."},
            {"symbol": "b", "text": "95% CI calculated using Clopper-Pearson exact method."},
        ]

        if study_config.study_type == 'biosimilar':
            footnotes.append({
                "symbol": "c",
                "text": "Similarity criterion: 90% CI for risk ratio within [0.75, 1.33]."
            })

        table = {
            "number": f"14.2.1.x",
            "title": f"Best Overall Response ({population} Population, {review_type} Review)",
            "tlf_type": "TABLE",
            "population": f"{population} Population",
            "review_type": review_type,
            "orientation": "PORTRAIT",
            "columns": [
                {"header": "Response Category", "width": 3.0, "alignment": "L"},
                {"header": f"{arm1}\n(N=xxx)\nn (%)", "width": 1.3, "alignment": "C", "format": "xxx (xx.x)"},
                {"header": f"{arm2}\n(N=xxx)\nn (%)", "width": 1.3, "alignment": "C", "format": "xxx (xx.x)"},
            ],
            "stub_rows": stub_rows,
            "footnotes": footnotes,
            "source_dataset": "ADRS",
            "filter_condition": f"{population}FL = 'Y' and PARAMCD = 'BOR' and REVIEW = '{review_type.upper()}'",
        }

        return table

    def generate_tte_table(self, study_config: StudyConfig,
                           endpoint: str = "PFS",
                           population: str = "ITT",
                           review_type: Optional[str] = None) -> Dict:
        """Generate time-to-event table shell."""
        core = self.load_core_base()
        tte_def = core['time_to_event_endpoints'].get(endpoint.lower(), {})

        arm1 = list(study_config.treatment_arms.values())[0]
        arm2 = list(study_config.treatment_arms.values())[1] if len(study_config.treatment_arms) > 1 else "Control"

        stub_rows = [
            {"level": 0, "label": "Number of Events, n (%)", "bold": True, "row_type": "data"},
            {"level": 0, "label": "Number Censored, n (%)", "bold": False, "row_type": "data"},
            {"level": 0, "label": "", "bold": False, "row_type": "spacer"},
            {"level": 0, "label": "Kaplan-Meier Estimates", "bold": True, "row_type": "header"},
            {"level": 1, "label": "25th Percentile (months) [95% CI]", "bold": False, "row_type": "data"},
            {"level": 1, "label": "Median (months) [95% CI]", "bold": False, "row_type": "data"},
            {"level": 1, "label": "75th Percentile (months) [95% CI]", "bold": False, "row_type": "data"},
            {"level": 0, "label": "", "bold": False, "row_type": "spacer"},
            {"level": 0, "label": "Event-Free Rate [95% CI]", "bold": True, "row_type": "header"},
            {"level": 1, "label": "At 6 Months", "bold": False, "row_type": "data"},
            {"level": 1, "label": "At 12 Months", "bold": False, "row_type": "data"},
            {"level": 1, "label": "At 24 Months", "bold": False, "row_type": "data"},
            {"level": 0, "label": "", "bold": False, "row_type": "spacer"},
            {"level": 0, "label": "Treatment Comparison", "bold": True, "row_type": "header"},
            {"level": 1, "label": "Hazard Ratio [95% CI]", "bold": False, "row_type": "data"},
            {"level": 1, "label": "P-value (Log-rank)", "bold": False, "row_type": "data"},
        ]

        title = f"Summary of {tte_def.get('label', endpoint)} ({population} Population"
        if review_type:
            title += f", {review_type} Review"
        title += ")"

        table = {
            "number": f"14.2.x.x",
            "title": title,
            "tlf_type": "TABLE",
            "population": f"{population} Population",
            "review_type": review_type,
            "orientation": "PORTRAIT",
            "columns": [
                {"header": "Parameter", "width": 3.0, "alignment": "L"},
                {"header": f"{arm1}\n(N=xxx)", "width": 1.8, "alignment": "C"},
                {"header": f"{arm2}\n(N=xxx)", "width": 1.8, "alignment": "C"},
            ],
            "stub_rows": stub_rows,
            "footnotes": [
                {"symbol": "", "text": f"{population} Population."},
                {"symbol": "a", "text": tte_def.get('definition', f"{endpoint} definition per protocol.")},
                {"symbol": "b", "text": "Kaplan-Meier estimates; 95% CI by Brookmeyer-Crowley method."},
                {"symbol": "c", "text": "HR from Cox proportional hazards model; HR < 1 favors " + arm1 + "."},
            ],
            "source_dataset": "ADTTE",
            "filter_condition": f"{population}FL = 'Y' and PARAMCD = '{endpoint}'",
        }

        return table

    # =========================================================================
    # STUDY WIZARD
    # =========================================================================

    def create_study_wizard(self) -> StudyConfig:
        """Interactive wizard to create new study configuration."""
        print("\n" + "="*60)
        print("TLF Shell Configuration Wizard")
        print("="*60)

        # Study ID
        study_id = input("\nEnter Study ID (e.g., CT-P16, KEYNOTE-123): ").strip()

        # Study Type
        print("\nSelect Study Type:")
        print("  1. Biosimilar")
        print("  2. Immuno-Oncology (Checkpoint Inhibitor)")
        print("  3. Targeted Therapy (TKI, etc.)")
        choice = input("Enter choice (1-3): ").strip()
        study_type_map = {'1': 'biosimilar', '2': 'immuno_oncology', '3': 'targeted_therapy'}
        study_type = study_type_map.get(choice, 'biosimilar')

        # Indication
        indication = input("\nEnter Indication (e.g., NSCLC, Breast Cancer): ").strip()

        # Drug Class (for AESI)
        print("\nSelect Drug Class(es) for AESI (comma-separated numbers):")
        aesi_lib = self.load_aesi_library()
        classes = list(aesi_lib.keys())
        for i, cls in enumerate(classes, 1):
            print(f"  {i}. {cls}")
        choices = input("Enter choices: ").strip().split(',')
        drug_class = [classes[int(c.strip())-1] for c in choices if c.strip().isdigit()]

        # Study Design
        print("\nSelect Study Design:")
        designs = self.load_study_designs()
        design_names = list(designs.keys())
        for i, name in enumerate(design_names, 1):
            desc = designs[name].get('description', '')[:50]
            print(f"  {i}. {name}: {desc}")
        choice = input("Enter choice: ").strip()
        study_design = design_names[int(choice)-1] if choice.isdigit() else 'continuous'

        # Treatment Arms
        print("\nEnter Treatment Arms:")
        arm1_name = input("  Arm 1 name (e.g., CT-P16, Pembrolizumab): ").strip()
        arm2_name = input("  Arm 2 name (e.g., EU-Avastin, Placebo, Chemo): ").strip()
        treatment_arms = {'arm1': arm1_name, 'arm2': arm2_name}

        # Review Types (for biosimilar)
        review_types = []
        if study_type == 'biosimilar':
            review_types = ['central', 'local']
        else:
            use_central = input("\nUse Central Review? (y/n): ").strip().lower() == 'y'
            review_types = ['central', 'local'] if use_central else ['local']

        # Populations
        populations = ['ITT', 'Safety']
        if study_type == 'biosimilar':
            populations.append('PP')

        config = StudyConfig(
            study_id=study_id,
            study_type=study_type,
            indication=indication,
            drug_class=drug_class,
            study_design=study_design,
            treatment_arms=treatment_arms,
            review_types=review_types,
            populations=populations,
        )

        print("\n" + "="*60)
        print("Configuration Summary:")
        print(f"  Study ID: {config.study_id}")
        print(f"  Type: {config.study_type}")
        print(f"  Indication: {config.indication}")
        print(f"  Drug Class: {config.drug_class}")
        print(f"  Design: {config.study_design}")
        print(f"  Arms: {config.treatment_arms}")
        print("="*60)

        return config

    # =========================================================================
    # OUTPUT GENERATION
    # =========================================================================

    def generate_table_markdown(self, table: Dict) -> str:
        """Generate markdown for a single table shell."""
        lines = []

        # Title
        number = table.get('number', 'X.X.X')
        title = table.get('title', 'Untitled')
        lines.append(f"### Table {number}: {title}")
        lines.append("")

        # Metadata
        lines.append(f"**Population:** {table.get('population', 'N/A')}")
        if table.get('study_period'):
            lines.append(f"**Study Period:** {table.get('study_period')}")
        if table.get('review_type'):
            lines.append(f"**Review Type:** {table.get('review_type')}")
        lines.append(f"**Orientation:** {table.get('orientation', 'PORTRAIT')}")
        lines.append(f"**Source Dataset:** {table.get('source_dataset', 'N/A')}")
        lines.append("")

        # Filter
        if table.get('filter_condition'):
            lines.append(f"**Filter:** `{table['filter_condition']}`")
            lines.append("")

        # Column Specifications
        if table.get('columns'):
            lines.append("#### Column Specifications")
            lines.append("")
            lines.append("| Column Header | Width (in) | Align | Format |")
            lines.append("|---------------|------------|-------|--------|")
            for col in table['columns']:
                header = col.get('header', '').replace('\n', ' / ')
                width = col.get('width', '-')
                align = col.get('alignment', '-')
                fmt = col.get('format', '-') or '-'
                lines.append(f"| {header} | {width} | {align} | {fmt} |")
            lines.append("")

        # Row Structure
        if table.get('stub_rows'):
            lines.append("#### Row Structure (Stub)")
            lines.append("")
            for row in table['stub_rows']:
                level = row.get('level', 0)
                label = row.get('label', '')
                row_type = row.get('row_type', 'data')
                if label or row_type == 'spacer':
                    indent = "  " * level
                    suffix = f" [{row_type}]" if row_type != 'data' else ""
                    if row_type == 'spacer':
                        lines.append(f"- *(spacer)*")
                    else:
                        bold = "**" if row.get('bold') else ""
                        lines.append(f"- {indent}{bold}{label}{bold}{suffix}")
            lines.append("")

        # Footnotes
        if table.get('footnotes'):
            lines.append("#### Footnotes")
            lines.append("")
            for fn in table['footnotes']:
                symbol = fn.get('symbol', '')
                text = fn.get('text', '')
                if symbol:
                    lines.append(f"- <sup>{symbol}</sup> {text}")
                else:
                    lines.append(f"- {text}")
            lines.append("")

        # Programming Notes
        if table.get('programming_notes'):
            lines.append("#### Programming Notes")
            lines.append("")
            for note in table['programming_notes']:
                lines.append(f"- {note}")
            lines.append("")

        lines.append("---")
        lines.append("")

        return '\n'.join(lines)

    def generate_study_document(self, study: str, priority: Optional[int] = None,
                                output_path: Optional[Path] = None) -> str:
        """Generate complete markdown document for a study."""
        configs = self.load_study_configs(study, priority)

        lines = []
        lines.append("# TLF Shell Specifications")
        lines.append("")
        lines.append(f"**Study:** {study.upper()}")
        if priority:
            lines.append(f"**Priority:** {priority}")
        lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # Summary
        total_tables = sum(len(c.get('tables', [])) for c in configs)
        lines.append("## Summary")
        lines.append("")
        lines.append(f"**Total Tables:** {total_tables}")
        lines.append("")
        lines.append("| Category | Tables | Source File |")
        lines.append("|----------|--------|-------------|")
        for config in configs:
            category = config.get('metadata', {}).get('category', 'Unknown')
            count = len(config.get('tables', []))
            source = config.get('_source_file', 'unknown')
            lines.append(f"| {category} | {count} | `{source}` |")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Table Index
        lines.append("## Table Index")
        lines.append("")
        for config in configs:
            category = config.get('metadata', {}).get('category', 'Unknown')
            lines.append(f"### {category}")
            lines.append("")
            for table in config.get('tables', []):
                number = table.get('number', 'X.X.X')
                title = table.get('title', 'Untitled')
                lines.append(f"- **{number}**: {title}")
            lines.append("")
        lines.append("---")
        lines.append("")

        # Detailed Specifications
        lines.append("## Detailed Specifications")
        lines.append("")
        for config in configs:
            metadata = config.get('metadata', {})
            category = metadata.get('category', 'Unknown')
            lines.append(f"## {category} Shells - {study.upper()}")
            lines.append("")
            lines.append(f"**Priority:** {metadata.get('priority', 'N/A')}")
            lines.append(f"**SAP Sections:** {metadata.get('sap_sections', [])}")
            lines.append(f"**Source:** `{config.get('_source_file', 'unknown')}`")
            lines.append("")
            lines.append("---")
            lines.append("")

            for table in config.get('tables', []):
                lines.append(self.generate_table_markdown(table))

        content = '\n'.join(lines)

        if output_path:
            output_path = Path(output_path)
            output_path.write_text(content, encoding='utf-8')
            print(f"Generated: {output_path}")

        return content

    def generate_from_study_config(self, config: StudyConfig,
                                   output_path: Optional[Path] = None) -> str:
        """Generate shells directly from a StudyConfig object."""
        lines = []
        lines.append("# TLF Shell Specifications")
        lines.append("")
        lines.append(f"**Study:** {config.study_id}")
        lines.append(f"**Type:** {config.study_type}")
        lines.append(f"**Indication:** {config.indication}")
        lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        tables = []

        # Generate efficacy tables
        for pop in config.populations:
            if pop in ['ITT', 'PP']:
                for review in config.review_types:
                    # Response table
                    tables.append(self.generate_response_table(config, pop, review.title()))
                    # PFS table
                    tables.append(self.generate_tte_table(config, "PFS", pop, review.title()))

        # Generate OS (no review type)
        tables.append(self.generate_tte_table(config, "OS", "ITT"))

        # Generate safety tables
        design = self.get_study_design(config.study_design)
        periods = list(design.get('periods', {}).keys())
        for period in periods[:4]:  # Limit to 4 periods
            tables.append(self.generate_aesi_table(config, period.title()))

        # Output summary
        lines.append("## Summary")
        lines.append("")
        lines.append(f"**Total Tables:** {len(tables)}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Output tables
        lines.append("## Detailed Specifications")
        lines.append("")
        for table in tables:
            lines.append(self.generate_table_markdown(table))

        content = '\n'.join(lines)

        if output_path:
            output_path = Path(output_path)
            output_path.write_text(content, encoding='utf-8')
            print(f"Generated: {output_path}")

        return content


def main():
    parser = argparse.ArgumentParser(description='TLF Configuration Generator v2.0')
    parser.add_argument('--study', help='Study ID to generate shells for')
    parser.add_argument('--priority', type=int, help='Priority level (1, 2, 3)')
    parser.add_argument('--output', help='Output file path')
    parser.add_argument('--list-templates', action='store_true', help='List available templates')
    parser.add_argument('--list-studies', action='store_true', help='List available studies')
    parser.add_argument('--wizard', action='store_true', help='Run interactive study wizard')
    parser.add_argument('--new-study', help='Create new study from wizard')

    args = parser.parse_args()

    generator = TLFConfigGeneratorV2()

    if args.list_templates:
        templates = generator.list_available_templates()
        print("\nAvailable Templates:")
        for category, items in templates.items():
            print(f"\n{category}:")
            for item in items:
                print(f"  - {item}")
        return

    if args.list_studies:
        studies = generator.list_available_studies()
        print("\nAvailable Studies:")
        for study in studies:
            print(f"  - {study}")
        return

    if args.wizard or args.new_study:
        config = generator.create_study_wizard()
        output_path = Path(args.output) if args.output else Path(f"{config.study_id.lower()}_shells.md")
        generator.generate_from_study_config(config, output_path)
        return

    if args.study:
        output_path = Path(args.output) if args.output else None
        generator.generate_study_document(args.study, args.priority, output_path)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
