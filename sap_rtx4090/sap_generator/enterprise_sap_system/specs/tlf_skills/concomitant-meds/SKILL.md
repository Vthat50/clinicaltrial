---
name: Concomitant Medications
ich_section: "14.3"
display_order: 4
version: "2.0.0"
---

# Concomitant Medications

Always included, every study. Uses Safety population.

## What Comes from the Protocol

- **Permitted medications**: which concomitant medications are allowed
- **Prohibited medications**: medications that constitute protocol deviations
- **Rescue/salvage therapy**: specific rescue medications and triggers for their use
- **Medication coding dictionary**: WHO Drug Dictionary version
- **Classification system**: ATC (Anatomical Therapeutic Chemical) coding level (typically Level 2 or 4)
- **Prior vs concomitant definition**: cutoff relative to first dose date

## Column Structure

- **Two-arm with total**: {Arm 1} | {Arm 2} | Total
- Arm names from `facts.arm_names[]`.

---

## Table: Concomitant Medications

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADCM |
| Orientation | LANDSCAPE |
| Filter | SAFFL = 'Y' |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Subjects with at least one concomitant medication | data | count_pct | 0 | **Bold** |
| | spacer | | 0 | |
| ATC Class | header | | 0 | Dynamic: one group per ATC class from data |
| Generic Drug Name | data | count_pct | 1 | Dynamic: drugs within each ATC class, sorted by frequency |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|-------------|---------|
| count_pct | xxx (xx.x) | 189 (77.1) |

### Calculation Methods

- **Concomitant**: Medications with start date on or after first dose, or ongoing medications that overlap with treatment period
- **Prior**: Medications with start date before first dose and end date before first dose (or missing end date with start before first dose)
- **Coding**: WHO Drug Dictionary; generic drug name (CMDECOD); ATC class (CMCLAS)
- **Subject counted once**: Per ATC class and per generic drug name
- **Sorting**: ATC class alphabetically or by frequency; drugs within ATC by decreasing frequency
- **SAS**: PROC FREQ or custom medication summary macro

### Footnotes

1. Safety Population: All subjects who received at least one dose of study treatment.
2. Medications coded using WHO Drug Dictionary.
3. Medications classified by ATC coding system.
4. A subject is counted once in each applicable category.
5. Sorted by decreasing frequency within ATC class.
