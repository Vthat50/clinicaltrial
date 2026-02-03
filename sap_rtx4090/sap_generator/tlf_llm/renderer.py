"""Render LLM-generated TLF shell specifications to Markdown or DOCX format.

DOCX output uses real pharmaceutical TLF shell formatting:
- Courier New monospace font (standard for SAS/RTF output alignment)
- Horizontal rules only (top, under header, bottom) — no grid borders
- Page header: Protocol ID + CONFIDENTIAL + Page X of Y
- Page footer: Source dataset + Program name + Date placeholder
- Footnotes as bracketed numbers below the table
"""

import logging
from io import BytesIO
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Format code → placeholder mapping
# ---------------------------------------------------------------------------

_FORMAT_PLACEHOLDERS = {
    "count": "xx",
    "count_pct": "xx (xx.x)",
    "percentage": "xx.x",
    "mean": "xx.x",
    "sd": "xx.xx",
    "mean_sd": "xx.x (xx.xx)",
    "mean_se": "xx.x (xx.xx)",
    "mean_ci": "xx.x (xx.x, xx.x)",
    "median": "xx.x",
    "median_ci": "xx.x (xx.x, xx.x)",
    "median_range": "xx.x (xx.x, xx.x)",
    "min": "xx.x",
    "max": "xx.x",
    "q1_q3": "xx.x, xx.x",
    "min_max": "xx.x, xx.x",
    "ci_95": "(xx.x, xx.x)",
    "hr_ci": "x.xx (xx.x, xx.x)",
    "hazard_ratio": "x.xx (xx.x, xx.x)",
    "diff_ci": "xx.x (xx.x, xx.x)",
    "ratio_ci": "x.xx (xx.x, xx.x)",
    "rate_ci": "xx.x (xx.x, xx.x)",
    "p_value": "x.xxxx",
    "rate_ratio": "x.xx (xx.x, xx.x)",
    "or_ci": "x.xx (xx.x, xx.x)",
    "events_rate": "xx (xx.x)",
    "n_pct": "xx (xx.x)",
    "fixed": "xxx",
    "text": "xxx",
}

# Comparison formats: single value spanning columns, not per-arm
_COMPARISON_FORMATS = {
    "hr_ci", "hazard_ratio", "diff_ci", "ratio_ci", "p_value",
    "or_ci", "rate_ratio",
}

_SECTION_LABELS = {
    "14.1": "Section 14.1 — Disposition and Demographics",
    "14.2": "Section 14.2 — Efficacy",
    "14.3": "Section 14.3 — Safety",
    "16.2": "Section 16.2 — Data Listings",
}


def _placeholder(fmt: str) -> str:
    return _FORMAT_PLACEHOLDERS.get(fmt, "xxx")


# =========================================================================
# MARKDOWN RENDERING
# =========================================================================

