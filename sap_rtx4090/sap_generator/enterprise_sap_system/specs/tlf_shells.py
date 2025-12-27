#!/usr/bin/env python3
"""
Enterprise SAP Generation System - TLF Shell Generator
========================================================
PRODUCTION-LEVEL TLF (Tables, Listings, Figures) shell specifications.

Generates detailed, programmer-ready TLF specifications including:
- Column specifications with widths
- Row headers and stub hierarchies
- Statistical footnotes
- Population specifications
- Sort orders
- Programming notes

These are real specifications that programmers can implement directly.
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

try:
    from ..core.schemas import ParsedProtocol, EndpointType, Estimand
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    from core.schemas import ParsedProtocol, EndpointType, Estimand


class TLFType(Enum):
    TABLE = "Table"
    LISTING = "Listing"
    FIGURE = "Figure"


class Orientation(Enum):
    PORTRAIT = "Portrait"
    LANDSCAPE = "Landscape"


@dataclass
class ColumnSpec:
    """Specification for a table column"""
    header: str
    width: float  # inches
    alignment: str  # "L", "C", "R"
    format: Optional[str] = None
    source_variable: Optional[str] = None
    derivation: Optional[str] = None


@dataclass
class RowSpec:
    """Specification for a row in the stub (left-most column)"""
    level: int  # Indentation level (0, 1, 2)
    label: str
    bold: bool = False
    row_type: str = "data"  # "header", "subheader", "data", "total", "spacer"


@dataclass
class FootnoteSpec:
    """Footnote specification"""
    symbol: str  # *, a, b, 1, etc.
    text: str
    applies_to: Optional[str] = None  # Column or row it applies to


@dataclass
class TLFShell:
    """Complete TLF shell specification"""
    number: str  # e.g., "14.1.1"
    title: str
    tlf_type: TLFType
    population: str
    orientation: Orientation
    columns: List[ColumnSpec]
    stub_rows: List[RowSpec]
    footnotes: List[FootnoteSpec]
    source_dataset: str
    filter_condition: Optional[str]
    sort_order: List[str]
    programming_notes: List[str]
    mock_data: Optional[str] = None  # ASCII mock-up of the table

    def to_markdown(self) -> str:
        """Generate markdown specification"""
        lines = [
            f"### {self.tlf_type.value} {self.number}: {self.title}",
            "",
            f"**Population:** {self.population}",
            f"**Orientation:** {self.orientation.value}",
            f"**Source:** {self.source_dataset}",
            ""
        ]

        if self.filter_condition:
            lines.append(f"**Filter:** `{self.filter_condition}`")
            lines.append("")

        # Column specifications
        lines.append("**Column Specifications:**")
        lines.append("")
        lines.append("| Column | Width (in) | Align | Format | Source |")
        lines.append("|--------|------------|-------|--------|--------|")
        for col in self.columns:
            source = col.source_variable or col.derivation or "-"
            fmt = col.format or "-"
            lines.append(f"| {col.header} | {col.width} | {col.alignment} | {fmt} | {source} |")
        lines.append("")

        # Stub hierarchy
        lines.append("**Row Structure (Stub):**")
        lines.append("")
        for row in self.stub_rows[:15]:  # Limit display
            indent = "  " * row.level
            bold_mark = "**" if row.bold else ""
            lines.append(f"- {indent}{bold_mark}{row.label}{bold_mark}")
        if len(self.stub_rows) > 15:
            lines.append(f"- ... ({len(self.stub_rows) - 15} more rows)")
        lines.append("")

        # Sort order
        if self.sort_order:
            lines.append(f"**Sort Order:** {' > '.join(self.sort_order)}")
            lines.append("")

        # Footnotes
        if self.footnotes:
            lines.append("**Footnotes:**")
            lines.append("")
            for fn in self.footnotes:
                lines.append(f"- {fn.symbol} {fn.text}")
            lines.append("")

        # Programming notes
        if self.programming_notes:
            lines.append("**Programming Notes:**")
            lines.append("")
            for note in self.programming_notes:
                lines.append(f"- {note}")
            lines.append("")

        # Mock shell if available
        if self.mock_data:
            lines.append("**Mock Shell:**")
            lines.append("```")
            lines.append(self.mock_data)
            lines.append("```")
            lines.append("")

        return "\n".join(lines)


class TLFShellGenerator:
    """
    Generates production-level TLF shell specifications.
    These specifications can be directly implemented by programmers.
    """

    # Standard safety table specifications
    SAFETY_TABLES = {
        "14.3.1": {
            "title": "Overall Summary of Treatment-Emergent Adverse Events",
            "columns": [
                ("", 2.5, "L"),
                ("Treatment A\\n(N=xxx)", 1.2, "C"),
                ("Treatment B\\n(N=xxx)", 1.2, "C"),
                ("Total\\n(N=xxx)", 1.2, "C"),
            ],
            "rows": [
                (0, "Subjects with at least one:", True, "header"),
                (1, "TEAE", False, "data"),
                (1, "Treatment-related TEAE", False, "data"),
                (1, "Serious AE", False, "data"),
                (1, "Treatment-related SAE", False, "data"),
                (1, "AE leading to discontinuation", False, "data"),
                (1, "AE leading to death", False, "data"),
                (0, "", False, "spacer"),
                (0, "Maximum severity of any TEAE:", True, "header"),
                (1, "Mild", False, "data"),
                (1, "Moderate", False, "data"),
                (1, "Severe", False, "data"),
            ],
            "footnotes": [
                ("a", "TEAEs defined as AEs with onset on or after first dose and within 30 days of last dose"),
                ("b", "Treatment-related per investigator assessment"),
                ("c", "Subjects may be counted in multiple categories"),
            ],
            "dataset": "ADAE",
            "filter": "SAFFL = 'Y' and TRTEMFL = 'Y'"
        },
        "14.3.2": {
            "title": "Treatment-Emergent Adverse Events by System Organ Class and Preferred Term",
            "columns": [
                ("System Organ Class\\n  Preferred Term", 3.0, "L"),
                ("Treatment A\\n(N=xxx)\\nn (%)", 1.1, "C"),
                ("Treatment B\\n(N=xxx)\\nn (%)", 1.1, "C"),
                ("Total\\n(N=xxx)\\nn (%)", 1.1, "C"),
            ],
            "rows": [
                (0, "Any TEAE", True, "total"),
                (0, "GASTROINTESTINAL DISORDERS", True, "header"),
                (1, "Nausea", False, "data"),
                (1, "Vomiting", False, "data"),
                (1, "Diarrhea", False, "data"),
                (0, "GENERAL DISORDERS AND ADMINISTRATION SITE CONDITIONS", True, "header"),
                (1, "Fatigue", False, "data"),
                (1, "Pyrexia", False, "data"),
                (0, "INFECTIONS AND INFESTATIONS", True, "header"),
                (1, "Upper respiratory tract infection", False, "data"),
                (1, "Nasopharyngitis", False, "data"),
            ],
            "footnotes": [
                ("", "MedDRA version XX.X coding dictionary"),
                ("", "Percentages based on number of subjects in population"),
                ("", "Subjects counted once per PT, may appear in multiple SOCs"),
            ],
            "dataset": "ADAE",
            "filter": "SAFFL = 'Y' and TRTEMFL = 'Y'",
            "sort": "SOC (alphabetical), PT (descending frequency within SOC)"
        }
    }

    # Standard efficacy table templates by endpoint type
    EFFICACY_TEMPLATES = {
        EndpointType.EFFICACY: [
            {
                "number": "14.2.1",
                "title": "Primary Efficacy Endpoint - Response Rate at Primary Timepoint",
                "columns": [
                    ("Response Category", 2.5, "L"),
                    ("Treatment A\\n(N=xxx)", 1.3, "C"),
                    ("Treatment B\\n(N=xxx)", 1.3, "C"),
                    ("Difference (95% CI)", 1.5, "C"),
                    ("p-value", 0.8, "C"),
                ],
                "rows": [
                    (0, "Responders, n (%)", True, "data"),
                    (0, "Non-responders, n (%)", False, "data"),
                    (0, "Not evaluable, n", False, "data"),
                ],
                "footnotes": [
                    ("a", "Response defined per protocol Section X.X"),
                    ("b", "Difference = Treatment A - Treatment B"),
                    ("c", "95% CI computed using Newcombe-Wilson method"),
                    ("d", "p-value from Cochran-Mantel-Haenszel test stratified by [stratification factors]"),
                ],
                "dataset": "ADEFF",
                "filter": "ITTFL = 'Y' and PARAMCD = 'PRIMARY' and ANL01FL = 'Y'",
                "programming": [
                    "Response defined as CRIT1FL = 'Y'",
                    "Use PROC FREQ with CMH option for stratified analysis",
                    "Report n (%) with percentages to 1 decimal place",
                ]
            },
            {
                "number": "14.2.2",
                "title": "Primary Efficacy Endpoint - Change from Baseline Over Time",
                "columns": [
                    ("Visit", 1.5, "L"),
                    ("Treatment A\\nN | Mean (SD)\\nMedian (Q1, Q3)", 2.0, "C"),
                    ("Treatment B\\nN | Mean (SD)\\nMedian (Q1, Q3)", 2.0, "C"),
                    ("LS Mean Diff\\n(95% CI)", 1.5, "C"),
                    ("p-value", 0.8, "C"),
                ],
                "rows": [
                    (0, "Baseline", True, "data"),
                    (0, "Week 4", False, "data"),
                    (0, "Week 8", False, "data"),
                    (0, "Week 12", False, "data"),
                    (0, "End of Treatment", False, "data"),
                ],
                "footnotes": [
                    ("a", "Change from baseline = Post-baseline value - Baseline value"),
                    ("b", "LS Mean from MMRM: CHG = TRT VISIT TRT*VISIT BASE STRAT1 STRAT2"),
                    ("c", "Unstructured covariance, Kenward-Roger degrees of freedom"),
                ],
                "dataset": "ADEFF",
                "filter": "ITTFL = 'Y' and PARAMCD = 'PRIMARY' and ANL01FL = 'Y'",
                "programming": [
                    "Include baseline record for display",
                    "MMRM using PROC MIXED with REPEATED statement",
                    "Report N, Mean (SD), Median (Q1, Q3) for observed data",
                ]
            }
        ],
        EndpointType.OS: [
            {
                "number": "14.2.1",
                "title": "Overall Survival Analysis",
                "columns": [
                    ("Statistic", 2.5, "L"),
                    ("Treatment A\\n(N=xxx)", 1.5, "C"),
                    ("Treatment B\\n(N=xxx)", 1.5, "C"),
                ],
                "rows": [
                    (0, "Number of events (%)", True, "data"),
                    (0, "Number censored (%)", False, "data"),
                    (0, "", False, "spacer"),
                    (0, "Median OS, months (95% CI)", True, "data"),
                    (0, "OS rate at 6 months (95% CI)", False, "data"),
                    (0, "OS rate at 12 months (95% CI)", False, "data"),
                    (0, "", False, "spacer"),
                    (0, "Hazard Ratio (95% CI)", True, "data"),
                    (0, "p-value (log-rank test)", False, "data"),
                ],
                "footnotes": [
                    ("a", "Based on Kaplan-Meier estimates"),
                    ("b", "95% CI for median computed using Brookmeyer-Crowley method"),
                    ("c", "HR from Cox model stratified by [factors]; HR < 1 favors Treatment A"),
                    ("d", "Stratified log-rank test"),
                ],
                "dataset": "ADTTE",
                "filter": "ITTFL = 'Y' and PARAMCD = 'OS'",
                "programming": [
                    "Use PROC LIFETEST for KM estimates and log-rank test",
                    "Use PROC PHREG for HR and 95% CI",
                    "Stratification factors: [per protocol]",
                    "Time in months: AVAL / 30.4375",
                ]
            }
        ],
        EndpointType.ORR: [
            {
                "number": "14.2.1",
                "title": "Best Overall Response (ITT Population)",
                "columns": [
                    ("Response Category", 2.0, "L"),
                    ("Treatment A\\n(N=xxx)\\nn (%)", 1.3, "C"),
                    ("Treatment B\\n(N=xxx)\\nn (%)", 1.3, "C"),
                    ("Total\\n(N=xxx)\\nn (%)", 1.3, "C"),
                ],
                "rows": [
                    (0, "Complete Response (CR)", False, "data"),
                    (0, "Partial Response (PR)", False, "data"),
                    (0, "Stable Disease (SD)", False, "data"),
                    (0, "Progressive Disease (PD)", False, "data"),
                    (0, "Not Evaluable (NE)", False, "data"),
                    (0, "", False, "spacer"),
                    (0, "Objective Response Rate (CR+PR)", True, "total"),
                    (0, "95% CI", False, "data"),
                    (0, "Disease Control Rate (CR+PR+SD)", True, "total"),
                    (0, "95% CI", False, "data"),
                ],
                "footnotes": [
                    ("a", "Per RECIST 1.1 criteria"),
                    ("b", "Confirmed response per protocol"),
                    ("c", "95% CI computed using Clopper-Pearson exact method"),
                ],
                "dataset": "ADRS",
                "filter": "ITTFL = 'Y' and PARAMCD = 'BOR' and ANL02FL = 'Y'",
                "programming": [
                    "BOR from ADRS where PARAMCD = 'BOR'",
                    "ORR = (n CR + n PR) / N evaluable",
                    "Use PROC FREQ for CI calculation with EXACT BINOMIAL option",
                ]
            }
        ],
        EndpointType.PFS: [
            {
                "number": "14.2.1",
                "title": "Progression-Free Survival Analysis",
                "columns": [
                    ("Statistic", 2.5, "L"),
                    ("Treatment A\\n(N=xxx)", 1.5, "C"),
                    ("Treatment B\\n(N=xxx)", 1.5, "C"),
                ],
                "rows": [
                    (0, "Number of events (%)", True, "data"),
                    (1, "Disease Progression", False, "data"),
                    (1, "Death", False, "data"),
                    (0, "Number censored (%)", False, "data"),
                    (0, "", False, "spacer"),
                    (0, "Median PFS, months (95% CI)", True, "data"),
                    (0, "PFS rate at 6 months (95% CI)", False, "data"),
                    (0, "PFS rate at 12 months (95% CI)", False, "data"),
                    (0, "", False, "spacer"),
                    (0, "Hazard Ratio (95% CI)", True, "data"),
                    (0, "p-value (stratified log-rank)", False, "data"),
                ],
                "footnotes": [
                    ("a", "Progression per RECIST 1.1 by investigator assessment"),
                    ("b", "Kaplan-Meier estimates; 95% CI by Brookmeyer-Crowley method"),
                    ("c", "Cox PH model stratified by [factors]"),
                    ("d", "HR < 1 favors Treatment A"),
                ],
                "dataset": "ADTTE",
                "filter": "ITTFL = 'Y' and PARAMCD = 'PFS'",
                "programming": [
                    "Event types from EVNTDESC variable",
                    "Censoring per protocol-defined hierarchy",
                    "Use PROC LIFETEST and PROC PHREG",
                ]
            }
        ]
    }

    def __init__(self, llm_client=None):
        """Initialize the TLF shell generator"""
        self.llm_client = llm_client

    def generate_demographics_table(
        self,
        protocol: ParsedProtocol,
        treatment_arms: List[str]
    ) -> TLFShell:
        """Generate demographics and baseline characteristics table"""

        # Build column specs
        columns = [ColumnSpec("Characteristic", 2.5, "L", None, None, None)]
        for arm in treatment_arms:
            columns.append(ColumnSpec(f"{arm}\\n(N=xxx)", 1.3, "C", None, "ADSL", None))
        columns.append(ColumnSpec("Total\\n(N=xxx)", 1.3, "C", None, "ADSL", None))
        if len(treatment_arms) == 2:
            columns.append(ColumnSpec("p-value", 0.8, "C", None, None, "Statistical test"))

        # Build row structure
        rows = [
            RowSpec(0, "Age (years)", True, "header"),
            RowSpec(1, "N", False, "data"),
            RowSpec(1, "Mean (SD)", False, "data"),
            RowSpec(1, "Median (Q1, Q3)", False, "data"),
            RowSpec(1, "Min, Max", False, "data"),
            RowSpec(0, "", False, "spacer"),
            RowSpec(0, "Age Group, n (%)", True, "header"),
            RowSpec(1, "<65 years", False, "data"),
            RowSpec(1, ">=65 years", False, "data"),
            RowSpec(0, "", False, "spacer"),
            RowSpec(0, "Sex, n (%)", True, "header"),
            RowSpec(1, "Male", False, "data"),
            RowSpec(1, "Female", False, "data"),
            RowSpec(0, "", False, "spacer"),
            RowSpec(0, "Race, n (%)", True, "header"),
            RowSpec(1, "White", False, "data"),
            RowSpec(1, "Black or African American", False, "data"),
            RowSpec(1, "Asian", False, "data"),
            RowSpec(1, "Other", False, "data"),
            RowSpec(0, "", False, "spacer"),
            RowSpec(0, "Ethnicity, n (%)", True, "header"),
            RowSpec(1, "Hispanic or Latino", False, "data"),
            RowSpec(1, "Not Hispanic or Latino", False, "data"),
            RowSpec(0, "", False, "spacer"),
            RowSpec(0, "BMI (kg/m2)", True, "header"),
            RowSpec(1, "N", False, "data"),
            RowSpec(1, "Mean (SD)", False, "data"),
            RowSpec(1, "Median (Q1, Q3)", False, "data"),
        ]

        footnotes = [
            FootnoteSpec("a", "Percentages based on the number of subjects in the population column"),
            FootnoteSpec("b", "p-values: ANOVA for continuous, Chi-square for categorical"),
            FootnoteSpec("c", "BMI = Weight (kg) / Height (m)^2"),
        ]

        mock = self._generate_demographics_mock(treatment_arms)

        return TLFShell(
            number="14.1.1",
            title="Demographics and Baseline Characteristics",
            tlf_type=TLFType.TABLE,
            population="ITT Population",
            orientation=Orientation.PORTRAIT,
            columns=columns,
            stub_rows=rows,
            footnotes=footnotes,
            source_dataset="ADSL",
            filter_condition="ITTFL = 'Y'",
            sort_order=["TRT01PN"],
            programming_notes=[
                "Continuous: N, Mean (SD), Median (Q1, Q3), Min-Max",
                "Categorical: n (%) with % = 100 * n / N",
                "Use PROC MEANS for continuous, PROC FREQ for categorical",
                "p-values for descriptive purposes only",
            ],
            mock_data=mock
        )

    def _generate_demographics_mock(self, treatment_arms: List[str]) -> str:
        """Generate ASCII mock of demographics table"""
        header = f"{'Characteristic':<35} | "
        header += " | ".join([f"{arm[:15]:^15}" for arm in treatment_arms])
        header += " | " + f"{'Total':^15}" + " |"

        sep = "-" * len(header)

        rows = [
            sep,
            header,
            sep,
            f"{'Age (years)':<35} |" + " | ".join([f"{'':^15}"] * (len(treatment_arms) + 1)) + " |",
            f"{'  N':<35} | " + " | ".join([f"{'xx':^15}"] * (len(treatment_arms) + 1)) + " |",
            f"{'  Mean (SD)':<35} | " + " | ".join([f"{'xx.x (xx.x)':^15}"] * (len(treatment_arms) + 1)) + " |",
            f"{'  Median (Q1, Q3)':<35} | " + " | ".join([f"{'xx.x (xx.x, xx.x)':^15}"] * (len(treatment_arms) + 1)) + " |",
            f"{'  Min, Max':<35} | " + " | ".join([f"{'xx, xx':^15}"] * (len(treatment_arms) + 1)) + " |",
            sep,
            f"{'Sex, n (%)':<35} |" + " | ".join([f"{'':^15}"] * (len(treatment_arms) + 1)) + " |",
            f"{'  Male':<35} | " + " | ".join([f"{'xx (xx.x)':^15}"] * (len(treatment_arms) + 1)) + " |",
            f"{'  Female':<35} | " + " | ".join([f"{'xx (xx.x)':^15}"] * (len(treatment_arms) + 1)) + " |",
            sep,
        ]

        return "\n".join(rows)

    def generate_efficacy_tables(
        self,
        protocol: ParsedProtocol,
        estimands: Dict[str, Any],
        endpoint_type: EndpointType
    ) -> List[TLFShell]:
        """Generate efficacy TLF shells based on endpoint type"""

        templates = self.EFFICACY_TEMPLATES.get(endpoint_type, self.EFFICACY_TEMPLATES[EndpointType.EFFICACY])
        shells = []

        for template in templates:
            columns = [
                ColumnSpec(
                    header=c[0],
                    width=c[1],
                    alignment=c[2],
                    format=None,
                    source_variable=None,
                    derivation=None
                )
                for c in template["columns"]
            ]

            rows = [
                RowSpec(
                    level=r[0],
                    label=r[1],
                    bold=r[2],
                    row_type=r[3]
                )
                for r in template["rows"]
            ]

            footnotes = [
                FootnoteSpec(symbol=f[0], text=f[1], applies_to=None)
                for f in template["footnotes"]
            ]

            shell = TLFShell(
                number=template["number"],
                title=template["title"],
                tlf_type=TLFType.TABLE,
                population="ITT Population",
                orientation=Orientation.PORTRAIT,
                columns=columns,
                stub_rows=rows,
                footnotes=footnotes,
                source_dataset=template["dataset"],
                filter_condition=template["filter"],
                sort_order=template.get("sort", ["TRT01PN"]) if isinstance(template.get("sort"), list) else [template.get("sort", "TRT01PN")],
                programming_notes=template.get("programming", []),
                mock_data=None
            )
            shells.append(shell)

        return shells

    def generate_safety_tables(self, protocol: ParsedProtocol) -> List[TLFShell]:
        """Generate standard safety TLF shells"""

        shells = []

        for table_num, spec in self.SAFETY_TABLES.items():
            columns = [
                ColumnSpec(
                    header=c[0],
                    width=c[1],
                    alignment=c[2],
                    format="n (xx.x%)" if c[2] == "C" else None,
                    source_variable=None,
                    derivation=None
                )
                for c in spec["columns"]
            ]

            rows = [
                RowSpec(
                    level=r[0],
                    label=r[1],
                    bold=r[2],
                    row_type=r[3]
                )
                for r in spec["rows"]
            ]

            footnotes = [
                FootnoteSpec(symbol=f[0], text=f[1], applies_to=None)
                for f in spec["footnotes"]
            ]

            sort_order = spec.get("sort", ["TRT01AN"])
            if isinstance(sort_order, str):
                sort_order = [sort_order]

            shell = TLFShell(
                number=table_num,
                title=spec["title"],
                tlf_type=TLFType.TABLE,
                population="Safety Population",
                orientation=Orientation.PORTRAIT if len(columns) <= 5 else Orientation.LANDSCAPE,
                columns=columns,
                stub_rows=rows,
                footnotes=footnotes,
                source_dataset=spec["dataset"],
                filter_condition=spec["filter"],
                sort_order=sort_order,
                programming_notes=[
                    "Count subjects, not events, for summary",
                    "Subject counted once per category regardless of number of events",
                    "Percentages based on N in column header",
                ],
                mock_data=None
            )
            shells.append(shell)

        return shells

    def generate_listings(self, protocol: ParsedProtocol) -> List[TLFShell]:
        """Generate standard data listings"""

        listings = []

        # Subject Disposition Listing
        listings.append(TLFShell(
            number="16.1.1",
            title="Subject Disposition",
            tlf_type=TLFType.LISTING,
            population="All Subjects",
            orientation=Orientation.LANDSCAPE,
            columns=[
                ColumnSpec("Subject ID", 1.0, "L", None, "ADSL.SUBJID", None),
                ColumnSpec("Site", 0.6, "C", None, "ADSL.SITEID", None),
                ColumnSpec("Treatment", 1.5, "L", None, "ADSL.TRT01P", None),
                ColumnSpec("Randomization\\nDate", 1.0, "C", "DATE9.", "ADSL.RANDDT", None),
                ColumnSpec("First Dose\\nDate", 1.0, "C", "DATE9.", "ADSL.TRTSDT", None),
                ColumnSpec("Last Dose\\nDate", 1.0, "C", "DATE9.", "ADSL.TRTEDT", None),
                ColumnSpec("End of Study\\nDate", 1.0, "C", "DATE9.", "ADSL.EOSDT", None),
                ColumnSpec("Status", 1.2, "L", None, "ADSL.EOSSTT", None),
                ColumnSpec("Reason for\\nDiscontinuation", 2.0, "L", None, "ADSL.DCSREAS", None),
            ],
            stub_rows=[],
            footnotes=[
                FootnoteSpec("", "Dates displayed as DDMMMYYYY"),
                FootnoteSpec("", "Sorted by Site, Subject ID"),
            ],
            source_dataset="ADSL",
            filter_condition=None,
            sort_order=["SITEID", "SUBJID"],
            programming_notes=[
                "Include all subjects in trial database",
                "Display missing dates as blank",
            ],
            mock_data=None
        ))

        # AE Listing
        listings.append(TLFShell(
            number="16.2.1",
            title="Adverse Events",
            tlf_type=TLFType.LISTING,
            population="Safety Population",
            orientation=Orientation.LANDSCAPE,
            columns=[
                ColumnSpec("Subject ID", 0.8, "L", None, "ADAE.SUBJID", None),
                ColumnSpec("Treatment", 1.2, "L", None, "ADAE.TRTA", None),
                ColumnSpec("SOC", 2.0, "L", None, "ADAE.AEBODSYS", None),
                ColumnSpec("PT", 1.5, "L", None, "ADAE.AEDECOD", None),
                ColumnSpec("Verbatim\\nTerm", 1.5, "L", None, "ADAE.AETERM", None),
                ColumnSpec("Start\\nDate", 0.8, "C", "DATE9.", "ADAE.ASTDT", None),
                ColumnSpec("End\\nDate", 0.8, "C", "DATE9.", "ADAE.AENDT", None),
                ColumnSpec("Severity", 0.7, "C", None, "ADAE.AESEV", None),
                ColumnSpec("Related", 0.6, "C", None, "ADAE.AEREL", None),
                ColumnSpec("SAE", 0.4, "C", None, "ADAE.AESER", None),
                ColumnSpec("Action\\nTaken", 1.0, "L", None, "ADAE.AEACN", None),
                ColumnSpec("Outcome", 1.0, "L", None, "ADAE.AEOUT", None),
            ],
            stub_rows=[],
            footnotes=[
                FootnoteSpec("", "TEAEs only (onset on or after first dose)"),
                FootnoteSpec("", "MedDRA version XX.X; SOC = System Organ Class, PT = Preferred Term"),
                FootnoteSpec("", "Related = Related/Possibly Related per investigator"),
            ],
            source_dataset="ADAE",
            filter_condition="SAFFL = 'Y' and TRTEMFL = 'Y'",
            sort_order=["SUBJID", "ASTDT", "AESEQ"],
            programming_notes=[
                "One row per adverse event",
                "Sort by subject, start date, sequence",
                "Display ongoing events with blank end date",
            ],
            mock_data=None
        ))

        return listings

    def generate_figures(
        self,
        protocol: ParsedProtocol,
        endpoint_type: EndpointType
    ) -> List[TLFShell]:
        """Generate figure specifications based on endpoint type"""

        figures = []

        if endpoint_type in [EndpointType.OS, EndpointType.PFS, EndpointType.DFS, EndpointType.EFS]:
            # Kaplan-Meier figure
            figures.append(TLFShell(
                number="14.2.F1",
                title=f"Kaplan-Meier Estimate of {endpoint_type.value}",
                tlf_type=TLFType.FIGURE,
                population="ITT Population",
                orientation=Orientation.LANDSCAPE,
                columns=[],  # N/A for figures
                stub_rows=[],
                footnotes=[
                    FootnoteSpec("", "Kaplan-Meier estimates with 95% confidence bands"),
                    FootnoteSpec("", "Tick marks indicate censored observations"),
                    FootnoteSpec("", "Number at risk shown below x-axis"),
                ],
                source_dataset="ADTTE",
                filter_condition=f"ITTFL = 'Y' and PARAMCD = '{endpoint_type.value.split()[0] if ' ' not in endpoint_type.value else endpoint_type.value}'",
                sort_order=["TRT01P"],
                programming_notes=[
                    "Use PROC LIFETEST with PLOTS=SURVIVAL(ATRISK CB)",
                    "X-axis: Time in months (0 to max follow-up)",
                    "Y-axis: Survival probability (0.0 to 1.0)",
                    "Separate line per treatment arm with legend",
                    "Add median survival time annotation",
                    "Include number at risk table below figure",
                ],
                mock_data="""
