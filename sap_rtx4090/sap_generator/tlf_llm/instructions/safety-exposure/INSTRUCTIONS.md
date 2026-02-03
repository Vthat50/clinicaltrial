---
name: Safety - Exposure
ich_section: "14.3"
display_order: 6
types: [exposure, concomitant_medications]
condition: always
---

You are generating the study drug exposure and concomitant medication table shells for ICH E3 Section 14.3.

## What to Look For in the Protocol

Read the protocol to identify:
- Study drug dosing regimen (fixed dose, weight-based, titrated)
- Whether dose modifications (reductions, interruptions, delays) are allowed
- Duration of treatment planned
- Number of cycles or infusions planned (if applicable)
- Whether treatment compliance/adherence is measured
- Whether concomitant medications are recorded
- Whether prior medications at baseline are recorded
- Rescue/salvage therapy defined in the protocol
- Backbone/background therapy (if add-on design)

## Duration Summary

Exposure duration must be summarized both as a continuous variable and as categorical duration bands derived from the planned treatment duration in the protocol.

## Mandatory Tables

- **Study Drug Exposure**: Duration of exposure (mean, median, range), total dose received, number of doses/cycles. By treatment arm. If the study involves combination therapy with multiple drugs, generate a SEPARATE exposure table for EACH drug component.
- **Concomitant Medications**: Summary by ATC class or medication category. By treatment arm.

## Conditional Tables

- **Dose Modifications Summary**: Include if protocol allows dose reductions, interruptions, or delays. Summarize frequency and reasons.
- **Treatment Compliance/Adherence**: Include if compliance is measured.
- **Prior Medications**: Include if prior medication use at baseline is collected and relevant to the study.
- **Rescue Medication Use**: Include if rescue/salvage therapy is defined in the protocol.
- **Backbone Therapy Exposure**: Include if the study is add-on design with background therapy.

## Design-Type Guidance

Design type affects column structure:
- Randomized: columns per treatment arm + total
- Single-arm: overall column only
- Crossover: generate separate tables per period; use period-specific baselines for shift tables
- Dose-escalation: group by dose/cohort

## Population

Exposure tables use the **Safety** population.

## Output Format — Full Shell Specification

Each table must include complete columns, rows, footnotes, source, and orientation. See the system prompt for the full JSON schema.

**Row guidance for exposure tables:**
- Header: "Duration of Exposure (weeks)" (bold) → sub-rows: n, Mean (mean), SD (sd), Median (median), Min (min), Max (max)
- Spacer
- Header: "Duration Category, n (%)" (bold) → sub-rows: duration categories (count_pct, indent=1)
- Spacer
- Header: "Total Dose" (bold) → sub-rows: n, Mean, SD, Median, Min, Max
- Header: "Number of Cycles/Infusions" (bold) → if applicable

**Row guidance for concomitant medication tables:**
- Header: "[ATC Class]" (bold, indent=0)
- Data: "[Medication Name]" (count_pct, indent=1)

Types: "exposure" for drug exposure, "concomitant_medications" for medication tables.
Source: ADEX (exposure), ADCM (medications). Section: "14.3". Orientation: PORTRAIT (exposure), LANDSCAPE (medications).