def _render_table_md(table: dict) -> str:
    number = table.get("number", "")
    title = table.get("title", "")
    population = table.get("population", "")
    source = table.get("source", "")
    orientation = table.get("orientation", "PORTRAIT")
    columns = table.get("columns", [])
    rows = table.get("rows", [])
    footnotes = table.get("footnotes", [])

    lines = []

    pop_suffix = ""
    if population and population.lower() not in title.lower():
        pop_suffix = f" ({population} Population)"
    lines.append(f"### {number}: {title}{pop_suffix}")
    lines.append("")
    lines.append(
        f"**Source Dataset:** {source} | **Population:** {population} "
        f"| **Orientation:** {orientation}"
    )
    lines.append("")

    if columns:
        headers = [c.get("header", "").replace("\n", " ") for c in columns]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join(["---" for _ in columns]) + "|")
    else:
        columns = [{"header": "Parameter"}, {"header": "Value"}]
        lines.append("| Parameter | Value |")
        lines.append("|-----------|-------|")

    # Detect multi-column label rows (visit/statistic fields)
    has_multi_label = any(row.get("visit") or row.get("statistic") for row in rows)

    if has_multi_label:
        # Multi-column label: columns include Parameter, Visit, Statistic, then data arms
        # Data columns start after the label columns (Parameter, Visit, Statistic = first 3)
        num_label_cols = 3
        num_data_cols = max(len(columns) - num_label_cols, 1)
    else:
        num_label_cols = 1
        num_data_cols = max(len(columns) - 1, 1)

    for row in rows:
        label = row.get("label", "")
        row_type = row.get("type", "data")
        fmt = row.get("format", "")
        indent = row.get("indent", 0)
        bold = row.get("bold", False)
        visit = row.get("visit", "")
        statistic = row.get("statistic", "")

        if row_type == "spacer":
            lines.append("| " + " | ".join(["" for _ in columns]) + " |")
            continue

        # For non-multi-label tables, skip empty rows
        if not has_multi_label and not label:
            lines.append("| " + " | ".join(["" for _ in columns]) + " |")
            continue

        display_label = ("\u00a0\u00a0" * indent) + label
        if bold:
            display_label = f"**{display_label}**"

        if has_multi_label:
            # Multi-column label: Parameter | Visit | Statistic | data columns...
            if row_type == "header":
                cells = [display_label, visit, statistic] + ["" for _ in range(num_data_cols)]
            elif fmt in _COMPARISON_FORMATS:
                ph = _placeholder(fmt)
                cells = [display_label, visit, statistic, ph] + ["" for _ in range(num_data_cols - 1)]
            else:
                ph = _placeholder(fmt) if fmt else ""
                cells = [display_label, visit, statistic] + ([ph] * num_data_cols if ph else ["" for _ in range(num_data_cols)])
        else:
            if row_type == "header":
                cells = [display_label] + ["" for _ in range(num_data_cols)]
            elif fmt in _COMPARISON_FORMATS:
                ph = _placeholder(fmt)
                cells = [display_label, ph] + ["" for _ in range(num_data_cols - 1)]
            else:
                ph = _placeholder(fmt)
                cells = [display_label] + [ph for _ in range(num_data_cols)]

        lines.append("| " + " | ".join(cells) + " |")

    lines.append("")

    if footnotes:
        for i, fn in enumerate(footnotes, 1):
            lines.append(f"[{i}] {fn}")
        lines.append("")

    programming_notes = table.get("programming_notes", "")
    if programming_notes:
        lines.append(f"**Programming Notes:** {programming_notes}")
        lines.append("")

    table_num = str(number).replace("Table ", "").replace(".", "_")
    lines.append(f"Source: {source}  |  Program: t_{table_num}.sas  |  Date: DDMONYYYY")
    lines.append("")

    return "\n".join(lines)


def _render_figure_md(fig: dict) -> str:
    number = fig.get("number", "")
    title = fig.get("title", "")
    fig_type = fig.get("type", "figure")
    population = fig.get("population", "")
    endpoint = fig.get("endpoint", "")

    lines = [f"### {number}: {title}", ""]
    if population:
        lines.append(f"Population: {population}")
    if endpoint:
        lines.append(f"Endpoint: {endpoint}")
    lines.append(f"Type: {fig_type.replace('_', ' ').title()}")
    lines.append("")

    if "km" in fig_type.lower():
        lines.append("[Kaplan-Meier survival curve — to be generated by statistical programming]")
    elif "forest" in fig_type.lower():
        lines.append("[Forest plot — to be generated by statistical programming]")
    elif "waterfall" in fig_type.lower():
        lines.append("[Waterfall plot — to be generated by statistical programming]")
    elif "swimmer" in fig_type.lower():
        lines.append("[Swimmer plot — to be generated by statistical programming]")
    else:
        lines.append("[Figure placeholder — to be generated by statistical programming]")

    lines.append("")
    return "\n".join(lines)


def _render_listing_md(listing: dict) -> str:
    number = listing.get("number", "")
    title = listing.get("title", "")
    population = listing.get("population", "Safety")
    source = listing.get("source", "")
    sort_order = listing.get("sort_order", "")
    page_break_by = listing.get("page_break_by", "")
    footnotes = listing.get("footnotes", [])
    programming_notes = listing.get("programming_notes", "")
    variables = listing.get(
        "variables", ["Subject ID", "Treatment", "Parameter", "Value"]
    )

    lines = [
        f"### {number}: {title} ({population} Population)",
        "",
        f"**Population:** {population} | **Source:** {source} | **Orientation:** LANDSCAPE",
    ]
    if sort_order:
        lines.append(f"**Sort Order:** {sort_order}")
    if page_break_by:
        lines.append(f"**Page Break By:** {page_break_by}")
    lines.append("")

    lines.append("| " + " | ".join(variables) + " |")
    lines.append("|" + "|".join(["---" for _ in variables]) + "|")
    lines.append("| " + " | ".join(["xxx" for _ in variables]) + " |")
    lines.append("")

    if footnotes:
        for i, fn in enumerate(footnotes, 1):
            lines.append(f"[{i}] {fn}")
        lines.append("")

    if programming_notes:
        lines.append(f"**Programming Notes:** {programming_notes}")
        lines.append("")

    listing_num = str(number).replace("Listing ", "").replace(".", "_")
    lines.append(f"Source: {source}  |  Program: l_{listing_num}.sas  |  Date: DDMONYYYY")
    lines.append("")

    return "\n".join(lines)


