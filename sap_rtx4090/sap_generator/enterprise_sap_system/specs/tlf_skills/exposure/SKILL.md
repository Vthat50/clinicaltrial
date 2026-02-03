---
name: Exposure
ich_section: "12.1"
display_order: 3
version: "2.0.0"
---

# Exposure

Always included, every study. Uses Safety population.

## What Comes from the Protocol

- **Drug name(s)**: study drug and any backbone therapies
- **Dosing regimen**: dose, frequency, route of administration
- **Planned dose**: for calculating relative dose intensity
- **Cycle length**: for cycle-based dosing (e.g., 21-day cycles)
- **Dose modification rules**: criteria for reduction, interruption, discontinuation
- **Duration unit**: weeks for most studies; days for short-duration studies

## Column Structure

- **Two-arm with total**: {Arm 1} | {Arm 2} | Total
- **Three-arm with total**: {Arm 1} | {Arm 2} | {Arm 3} | Total
- Arm names from `facts.arm_names[]`.

---

## Table: Study Drug Exposure

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADEX |
| Orientation | PORTRAIT |
| Filter | SAFFL = 'Y' |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Number of subjects treated | data | count | 0 | N per arm |
| | spacer | | 0 | |
| Duration of Treatment (weeks) | header | | 0 | |
| Mean (SD) | data | mean_sd | 1 | |
| Median | data | median | 1 | |
| Min, Max | data | min_max | 1 | |
| | spacer | | 0 | |
| Number of Doses/Cycles Received | header | | 0 | |
| Mean (SD) | data | mean_sd | 1 | |
| Median | data | median | 1 | |
| Min, Max | data | min_max | 1 | |
| | spacer | | 0 | |
| Cumulative Dose ({unit}) | header | | 0 | Unit from protocol (mg, mg/kg, etc.) |
| Mean (SD) | data | mean_sd | 1 | |
| Median | data | median | 1 | |
| | spacer | | 0 | |
| Relative Dose Intensity (%) | header | | 0 | |
| Mean (SD) | data | mean_sd | 1 | |
| Median | data | median | 1 | |
| Min, Max | data | min_max | 1 | |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|-------------|---------|
| count | xxx | 245 |
| mean_sd | xx.x (xx.xx) | 24.3 (8.67) |
| median | xx.x | 26.0 |
| min_max | xx.x-xx.x | 1.0-52.0 |

### Calculation Methods

- **Duration of treatment**: (Date of last dose − Date of first dose + 1) / 7 (in weeks)
- **Number of doses/cycles**: Count of non-missing dose records per subject in ADEX
- **Cumulative dose**: Sum of all doses administered per subject (AVAL where PARAMCD = 'CUMDOSE')
- **Relative dose intensity**: 100 × (actual cumulative dose / planned cumulative dose per protocol)
- **SAS**: PROC MEANS for descriptive statistics of exposure parameters from ADEX

### Footnotes

1. Safety Population: All subjects who received at least one dose of study treatment.
2. Relative dose intensity = 100 × (actual cumulative dose / planned cumulative dose).
