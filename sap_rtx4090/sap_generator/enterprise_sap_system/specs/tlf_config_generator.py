#!/usr/bin/env python3
"""
Config-Driven TLF Shell Generator
=================================
Reads YAML configuration files and generates TLF shell specifications.

Usage:
    python tlf_config_generator.py --config ct_p16/priority_1_efficacy.yaml --output shells_efficacy.md
    python tlf_config_generator.py --study ct_p16 --priority 1 --output priority_1_shells.md
    python tlf_config_generator.py --study ct_p16 --all --output all_shells.md
"""

import yaml
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


class TLFConfigGenerator:
    """
    Generates TLF shell specifications from YAML configuration files.
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize the generator with config directory path."""
        if config_dir is None:
            config_dir = Path(__file__).parent / "tlf_configs"
        self.config_dir = Path(config_dir)

    def load_yaml(self, filepath: Path) -> Dict:
        """Load a YAML configuration file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def load_study_configs(self, study: str, priority: Optional[int] = None) -> List[Dict]:
        """Load all configuration files for a study, optionally filtered by priority."""
        study_dir = self.config_dir / study
        configs = []

        if not study_dir.exists():
            raise FileNotFoundError(f"Study directory not found: {study_dir}")

        for yaml_file in study_dir.glob("*.yaml"):
            config = self.load_yaml(yaml_file)
            if priority is None or config.get('metadata', {}).get('priority') == priority:
                config['_source_file'] = yaml_file.name
                configs.append(config)

        return configs

    def generate_table_markdown(self, table: Dict) -> str:
        """Generate markdown specification for a single table."""
        lines = []

        # Title
        lines.append(f"### Table {table['number']}: {table['title']}")
        lines.append("")

        # Metadata
        lines.append(f"**Population:** {table['population']}")
        lines.append(f"**Orientation:** {table['orientation']}")
        lines.append(f"**Source Dataset:** {table['source_dataset']}")
        lines.append("")

        # Filter condition
        if table.get('filter_condition'):
            lines.append(f"**Filter:** `{table['filter_condition']}`")
            lines.append("")

        # Column specifications
        lines.append("#### Column Specifications")
        lines.append("")
        lines.append("| Column Header | Width (in) | Align | Format |")
        lines.append("|---------------|------------|-------|--------|")
        for col in table.get('columns', []):
            header = col.get('header', '').replace('\n', ' / ')
            width = col.get('width', '-')
            align = col.get('alignment', '-')
            fmt = col.get('format', '-') or '-'
            lines.append(f"| {header} | {width} | {align} | {fmt} |")
        lines.append("")

        # Row structure (stub)
        if table.get('stub_rows'):
            lines.append("#### Row Structure (Stub)")
            lines.append("")
            for row in table['stub_rows'][:25]:  # Limit display
                level = row.get('level', 0)
                indent = "  " * level
                label = row.get('label', '')
                bold = row.get('bold', False)
                row_type = row.get('row_type', 'data')

                if label:  # Skip spacers
                    if bold:
                        lines.append(f"- {indent}**{label}** [{row_type}]")
                    else:
                        lines.append(f"- {indent}{label} [{row_type}]")
            if len(table['stub_rows']) > 25:
                lines.append(f"- ... ({len(table['stub_rows']) - 25} more rows)")
            lines.append("")

        # Sort order
        if table.get('sort_order'):
            lines.append(f"**Sort Order:** {' > '.join(table['sort_order'])}")
            lines.append("")

        # Footnotes
        if table.get('footnotes'):
            lines.append("#### Footnotes")
            lines.append("")
            for fn in table['footnotes']:
                symbol = fn.get('symbol', '')
                text = fn.get('text', '')
                if symbol:
                    lines.append(f"- {symbol}. {text}")
                else:
                    lines.append(f"- {text}")
            lines.append("")

        # Programming notes
        if table.get('programming_notes'):
            lines.append("#### Programming Notes")
            lines.append("")
            for note in table['programming_notes']:
                lines.append(f"- {note}")
            lines.append("")

        lines.append("---")
        lines.append("")

        return "\n".join(lines)

    def generate_config_markdown(self, config: Dict) -> str:
        """Generate markdown for an entire configuration file."""
        lines = []

        # Metadata header
        metadata = config.get('metadata', {})
        lines.append(f"## {metadata.get('category', 'TLF')} Shells - {metadata.get('study', 'Unknown Study')}")
        lines.append("")
        lines.append(f"**Priority:** {metadata.get('priority', 'N/A')}")
        lines.append(f"**SAP Sections:** {', '.join(metadata.get('sap_sections', []))}")
        if config.get('_source_file'):
            lines.append(f"**Source:** `{config['_source_file']}`")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Generate each table
        for table in config.get('tables', []):
            lines.append(self.generate_table_markdown(table))

        return "\n".join(lines)

    def generate_study_document(
        self,
        study: str,
        priority: Optional[int] = None,
        output_path: Optional[Path] = None
    ) -> str:
        """Generate complete markdown document for a study."""
        configs = self.load_study_configs(study, priority)

        lines = []

        # Document header
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

        # Table index
        lines.append("## Table Index")
        lines.append("")
        for config in configs:
            category = config.get('metadata', {}).get('category', 'Unknown')
            lines.append(f"### {category}")
            lines.append("")
            for table in config.get('tables', []):
                lines.append(f"- **{table['number']}**: {table['title']}")
            lines.append("")
        lines.append("---")
        lines.append("")

        # Full specifications
        lines.append("## Detailed Specifications")
        lines.append("")
        for config in configs:
            lines.append(self.generate_config_markdown(config))

        document = "\n".join(lines)

        # Write to file if output path provided
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(document)
            print(f"Generated: {output_path}")

        return document

    def generate_mock_table(self, table: Dict) -> str:
        """Generate ASCII mock-up of a table."""
        columns = table.get('columns', [])
        rows = table.get('stub_rows', [])

        if not columns:
            return ""

        # Calculate column widths (use width in inches * 10 as character approximation)
        col_widths = [max(10, int(c.get('width', 1.5) * 8)) for c in columns]
        total_width = sum(col_widths) + len(col_widths) + 1

        lines = []
        sep = "+" + "+".join(["-" * w for w in col_widths]) + "+"

        lines.append(sep)

        # Header row
        header_parts = []
        for i, col in enumerate(columns):
            header = col.get('header', '').replace('\n', ' ').replace('\\n', ' ')[:col_widths[i]-2]
            header_parts.append(f" {header:<{col_widths[i]-2}} ")
        lines.append("|" + "|".join(header_parts) + "|")
        lines.append(sep)

        # Data rows (sample)
        for row in rows[:10]:
            if row.get('row_type') == 'spacer':
                continue
            label = row.get('label', '')
            indent = "  " * row.get('level', 0)
            label = indent + label
            label = label[:col_widths[0]-2]

            row_parts = [f" {label:<{col_widths[0]-2}} "]
            for i, w in enumerate(col_widths[1:], 1):
                row_parts.append(f" {'xxx (xx.x)':^{w-2}} ")
            lines.append("|" + "|".join(row_parts) + "|")

        lines.append(sep)

        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='Generate TLF shell specifications from YAML configs')
    parser.add_argument('--config', type=str, help='Single config file to process (relative to tlf_configs/)')
    parser.add_argument('--study', type=str, help='Study name (e.g., ct_p16)')
    parser.add_argument('--priority', type=int, help='Filter by priority level')
    parser.add_argument('--all', action='store_true', help='Process all configs for study')
    parser.add_argument('--output', type=str, help='Output file path')
    parser.add_argument('--list', action='store_true', help='List available configs')

    args = parser.parse_args()

    generator = TLFConfigGenerator()

    if args.list:
        print("Available configurations:")
        for study_dir in generator.config_dir.iterdir():
            if study_dir.is_dir() and not study_dir.name.startswith('.'):
                print(f"\n  {study_dir.name}/")
                for yaml_file in study_dir.glob("*.yaml"):
                    print(f"    - {yaml_file.name}")
        return

    if args.config:
        config_path = generator.config_dir / args.config
        config = generator.load_yaml(config_path)
        config['_source_file'] = args.config
        document = generator.generate_config_markdown(config)
    elif args.study:
        priority = args.priority if not args.all else None
        output_path = Path(args.output) if args.output else None
        document = generator.generate_study_document(args.study, priority, output_path)
    else:
        parser.print_help()
        return

    if not args.output:
        print(document)


if __name__ == "__main__":
    main()