def _render_summary_md(
    tables: list[dict], figures: list[dict], listings: list[dict]
) -> str:
    lines = ["---", "", "### TLF Shell Summary", "", "| Category | Count |", "|----------|-------|"]

    section_counts: dict[str, int] = {}
    for t in tables:
        sec = t.get("section", "14.3")
        cat = {"14.1": "Disposition & Demographics", "14.2": "Efficacy", "14.3": "Safety"}.get(sec, sec)
        section_counts[cat] = section_counts.get(cat, 0) + 1

    for cat, count in sorted(section_counts.items()):
        lines.append(f"| {cat} | {count} |")

    lines.append(f"| Figures | {len(figures)} |")
    lines.append(f"| Listings | {len(listings)} |")
    total = len(tables) + len(figures) + len(listings)
    lines.append(f"| **Total TLFs** | **{total}** |")
    lines.append("")

    return "\n".join(lines)


def render_markdown(
    tables: list[dict],
    figures: list[dict],
    listings: list[dict],
    domain_facts: Optional[dict] = None,
) -> str:
    parts = ["# TLF Shell Specifications\n"]
    parts.append(
        f"**Total:** {len(tables)} tables, {len(figures)} figures, "
        f"{len(listings)} listings\n"
    )

    if tables:
        parts.append("## Tables\n")
        current_section = ""
        for t in tables:
            # Debug: log table keys to see if columns/rows are present
            logger.info(f"[Renderer] Table '{t.get('title', '?')[:50]}' keys: {list(t.keys())}, "
                        f"columns={len(t.get('columns', []))}, rows={len(t.get('rows', []))}")
            section = t.get("section", "")
            if section != current_section:
                current_section = section
                section_label = _SECTION_LABELS.get(section, section)
                parts.append(f"\n### {section_label}\n")
            parts.append(_render_table_md(t))

    if figures:
        parts.append("\n## Figures\n")
        for fig in figures:
            parts.append(_render_figure_md(fig))

    if listings:
        parts.append("\n## Listings (ICH E3 Section 16.2)\n")
        for li in listings:
            parts.append(_render_listing_md(li))

    parts.append(_render_summary_md(tables, figures, listings))

    return "\n".join(parts)


# =========================================================================
# DOCX RENDERING — Pharmaceutical TLF Shell Format
# =========================================================================

_FONT = "Courier New"
_FONT_SIZE_BODY = 9
_FONT_SIZE_HEADER = 9
_FONT_SIZE_TITLE = 10
_FONT_SIZE_FOOTNOTE = 8
_FONT_SIZE_PAGE_HDR = 8