+-----------------------------------------------------------------------+
|  1.0 |--o----o--------                                                |
|      |       \\                                                        |
|      |        \\-------o----o----                                      |
|  0.8 |               Treatment A ----                                 |
|      |----o---------o                                                 |
|      |              \\                                                 |
|  0.6 |               \\----o----o----                                  |
|      |                    Treatment B ----                            |
|  0.4 |                                                                |
|      |                                                                |
|  0.2 |                                                                |
|      |                                                                |
|  0.0 +----------------------------------------------------------------|
|      0     3     6     9    12    15    18    21    24 months         |
+-----------------------------------------------------------------------+
Number at risk:
Trt A:  100   95    88    82    75    68    55    42    30
Trt B:  100   90    80    70    60    48    35    22    15
"""
            ))

            # Forest plot for subgroups
            figures.append(TLFShell(
                number="14.2.F2",
                title=f"Forest Plot of {endpoint_type.value} by Subgroup",
                tlf_type=TLFType.FIGURE,
                population="ITT Population",
                orientation=Orientation.LANDSCAPE,
                columns=[],
                stub_rows=[
                    RowSpec(0, "Overall", True, "header"),
                    RowSpec(0, "Age Group", True, "header"),
                    RowSpec(1, "<65 years", False, "data"),
                    RowSpec(1, ">=65 years", False, "data"),
                    RowSpec(0, "Sex", True, "header"),
                    RowSpec(1, "Male", False, "data"),
                    RowSpec(1, "Female", False, "data"),
                    RowSpec(0, "ECOG PS", True, "header"),
                    RowSpec(1, "0", False, "data"),
                    RowSpec(1, "1", False, "data"),
                ],
                footnotes=[
                    FootnoteSpec("", "HR and 95% CI from unstratified Cox model within each subgroup"),
                    FootnoteSpec("", "HR < 1 favors experimental treatment"),
                    FootnoteSpec("", "Subgroup analyses are exploratory; not adjusted for multiplicity"),
                ],
                source_dataset="ADTTE + ADSL subgroup flags",
                filter_condition="ITTFL = 'Y'",
                sort_order=[],
                programming_notes=[
                    "Calculate HR and 95% CI within each subgroup",
                    "Display: Subgroup | n/N (%) | HR (95% CI) | Forest plot",
                    "Vertical line at HR = 1 (null)",
                    "Use log scale for x-axis",
                    "Include interaction p-values if requested",
                ],
                mock_data=None
            ))

        # Responder analysis waterfall (for response endpoints)
        if endpoint_type in [EndpointType.ORR, EndpointType.EFFICACY]:
            figures.append(TLFShell(
                number="14.2.F1",
                title="Response Over Time by Subject (Swimmer Plot)" if endpoint_type == EndpointType.ORR else "Change from Baseline by Visit",
                tlf_type=TLFType.FIGURE,
                population="ITT Population",
                orientation=Orientation.LANDSCAPE,
                columns=[],
                stub_rows=[],
                footnotes=[
                    FootnoteSpec("", "Each bar represents one subject"),
                    FootnoteSpec("", "Response status indicated by color/symbol"),
                ],
                source_dataset="ADRS" if endpoint_type == EndpointType.ORR else "ADEFF",
                filter_condition="ITTFL = 'Y'",
                sort_order=["Best response category", "Time on treatment"],
                programming_notes=[
                    "PROC SGPLOT with HBAR or HIGHLOW",
                    "Color coding: CR=green, PR=blue, SD=yellow, PD=red",
                    "Sort subjects by best response then duration",
                ],
                mock_data=None
            ))

        return figures

    def generate_all_shells(
        self,
        protocol: ParsedProtocol,
        estimands: Dict[str, Any]
    ) -> Dict[str, List[TLFShell]]:
        """Generate all TLF shells for the study"""

        endpoint_type = EndpointType.OTHER
        if protocol.primary_estimand:
            endpoint_type = protocol.primary_estimand.variable_type

        treatment_arms = getattr(protocol, 'treatment_arms', None) or ["Treatment A", "Treatment B"]

        shells = {
            "demographics": [self.generate_demographics_table(protocol, treatment_arms)],
            "efficacy": self.generate_efficacy_tables(protocol, estimands, endpoint_type),
            "safety": self.generate_safety_tables(protocol),
            "listings": self.generate_listings(protocol),
            "figures": self.generate_figures(protocol, endpoint_type)
        }

        return shells

    def generate_tlf_document(
        self,
        protocol: ParsedProtocol,
        estimands: Dict[str, Any]
    ) -> str:
        """Generate complete TLF specification document"""

        all_shells = self.generate_all_shells(protocol, estimands)

        lines = [
            "# TLF SHELL SPECIFICATIONS",
            "",
            f"**Study:** {protocol.nct_id}",
            f"**Date:** Generated",
            "",
            "---",
            "",
            "## Overview",
            "",
            "This document contains detailed TLF (Tables, Listings, Figures) shell specifications.",
            "These specifications define the structure, content, and formatting for all outputs.",
            "",
            "### Summary of Outputs",
            "",
            "| Category | Count |",
            "|----------|-------|",
        ]

        total = 0
        for category, shells in all_shells.items():
            lines.append(f"| {category.title()} | {len(shells)} |")
            total += len(shells)
        lines.append(f"| **Total** | **{total}** |")

        lines.append("")
        lines.append("---")
        lines.append("")

        # Demographics tables
        lines.append("## Demographics and Baseline Characteristics")
        lines.append("")
        for shell in all_shells["demographics"]:
            lines.append(shell.to_markdown())

        lines.append("---")
        lines.append("")

        # Efficacy tables
        lines.append("## Efficacy Tables")
        lines.append("")
        for shell in all_shells["efficacy"]:
            lines.append(shell.to_markdown())

        lines.append("---")
        lines.append("")

        # Safety tables
        lines.append("## Safety Tables")
        lines.append("")
        for shell in all_shells["safety"]:
            lines.append(shell.to_markdown())

        lines.append("---")
        lines.append("")

        # Figures
        lines.append("## Figures")
        lines.append("")
        for shell in all_shells["figures"]:
            lines.append(shell.to_markdown())

        lines.append("---")
        lines.append("")

        # Listings
        lines.append("## Data Listings")
        lines.append("")
        for shell in all_shells["listings"]:
            lines.append(shell.to_markdown())

        return "\n".join(lines)


# Factory function
def create_tlf_generator(llm_client=None) -> TLFShellGenerator:
    """Create a TLF shell generator instance"""
    return TLFShellGenerator(llm_client=llm_client)
