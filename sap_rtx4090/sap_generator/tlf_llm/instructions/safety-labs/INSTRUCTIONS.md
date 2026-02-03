---
name: Safety - Laboratory Parameters
ich_section: "14.3"
display_order: 7
types: [labs_summary, labs_shift]
condition: always
---

You are generating the laboratory parameter table shells for ICH E3 Section 14.3.

## What to Look For in the Protocol

Search the protocol for lab panel information. Check the schedule of assessments, safety assessments section, laboratory procedures section, appendices, inclusion/exclusion criteria, and stopping rules or dose modification criteria. If lab panels are not clearly listed in these locations, search the entire protocol for any mention of laboratory assessments.

Identify:
- EVERY distinct lab panel collected for ongoing safety monitoring (each panel named in the protocol is a separate panel, regardless of how few parameters it contains) — include every one the protocol mentions.
- Specific lab parameters mentioned as safety endpoints or requiring special monitoring
- Whether a toxicity grading scale is referenced for lab parameters
- Whether any lab parameter has protocol-defined stopping rules
- Hepatic monitoring requirements (liver function parameters)

Labs collected only at screening or baseline to determine eligibility are not safety monitoring panels — do not generate summary or shift tables for them. Only generate summary and shift tables for panels that are collected repeatedly during the treatment period for ongoing safety monitoring. Check the schedule of assessments, the laboratory assessments section, or any text describing collection frequency to determine which panels are collected repeatedly.

If the protocol groups multiple sub-categories under a single panel name, treat them as one panel. If the protocol lists them as separate panels, treat them as separate panels. Follow the protocol's own grouping.

List every lab panel you find in the `"lab_panels"` key of your `extracted_facts`. This list drives downstream validation — if a panel is not listed there, it will be missed.

## Lab Tables

Generate SEPARATE tables for EACH lab panel collected. For each panel, generate BOTH a summary table AND a shift table:

- **[Panel] Summary**: Change from baseline by visit with descriptive statistics. One table per panel.
- **[Panel] Shift Table**: Shift from baseline category to worst post-baseline category. One table per panel.
- **Potentially Clinically Significant Lab Abnormalities**: Generate this table for every study. Use PCS criteria from the protocol if defined, otherwise use standard regulatory criteria. One combined table covering all lab panels.
- **Hepatic Function (Hy's Law Analysis)**: Include for any study that monitors liver function parameters. Generate the evaluation table.
- **Special Monitoring Parameters**: If the protocol lists specific parameters requiring focused monitoring, generate a dedicated summary table.

## CRITICAL: Every Lab Panel Gets Its Own Tables

Generate a SEPARATE summary table AND a SEPARATE shift table for EVERY lab panel the protocol collects. The number of lab tables must equal at least twice the number of panels (one summary + one shift per panel), plus additional tables for PCS abnormalities and hepatic function as applicable. Do NOT generate tables for only one panel and stop. If specific lab panels are NOT identified in the protocol but labs are mentioned as collected, generate summary and shift tables for each panel that is standard for the therapeutic area.

Before finalizing, count: list every panel you found in extracted_facts, then verify you have both a summary table AND a shift table for each one. If any panel is missing either table, add it.

Missing a lab panel is a critical gap — it is always better to include a panel than to skip one.

## CRITICAL: Multiple Treatment Periods

If the protocol has multiple distinct treatment periods, generate SEPARATE lab summary and shift tables for EACH period in addition to the overall tables.

## Design-Type Guidance

Design type affects column structure:
- Randomized: columns per treatment arm + total
- Single-arm: overall column only
- Crossover: generate separate tables per period; use period-specific baselines for shift tables
- Dose-escalation: group by dose/cohort

## Population

All lab tables use the **Safety** population.

## Baseline Definition

Lab baseline is the last non-missing value prior to the first dose of study drug unless the protocol defines a different rule. The baseline definition must appear in the footnotes of every lab summary and shift table.

## Shift Table Denominator

The denominator for each cell in a shift table is the number of subjects who have both a baseline value and at least one post-baseline value for that parameter. This denominator must be stated in the footnotes.

## Output Format — Full Shell Specification

Each table must include complete columns, rows, footnotes, source, and orientation. See the system prompt for the full JSON schema.

**Row guidance for lab summary tables (use descriptive column template — no Total column):**
- Header: "[Lab Parameter Name]" (bold) → sub-rows: n (count), Mean (mean), SD (sd), Median (median), Min (min), Max (max), Change from Baseline Mean (mean), Change from Baseline SD (sd)
- Include a section for EVERY lab parameter listed under that panel in the protocol. Do not select a subset — include all of them.

**Row guidance for lab shift tables (use shift column template):**
- Check if the protocol references a toxicity grading scale for lab parameters. If it does, generate TWO types of shift tables per panel: one using standard reference range categories (Normal/Low/High) AND one using the toxicity grade categories from the protocol. These are SEPARATE tables with different titles.
- If the protocol does NOT reference any toxicity grading scale, generate only the standard reference range shift table (Normal/Low/High).
- Header: "[Lab Parameter Name]" (bold) → sub-rows: one row per baseline-to-post-baseline category transition (count_pct, indent=1)

Types: "labs_summary", "labs_shift".
Source: ADLB. Section: "14.3". Orientation: PORTRAIT (summary), LANDSCAPE (shift tables).
