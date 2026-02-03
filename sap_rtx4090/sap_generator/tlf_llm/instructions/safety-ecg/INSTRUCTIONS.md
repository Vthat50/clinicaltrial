---
name: Safety - ECG
ich_section: "14.3"
display_order: 9
types: [ecg]
condition: has_ecg
---

You are generating the electrocardiogram (ECG) table shells for ICH E3 Section 14.3.

This domain only runs when the protocol includes ECG assessments.

## What to Look For in the Protocol

Search the protocol for ECG information. Check the schedule of assessments, safety assessments section, ECG or cardiac assessment section, appendices, inclusion/exclusion criteria, and stopping rules or dose modification criteria. If ECG details are not clearly listed in these locations, search the entire protocol for any mention of electrocardiogram assessments.

Identify:
- Whether ECGs are collected, and if so: standard 12-lead, Holter, central reading
- QT/QTc correction method mentioned in the protocol
- Whether categorical thresholds are defined for ECG intervals (absolute values and change from baseline)
- ECG assessment schedule and timing relative to dosing
- Whether ECG is a safety endpoint or part of a thorough QT study
- Whether any ECG parameter has protocol-defined stopping rules or monitoring thresholds
- ALL ECG intervals measured (HR, PR, QRS, QT, QTc at minimum for standard 12-lead)

List every ECG parameter and threshold you find in your `extracted_facts`. This list drives downstream validation — if a parameter is not listed there, it will be missed.

## ECG Tables

- **ECG Summary by Visit**: Change from baseline in ECG intervals. Summary statistics by visit. This is the primary ECG table — it must include a section for every ECG interval measured.
- **ECG Categorical Analysis**: QTc prolongation categories (absolute values and change-from-baseline categories) as defined in the protocol or per regulatory guidance. Generate this table for every study that collects ECGs.
- **ECG Outlier Analysis**: If the protocol specifies outlier criteria for any ECG interval, generate a separate table.
- **ECG Shift Table**: Shift from baseline category to worst post-baseline category for ECG intervals.

## Categorical Thresholds

ECG categorical analysis tables must include both absolute value categories and change-from-baseline categories. If the protocol does not define specific thresholds, use standard regulatory thresholds. The source of thresholds (protocol-defined or regulatory standard) must be stated in the footnotes.

## Baseline Definition

ECG baseline is the last assessment prior to the first dose of study drug unless the protocol defines a different rule. The baseline definition must appear in the footnotes of every ECG table.

## CRITICAL: Every ECG Parameter Gets Included

Include a section for EVERY ECG interval measured in the protocol. Do not select a subset — include all of them. The summary table must have a row section for each interval. The categorical and shift tables must cover each interval with defined thresholds.

Before finalizing, count: list every ECG parameter you found, then verify your summary table has a section for each one. If any parameter is missing, add it.

Missing an ECG parameter is a critical gap — it is always better to include a parameter than to skip one.

## CRITICAL: Multiple Treatment Periods

If the protocol has multiple distinct treatment periods, generate SEPARATE ECG summary and shift tables for EACH period in addition to the overall tables.

## Design-Type Guidance

Design type affects column structure:
- Randomized: columns per treatment arm + total
- Single-arm: overall column only
- Crossover: generate separate tables per period; use period-specific baselines for shift tables
- Dose-escalation: group by dose/cohort

## Population

All ECG tables use the **Safety** population.

## Output Format — Full Shell Specification

Each table must include complete columns, rows, footnotes, source, and orientation. See the system prompt for the full JSON schema.

**Row guidance for ECG summary (use descriptive column template — no Total column):**
- Header: "[ECG Interval]" (bold) for each interval measured → sub-rows: n (count), Mean (mean), SD (sd), Median (median), Min (min), Max (max), Change from Baseline Mean (mean), Change from Baseline SD (sd)
- Include a section for EVERY ECG interval collected in the protocol. Do not select a subset — include all of them.
- Spacer
- Header: "QTc Categories" (bold) → sub-rows: one row per categorical threshold defined in the protocol or per regulatory guidance (count_pct)

**Row guidance for ECG shift tables (use shift column template):**
- Header: "[ECG Interval]" (bold) → sub-rows: one row per baseline-to-post-baseline category transition (count_pct, indent=1)

**Footnotes must include:** Safety population definition, baseline definition, QTc correction method, categorical threshold source (protocol-defined or regulatory standard).

Types: "ecg".
Source: ADEG. Section: "14.3". Orientation: PORTRAIT (summary), LANDSCAPE (shift/categorical tables).
