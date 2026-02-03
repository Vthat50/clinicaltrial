---
name: Pharmacokinetics
ich_section: "14.3"
display_order: 8
types: [pk_parameters, pk_concentration]
condition: has_pk
---

You are generating the pharmacokinetic (PK) table and figure shells for ICH E3 Section 14.3.

This domain only runs when the protocol includes PK sampling.

## What to Look For in the Protocol

Read the protocol to identify:
- PK sampling type (intensive, sparse, population PK)
- Analytes measured (parent drug, metabolites)
- PK parameters to be derived as specified in the protocol
- Whether PK is a primary or secondary objective
- Bioequivalence criteria if applicable (biosimilar/BE studies)
- Whether PK-PD analysis is planned
- Whether dose proportionality assessment is planned
- PK population definition

## Tables

- **PK Parameters Summary**: Summary statistics (N, mean, SD, %CV, median, min, max, geometric mean, geometric %CV) for each derived PK parameter by treatment arm. One table per analyte if multiple analytes.
- **PK Concentration Summary by Timepoint**: Mean and individual concentration data at each sampling timepoint. By treatment arm.

### Conditional PK Tables — Generate ALL That Apply

- **Bioequivalence Analysis**: Include for biosimilar/BE studies. Present geometric mean ratios with 90% CI for AUC and Cmax.
- **Dose Proportionality**: Include if dose proportionality assessment is mentioned.
- **PK-PD Analysis**: Include if PK-PD relationship analysis is described.
- **PK by Subgroup**: Include if protocol specifies PK subgroup analyses.
- **PK by ADA Status**: Include if immunogenicity is assessed alongside PK. Trough or parameter summary by ADA-positive vs ADA-negative.
- **Trough Concentration by Visit**: For studies with sparse PK sampling, include a trough concentration summary by visit.

## Figures

Generate ALL of the following for every PK study:
- **Concentration-Time Curve (Linear Scale)**: Mean ± SD concentration vs time. By treatment arm. This is a SEPARATE figure.
- **Concentration-Time Curve (Semi-Log Scale)**: Same data on semi-logarithmic y-axis. This is a SEPARATE figure — do NOT combine with the linear scale figure.
- **Individual Concentration-Time Profiles**: If the study is small (Phase 1) or intensive PK.

### Conditional Figures

- **Dose Proportionality Plot**: If dose proportionality is assessed.
- **PK-PD Scatter Plot**: If PK-PD analysis is planned.

## Separate Scale Figures

Linear-scale and semi-logarithmic-scale concentration-time curves are separate figures with different y-axis scales. Both must always be generated.

## Design-Type Guidance

Design type affects column structure:
- Randomized: columns per treatment arm + total
- Single-arm: overall column only
- Crossover: generate separate tables per period; use period-specific baselines for shift tables
- Dose-escalation: group by dose/cohort

## Population

PK tables use the **PK Evaluable** population (or PK population as defined in the protocol).

## Output Format — Full Shell Specification

Each table must include complete columns, rows, footnotes, source, and orientation. See the system prompt for the full JSON schema. Use descriptive column template (no Total column).

**Row guidance for PK parameter tables:**
- Header: "[PK Parameter Name, units]" (bold) for each parameter defined in the protocol
- Sub-rows: n (count), Arithmetic Mean (mean), SD (sd), %CV (percentage), Geometric Mean (mean), Geometric %CV (percentage), Median (median), Min (min), Max (max)

**Row guidance for PK concentration tables:**
- Header: "Timepoint" rows for each sampling time → concentration stats per arm

**For biosimilar/BE studies, include:** Geometric Mean Ratio (ratio_ci), 90% CI, within standard equivalence margins footnote.

Types: "pk_parameters", "pk_concentration".
Source: ADPP (parameters), ADPC (concentrations). Section: "14.3". Orientation: LANDSCAPE.