def render_docx(
    tables: list[dict],
    figures: list[dict],
    listings: list[dict],
) -> bytes:
    """Render TLF shells as a Word document in pharmaceutical format.

    - Courier New monospace throughout
    - Horizontal rules only (no vertical grid lines)
    - Page header/footer with protocol info
    - Bracketed footnotes
    """
    try:
        from docx import Document
        from docx.shared import Inches, Pt, RGBColor, Emu
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT
        from docx.enum.section import WD_ORIENT
        from docx.oxml.ns import qn, nsdecls
        from docx.oxml import parse_xml
    except ImportError:
        logger.error("python-docx not installed")
        raise ImportError("python-docx is required for DOCX output")

    doc = Document()

    # --- Page setup ---
    sect = doc.sections[0]
    sect.page_width = Inches(8.5)
    sect.page_height = Inches(11)
    sect.top_margin = Inches(1)
    sect.bottom_margin = Inches(0.75)
    sect.left_margin = Inches(0.75)
    sect.right_margin = Inches(0.75)

    # --- Default font: Courier New ---
    style = doc.styles["Normal"]
    style.font.name = _FONT
    style.font.size = Pt(_FONT_SIZE_BODY)

    # --- Page header ---
    hdr = sect.header
    hdr.is_linked_to_previous = False
    hp = hdr.paragraphs[0]
    hp.text = ""
    run_left = hp.add_run("Sponsor Name          Protocol Number          CONFIDENTIAL          Page X of Y")
    run_left.font.name = _FONT
    run_left.font.size = Pt(_FONT_SIZE_PAGE_HDR)
    run_left.font.color.rgb = RGBColor(100, 100, 100)

    # --- Helpers ---

    def _set_borders_horiz_only(tbl):
        """Remove all borders, then add top border on first row and
        bottom border on last row, plus bottom border on header row."""
        tbl_pr = tbl._tbl.tblPr
        borders_xml = (
            f'<w:tblBorders {nsdecls("w")}>'
            '  <w:top w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
            '  <w:left w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
            '  <w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
            '  <w:right w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
            '  <w:insideH w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
            '  <w:insideV w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
            '</w:tblBorders>'
        )
        existing = tbl_pr.find(qn('w:tblBorders'))
        if existing is not None:
            tbl_pr.remove(existing)
        tbl_pr.append(parse_xml(borders_xml))

    def _add_bottom_border_to_row(row):
        """Add a bottom border line to every cell in a row (header underline)."""
        for cell in row.cells:
            tc_pr = cell._tc.get_or_add_tcPr()
            borders_xml = (
                f'<w:tcBorders {nsdecls("w")}>'
                '  <w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
                '</w:tcBorders>'
            )
            existing = tc_pr.find(qn('w:tcBorders'))
            if existing is not None:
                tc_pr.remove(existing)
            tc_pr.append(parse_xml(borders_xml))

    def _set_cell(cell, text, bold=False, size=None, indent=0, align=None):
        cell.text = ""
        p = cell.paragraphs[0]
        if align:
            p.alignment = align
        prefix = "  " * indent
        run = p.add_run(prefix + str(text))
        run.font.name = _FONT
        run.font.size = Pt(size or _FONT_SIZE_BODY)
        run.bold = bold

    def _add_landscape_section(doc):
        new_sect = doc.add_section(2)
        new_sect.orientation = WD_ORIENT.LANDSCAPE
        new_sect.page_width = Inches(11)
        new_sect.page_height = Inches(8.5)
        new_sect.top_margin = Inches(0.75)
        new_sect.bottom_margin = Inches(0.75)
        new_sect.left_margin = Inches(0.75)
        new_sect.right_margin = Inches(0.75)
        return new_sect

    def _add_portrait_section(doc):
        new_sect = doc.add_section(2)
        new_sect.orientation = WD_ORIENT.PORTRAIT
        new_sect.page_width = Inches(8.5)
        new_sect.page_height = Inches(11)
        new_sect.top_margin = Inches(1)
        new_sect.bottom_margin = Inches(0.75)
        new_sect.left_margin = Inches(0.75)
        new_sect.right_margin = Inches(0.75)
        return new_sect

    def _add_rule(doc):
        """Add a thin horizontal rule paragraph."""
        p = doc.add_paragraph()
        p_fmt = p.paragraph_format
        p_fmt.space_before = Pt(0)
        p_fmt.space_after = Pt(0)
        pPr = p._p.get_or_add_pPr()
        bottom = parse_xml(
            f'<w:pBdr {nsdecls("w")}>'
            '  <w:bottom w:val="single" w:sz="4" w:space="1" w:color="000000"/>'
            '</w:pBdr>'
        )
        pPr.append(bottom)

    def _add_text(doc, text, bold=False, size=None, italic=False, color=None, align=None, keep_with_next=False):
        """Add a text paragraph.

        Fix 5.7: Added keep_with_next parameter to prevent orphaned titles.
        """
        p = doc.add_paragraph()
        if align:
            p.alignment = align
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(1)
        # Fix 5.7: Keep title paragraphs with following content
        if keep_with_next:
            p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = _FONT
        run.font.size = Pt(size or _FONT_SIZE_BODY)
        run.bold = bold
        run.italic = italic
        if color:
            run.font.color.rgb = color
        return p

    def _set_header_row_repeat(tbl):
        """Mark the first row as a header row that repeats on each page.

        Fix 5.3: Essential for multi-page tables like the 352-row chemistry table.
        Without this, pages 2+ have no column headers.
        """
        first_row = tbl.rows[0]._tr
        trPr = first_row.get_or_add_trPr()
        tblHeader = parse_xml(f'<w:tblHeader {nsdecls("w")}/>')
        trPr.append(tblHeader)

    def _calculate_column_widths(headers: list[str], data_rows: list[list[str]],
                                  total_width: float, min_width: float = 0.4,
                                  chars_per_inch: float = 10.0) -> list[float]:
        """Calculate content-aware column widths to minimize text wrapping.

        Uses a priority-based algorithm:
        1. Calculate ideal width for each column based on max content
        2. For dense tables (many columns), use sqrt scaling to compress differences
        3. Ensure long-content columns get proportionally more space

        Args:
            headers: List of header strings
            data_rows: List of rows, each row is a list of cell strings
            total_width: Total available width in inches
            min_width: Minimum column width in inches
            chars_per_inch: Characters per inch at current font size (9pt Courier ≈ 10)

        Returns:
            List of column widths in inches
        """
        num_cols = len(headers)
        if num_cols == 0:
            return []

        # Calculate max content length for each column
        max_lengths = []
        for col_idx in range(num_cols):
            # Header length (may have newlines, take longest line)
            header_text = headers[col_idx] if col_idx < len(headers) else ""
            header_lines = header_text.split('\n') if header_text else [""]
            header_len = max(len(line) for line in header_lines)

            # Data content length
            data_len = 0
            for row in data_rows:
                if col_idx < len(row):
                    cell_text = str(row[col_idx]) if row[col_idx] else ""
                    cell_lines = cell_text.split('\n') if cell_text else [""]
                    cell_len = max(len(line) for line in cell_lines)
                    data_len = max(data_len, cell_len)

            # Use max of header and data, with minimum of 3 chars
            max_lengths.append(max(header_len, data_len, 3))

        # For dense tables (>6 columns), use power scaling to:
        # - Give proportionally MORE space to longer content columns
        # - Compress short columns to free up space
        if num_cols > 8:
            # For very dense tables: use 0.7 power (more aggressive compression)
            scaled_lengths = [length ** 0.7 for length in max_lengths]
        elif num_cols > 6:
            # For moderately dense tables: use 0.8 power
            scaled_lengths = [length ** 0.8 for length in max_lengths]
        else:
            scaled_lengths = max_lengths

        # Calculate proportional widths
        total_scaled = sum(scaled_lengths)
        if total_scaled > 0:
            widths = [(length / total_scaled) * total_width for length in scaled_lengths]
        else:
            widths = [total_width / num_cols] * num_cols

        # Apply minimum width
        widths = [max(w, min_width) for w in widths]

        # Re-normalize to fit total width after applying minimums
        total_actual = sum(widths)
        if total_actual > total_width:
            # Scale down, but protect minimum widths
            excess = total_actual - total_width
            reducible = [max(0, w - min_width) for w in widths]
            total_reducible = sum(reducible)

            if total_reducible > 0:
                for i in range(num_cols):
                    reduction = (reducible[i] / total_reducible) * excess
                    widths[i] = max(widths[i] - reduction, min_width)

        return widths

    def _set_table_column_widths(tbl, widths: list[float]):
        """Set explicit column widths on a Word table.

        Args:
            tbl: python-docx Table object
            widths: List of widths in inches
        """
        for col_idx, width in enumerate(widths):
            if col_idx < len(tbl.columns):
                tbl.columns[col_idx].width = Inches(width)
                # Also set width on each cell in the column for consistency
                for row in tbl.rows:
                    if col_idx < len(row.cells):
                        row.cells[col_idx].width = Inches(width)

    # =================================================================
    # TITLE PAGE
    # =================================================================
    doc.add_paragraph("")
    doc.add_paragraph("")
    _add_text(doc, "TABLE, LISTING, AND FIGURE SHELLS",
              bold=True, size=14, align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_paragraph("")

    total = len(tables) + len(figures) + len(listings)
    _add_text(doc,
              f"{len(tables)} Tables  |  {len(figures)} Figures  |  "
              f"{len(listings)} Listings  |  {total} Total",
              size=10, align=WD_ALIGN_PARAGRAPH.CENTER)

    # =================================================================
    # TABLES — Word table format with horizontal-only borders
    # =================================================================

    # Track current orientation to minimize section breaks
    current_orientation = "PORTRAIT"

    for table_dict in tables:
        number = table_dict.get("number", "")
        title = table_dict.get("title", "")
        population = table_dict.get("population", "")
        source = table_dict.get("source", "")
        columns = table_dict.get("columns", [])
        rows = table_dict.get("rows", [])
        footnotes = table_dict.get("footnotes", [])
        orientation = table_dict.get("orientation", "PORTRAIT").upper()

        # Fix 5.1: Handle per-table orientation
        # If this table needs landscape and we're in portrait, switch
        if orientation == "LANDSCAPE" and current_orientation == "PORTRAIT":
            _add_landscape_section(doc)
            current_orientation = "LANDSCAPE"
        elif orientation == "PORTRAIT" and current_orientation == "LANDSCAPE":
            _add_portrait_section(doc)
            current_orientation = "PORTRAIT"
        else:
            doc.add_page_break()

        if not columns:
            columns = [{"header": "Parameter"}, {"header": "Value"}]

        # Detect multi-column label rows (visit/statistic fields)
        has_multi_label = any(row.get("visit") or row.get("statistic") for row in rows)

        if has_multi_label:
            num_label_cols = 3  # Parameter, Visit, Statistic
            num_data_cols = max(len(columns) - num_label_cols, 1)
        else:
            num_label_cols = 1
            num_data_cols = max(len(columns) - 1, 1)

        num_total_cols = len(columns)

        # Title block (no duplicate page header — uses section header only)
        # Fix 5.7: Use keep_with_next to prevent orphaned titles
        pop_suffix = ""
        if population and population.lower() not in title.lower():
            pop_suffix = f"  ({population} Population)"
        _add_text(doc, f"{number}", bold=True, size=_FONT_SIZE_BODY, keep_with_next=True)
        _add_text(doc, f"{title}{pop_suffix}", bold=True, size=_FONT_SIZE_BODY, keep_with_next=True)

        # Build data rows list for the Word table
        table_rows_data = []
        for row in rows:
            label = row.get("label", "")
            row_type = row.get("type", "data")
            fmt = row.get("format", "")
            indent = row.get("indent", 0)
            bold = row.get("bold", False)
            visit = row.get("visit", "")
            statistic = row.get("statistic", "")

            if row_type == "spacer":
                table_rows_data.append({"cells": [""] * num_total_cols, "bold": False, "type": "spacer"})
                continue

            indent_str = "  " * indent
            display_label = indent_str + label

            if has_multi_label:
                if row_type == "header":
                    cells = [display_label] + [""] * (num_total_cols - 1)
                else:
                    ph = _placeholder(fmt) if fmt else ""
                    cells = [display_label, visit, statistic] + ([ph] * num_data_cols if ph else [""] * num_data_cols)
            else:
                if row_type == "header":
                    cells = [display_label] + [""] * num_data_cols
                elif fmt in _COMPARISON_FORMATS:
                    ph = _placeholder(fmt)
                    cells = [display_label, ph] + [""] * (num_data_cols - 1)
                elif not label:
                    cells = [""] * num_total_cols
                else:
                    ph = _placeholder(fmt)
                    cells = [display_label] + [ph] * num_data_cols

            table_rows_data.append({"cells": cells, "bold": bold or row_type == "header", "type": row_type})

        # Create Word table: 1 header row + data rows
        total_word_rows = 1 + len(table_rows_data)
        tbl = doc.add_table(rows=total_word_rows, cols=num_total_cols)
        tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
        tbl.autofit = False  # Disable autofit to use explicit widths
        _set_borders_horiz_only(tbl)

        # Calculate content-aware column widths
        headers = [c.get("header", "").replace("\n", " ") for c in columns]
        data_for_width = [row_data["cells"] for row_data in table_rows_data]
        # Portrait = 7.0" usable, Landscape = 9.5" usable
        usable_width = 9.5 if orientation.upper() == "LANDSCAPE" else 7.0
        col_widths = _calculate_column_widths(headers, data_for_width, usable_width)
        _set_table_column_widths(tbl, col_widths)

        # Header row
        for c_idx, hdr_text in enumerate(headers):
            align = None
            col_align = columns[c_idx].get("align", "L") if c_idx < len(columns) else "L"
            if col_align == "C":
                align = WD_ALIGN_PARAGRAPH.CENTER
            _set_cell(tbl.rows[0].cells[c_idx], hdr_text, bold=True,
                      size=_FONT_SIZE_HEADER, align=align)
        _add_bottom_border_to_row(tbl.rows[0])

        # Fix 5.3: Set header row to repeat on each page for multi-page tables
        _set_header_row_repeat(tbl)

        # Data rows
        for r_idx, row_data in enumerate(table_rows_data):
            word_row = tbl.rows[r_idx + 1]
            cells = row_data["cells"]
            is_bold = row_data["bold"]

            for c_idx, cell_text in enumerate(cells):
                if c_idx >= num_total_cols:
                    break
                align = None
                # Center-align data columns (not the label columns)
                if has_multi_label and c_idx >= 3:
                    align = WD_ALIGN_PARAGRAPH.CENTER
                elif not has_multi_label and c_idx >= 1:
                    align = WD_ALIGN_PARAGRAPH.CENTER
                _set_cell(word_row.cells[c_idx], cell_text, bold=is_bold,
                          size=_FONT_SIZE_BODY, align=align)

        # Footnotes
        if footnotes:
            for i, fn in enumerate(footnotes, 1):
                _add_text(doc, f"[{i}] {fn}", size=_FONT_SIZE_FOOTNOTE)

        # Programming notes
        prog_notes = table_dict.get("programming_notes", "")
        if prog_notes:
            _add_text(doc, f"Programming Notes: {prog_notes}",
                      size=_FONT_SIZE_FOOTNOTE, color=RGBColor(100, 100, 100))

        # Source line
        table_num = str(number).replace("Table ", "").replace(".", "_")
        _add_text(doc, "", size=_FONT_SIZE_FOOTNOTE)
        _add_text(doc,
                  f"Source: {source}        "
                  f"Program: t_{table_num}.sas        "
                  f"Date: DDMONYYYY",
                  size=_FONT_SIZE_FOOTNOTE, color=RGBColor(100, 100, 100))

    # =================================================================
    # FIGURES
    # =================================================================
    if figures:
        doc.add_page_break()
        _add_text(doc, "FIGURE SHELLS", bold=True, size=12)

        for fig in figures:
            doc.add_page_break()

            fig_type = fig.get("type", "figure")
            fig_title = fig.get("title", "")
            fig_number = fig.get("number", "")
            endpoint = fig.get("endpoint", "")
            fig_population = fig.get("population", "")

            _add_text(doc, f"{fig_number}", bold=True, size=_FONT_SIZE_TITLE)
            _add_text(doc, fig_title, bold=True, size=_FONT_SIZE_TITLE)
            if fig_population:
                _add_text(doc, f"Population: {fig_population}",
                          size=_FONT_SIZE_FOOTNOTE, color=RGBColor(100, 100, 100))
            if endpoint:
                _add_text(doc, f"Endpoint: {endpoint}",
                          size=_FONT_SIZE_FOOTNOTE, color=RGBColor(100, 100, 100))

            _add_rule(doc)
            doc.add_paragraph("")

            if "km" in fig_type.lower():
                placeholder = "[Kaplan-Meier survival curve — to be generated by statistical programming]"
            elif "forest" in fig_type.lower():
                placeholder = "[Forest plot — to be generated by statistical programming]"
            elif "waterfall" in fig_type.lower():
                placeholder = "[Waterfall plot — to be generated by statistical programming]"
            elif "swimmer" in fig_type.lower():
                placeholder = "[Swimmer plot — to be generated by statistical programming]"
            else:
                placeholder = "[Figure — to be generated by statistical programming]"

            _add_text(doc, placeholder, italic=True,
                      align=WD_ALIGN_PARAGRAPH.CENTER, size=_FONT_SIZE_BODY)

            _add_rule(doc)

            fig_num_str = str(fig_number).replace("Figure ", "").replace(".", "_")
            doc.add_paragraph("")
            fp = doc.add_paragraph()
            run = fp.add_run(
                f"Program: f_{fig_num_str}.sas        Date: DDMONYYYY"
            )
            run.font.name = _FONT
            run.font.size = Pt(_FONT_SIZE_FOOTNOTE)
            run.font.color.rgb = RGBColor(100, 100, 100)

    # =================================================================
    # LISTINGS — Word table format (landscape, auto-fit columns)
    # =================================================================
    if listings:
        for lst_idx, lst in enumerate(listings):
            # Each listing gets its own landscape section
            _add_landscape_section(doc)

            lst_number = lst.get("number", "")
            lst_title = lst.get("title", "")
            lst_population = lst.get("population", "Safety")
            lst_source = lst.get("source", "")
            lst_sort_order = lst.get("sort_order", "")
            lst_page_break = lst.get("page_break_by", "")
            lst_footnotes = lst.get("footnotes", [])
            lst_prog_notes = lst.get("programming_notes", "")
            variables = lst.get(
                "variables",
                ["Subject ID", "Treatment", "Parameter", "Value"],
            )

            num_vars = len(variables)

            # Title (page header comes from the Word section header automatically)
            # Fix 5.7: Use keep_with_next to prevent orphaned titles
            pop_suffix = ""
            if lst_population and lst_population.lower() not in lst_title.lower():
                pop_suffix = f"  ({lst_population} Population)"
            _add_text(doc, f"{lst_number}", bold=True, size=_FONT_SIZE_BODY, keep_with_next=True)
            _add_text(doc, f"{lst_title}{pop_suffix}", bold=True, size=_FONT_SIZE_BODY, keep_with_next=True)

            # Word table: header row + 1 sample data row
            tbl = doc.add_table(rows=2, cols=num_vars)
            tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
            tbl.autofit = False  # Disable autofit to use explicit widths
            _set_borders_horiz_only(tbl)

            # Calculate content-aware column widths for listing
            # Listings are landscape = 9.5" usable width
            sample_data = [["xxx"] * num_vars]  # Sample data row
            lst_col_widths = _calculate_column_widths(variables, sample_data, 9.5)
            _set_table_column_widths(tbl, lst_col_widths)

            # Header row
            for c_idx, var_name in enumerate(variables):
                _set_cell(tbl.rows[0].cells[c_idx], var_name, bold=True,
                          size=_FONT_SIZE_BODY)
            _add_bottom_border_to_row(tbl.rows[0])

            # Fix 5.3: Set header row to repeat on each page
            _set_header_row_repeat(tbl)

            # Sample data row
            for c_idx in range(num_vars):
                _set_cell(tbl.rows[1].cells[c_idx], "xxx", size=_FONT_SIZE_BODY)

            # Sort order / page break
            if lst_sort_order:
                _add_text(doc, f"Sort Order: {lst_sort_order}", size=_FONT_SIZE_FOOTNOTE)
            if lst_page_break:
                _add_text(doc, f"Page Break By: {lst_page_break}", size=_FONT_SIZE_FOOTNOTE)

            # Footnotes
            if lst_footnotes:
                for i, fn in enumerate(lst_footnotes, 1):
                    _add_text(doc, f"[{i}] {fn}", size=_FONT_SIZE_FOOTNOTE)

            # Programming notes
            if lst_prog_notes:
                _add_text(doc, f"Programming Notes: {lst_prog_notes}",
                          size=_FONT_SIZE_FOOTNOTE, color=RGBColor(100, 100, 100))

            # Source line
            lst_num_str = str(lst_number).replace("Listing ", "").replace(".", "_")
            _add_text(doc, "", size=_FONT_SIZE_FOOTNOTE)
            _add_text(doc,
                      f"Source: {lst_source}        "
                      f"Program: l_{lst_num_str}.sas        "
                      f"Date: DDMONYYYY",
                      size=_FONT_SIZE_FOOTNOTE, color=RGBColor(100, 100, 100))

    # =================================================================
    # SUMMARY PAGE
    # =================================================================
    _add_portrait_section(doc)

    _add_text(doc, "TLF Shell Summary", bold=True, size=12)
    doc.add_paragraph("")

    section_counts: dict[str, int] = {}
    for t in tables:
        sec = t.get("section", "14.3")
        cat = {"14.1": "Disposition & Demographics", "14.2": "Efficacy", "14.3": "Safety"}.get(sec, sec)
        section_counts[cat] = section_counts.get(cat, 0) + 1

    num_summary_rows = 1 + len(section_counts) + 3
    summary_tbl = doc.add_table(rows=num_summary_rows, cols=2)
    summary_tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    _set_borders_horiz_only(summary_tbl)

    _set_cell(summary_tbl.rows[0].cells[0], "Category", bold=True, size=_FONT_SIZE_HEADER)
    _set_cell(summary_tbl.rows[0].cells[1], "Count", bold=True, size=_FONT_SIZE_HEADER)
    _add_bottom_border_to_row(summary_tbl.rows[0])

    row_idx = 1
    for cat, count in sorted(section_counts.items()):
        _set_cell(summary_tbl.rows[row_idx].cells[0], cat)
        _set_cell(summary_tbl.rows[row_idx].cells[1], str(count))
        row_idx += 1

    _set_cell(summary_tbl.rows[row_idx].cells[0], "Figures")
    _set_cell(summary_tbl.rows[row_idx].cells[1], str(len(figures)))
    row_idx += 1
    _set_cell(summary_tbl.rows[row_idx].cells[0], "Listings")
    _set_cell(summary_tbl.rows[row_idx].cells[1], str(len(listings)))

    total_row = summary_tbl.add_row()
    _set_cell(total_row.cells[0], "Total TLFs", bold=True)
    _set_cell(total_row.cells[1], str(len(tables) + len(figures) + len(listings)), bold=True)
    _add_bottom_border_to_row(total_row)

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()
