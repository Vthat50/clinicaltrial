---
name: Quality of Life / Patient-Reported Outcomes
ich_section: "14.2"
display_order: 10
types: [qol]
condition: has_qol
---

You are generating the QoL and patient-reported outcome (PRO) table and figure shells for ICH E3 Section 14.2.

This domain only runs when the protocol includes QoL/PRO instruments.

## What to Look For in the Protocol

Read the protocol THOROUGHLY to identify ALL QoL/PRO instruments:
- Generic instruments — these are SEPARATE instruments that require their own tables
- Disease-specific modules — these are SEPARATE instruments that require their own tables
- Which instruments are primary vs secondary endpoints (primary endpoints should already be covered in efficacy domains)
- Scoring methodology for each instrument (total score, subscale scores, domain scores)
- Clinically meaningful change thresholds if defined
- Responder definitions for each instrument
- Assessment schedule (which visits)

## CRITICAL: Every Instrument Gets Its Own Tables

Generate a FULL SET of tables for EACH QoL/PRO instrument found. If the protocol uses both a generic instrument AND a disease-specific module, both need separate tables.

## Tables Per Instrument

For EACH QoL/PRO instrument found in the protocol:

- **Total Score Summary**: Observed scores and change from baseline by visit. Summary statistics by treatment arm.
- **Domain/Subscale Scores**: If the instrument has subscales or domains, include a table summarizing each.
- **Responder Analysis**: If a responder threshold is defined, include a responder rate table.

## Scoring Reference

Each instrument table must state the score range and direction of improvement in the footnotes.

## Figures

- **Score Over Time**: Line plot of mean score (± SE or 95% CI) by visit for each treatment arm. One per instrument or key instrument.

## IMPORTANT: Avoid Duplication

If a QoL/PRO instrument is a primary or secondary efficacy endpoint, it may already be covered in the primary-efficacy or secondary-efficacy domains. Check "Already Generated" and do NOT duplicate. Only generate here if the instrument is NOT already covered as an efficacy endpoint.

## Design-Type Guidance

Design type affects column structure:
- Randomized: columns per treatment arm + total
- Single-arm: overall column only
- Crossover: generate separate tables per period; use period-specific baselines for shift tables
- Dose-escalation: group by dose/cohort

## Population

QoL tables typically use the **ITT/FAS** or **Enrolled** population — whichever the protocol specifies for QoL analysis.

## Output Format — Full Shell Specification

Each table must include complete columns, rows, footnotes, source, and orientation. See the system prompt for the full JSON schema.

**Row guidance for QoL summary tables:**
- Header: "Total Score" (bold)
- Sub-rows: Baseline: n, Mean, SD; Visit X: n, Mean, SD, Change from Baseline Mean, SD
- Spacer
- Header: "[Domain/Subscale Name]" (bold) → same structure per subscale

**Row guidance for responder tables:**
- Data: Responders (≥MCID improvement), n (%) (count_pct) per arm per visit
- Data: Treatment difference (diff_ci)
- Data: p-value (p_value)

Include the instrument name in the table title.

Type: "qol".
Source: ADQS. Section: "14.2". Orientation: PORTRAIT.
