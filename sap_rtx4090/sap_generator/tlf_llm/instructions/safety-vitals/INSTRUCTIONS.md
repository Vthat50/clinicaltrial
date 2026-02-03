---
name: Safety - Vital Signs & Physical Examination
ich_section: "14.3"
display_order: 8
types: [vitals, physical_exam]
condition: always
---

You are generating the vital signs and physical examination table shells for ICH E3 Section 14.3.

## What to Look For in the Protocol

Search the protocol for vital signs information. Check the schedule of assessments, safety assessments section, physical examination section, vital signs section, appendices, inclusion/exclusion criteria, and stopping rules or dose modification criteria. If vital sign parameters are not clearly listed in these locations, search the entire protocol for any mention of vital signs assessments.

Identify:
- EVERY vital sign parameter collected (each parameter is a separate row section in the summary table, regardless of how routine it may seem)
- Whether orthostatic blood pressure and pulse are assessed
- Whether any vital sign parameter has protocol-defined stopping rules or monitoring thresholds
- Potentially clinically significant (PCS) criteria for vital signs, whether defined in the protocol or per standard regulatory criteria
- Physical examination assessment schedule and whether findings are quantifiable
- Whether vital signs are collected at specific timepoints relative to dosing (pre-dose, post-dose)
- Whether height and weight are collected

List every vital sign parameter you find in your `extracted_facts`. This list drives downstream validation — if a parameter is not listed there, it will be missed.

## Vital Signs Tables

- **Vital Signs Summary by Visit**: Change from baseline by visit for EACH vital parameter collected in the protocol. This is the primary vital signs table — it must include a section for every parameter.
- **Vital Signs Shift Table**: Shift from baseline category (normal/abnormal or normal/low/high) to post-baseline worst for each parameter.
- **Potentially Clinically Significant Vital Sign Abnormalities**: Subjects meeting PCS criteria for each parameter. Generate this table for every study that collects vital signs. Use PCS criteria from the protocol if defined, otherwise use standard regulatory criteria.
- **Orthostatic Assessment**: Include if orthostatic BP/pulse is measured. Summary of orthostatic changes by visit.
- **Special Monitoring Vital Signs**: If the protocol specifies monitoring vital signs at specific timepoints relative to dosing, generate a separate summary table for those assessments.

## CRITICAL: Every Vital Parameter Gets Included

Include a section for EVERY vital sign parameter collected in the protocol. Do not select a subset — include all of them. The summary table must have a row section for each parameter. The shift table must have a row section for each parameter.

Before finalizing, count: list every vital sign parameter you found, then verify your summary table has a section for each one AND your shift table has a section for each one. If any parameter is missing from either table, add it.

Missing a vital sign parameter is a critical gap — it is always better to include a parameter than to skip one.

## Physical Examination

- Typically summarized narratively, not as a table. Only include a table if the protocol specifies quantifiable physical exam assessments.

## CRITICAL: Multiple Treatment Periods

If the protocol has multiple distinct treatment periods, generate SEPARATE vital signs summary and shift tables for EACH period in addition to the overall tables.

## Design-Type Guidance

Design type affects column structure:
- Randomized: columns per treatment arm + total
- Single-arm: overall column only
- Crossover: generate separate tables per period; use period-specific baselines for shift tables
- Dose-escalation: group by dose/cohort

## Baseline Definition

Vital signs baseline is the last assessment prior to the first dose of study drug unless the protocol defines a different rule. The baseline definition must appear in the footnotes of every vital signs table.

## PCS Criteria Source

Potentially clinically significant abnormality criteria must come from the protocol if defined there. If the protocol does not define PCS criteria, use standard regulatory criteria. The source of criteria must be stated in the footnotes of the PCS table.

## Population

All vital signs tables use the **Safety** population.

## Output Format — Full Shell Specification

Each table must include complete columns, rows, footnotes, source, and orientation. See the system prompt for the full JSON schema.

**Row guidance for vital signs summary (use descriptive column template — no Total column):**
- Header: "[Vital Parameter Name]" (bold) → sub-rows: n (count), Mean (mean), SD (sd), Median (median), Min (min), Max (max), Change from Baseline Mean (mean), Change from Baseline SD (sd)
- Include a section for EVERY vital parameter collected in the protocol. Do not select a subset — include all of them.

**Row guidance for vital signs shift tables (use shift column template):**
- Header: "[Vital Parameter Name]" (bold) → sub-rows: one row per baseline-to-post-baseline category transition (count_pct, indent=1)

**Footnotes must include:** Safety population definition, baseline definition, PCS criteria source (protocol-defined or standard).

Types: "vitals", "physical_exam".
Source: ADVS. Section: "14.3". Orientation: PORTRAIT (summary), LANDSCAPE (shift tables).
