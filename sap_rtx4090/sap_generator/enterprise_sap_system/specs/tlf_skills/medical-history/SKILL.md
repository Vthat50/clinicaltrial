---
name: Medical History
ich_section: "14.1"
display_order: 3
version: "2.0.0"
---

# Medical History

Always included, every study. Uses Safety population.

## What Comes from the Protocol

- **Disease under study**: the primary diagnosis (excluded from medical history summary or shown separately)
- **Relevant medical conditions**: conditions that affect eligibility or stratification
- **Coding dictionary**: MedDRA version for medical history terms
- **Prior therapy definition**: therapies started before first dose

## Column Structure

- **Two-arm with total**: {Arm 1} | {Arm 2} | Total
- Arm names from `facts.arm_names[]`.

---

## Table: Medical History

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADMH |
| Orientation | LANDSCAPE |
| Filter | SAFFL = 'Y' |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Subjects with at least one medical history | data | count_pct | 0 | **Bold** |
| | spacer | | 0 | |
| System Organ Class | header | | 0 | Dynamic: one group per SOC from data |
| Preferred Term | data | count_pct | 1 | Dynamic: PTs within each SOC, sorted by decreasing frequency |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|-------------|---------|
| count_pct | xxx (xx.x) | 201 (82.0) |

### Calculation Methods

- **Coding**: MedDRA (SOC → PT hierarchy)
- **Subject counted once**: Per SOC and per PT, regardless of number of medical history entries
- **Sorting**: SOC by decreasing frequency or alphabetically; PT by decreasing frequency within SOC
- **Ongoing conditions**: Included regardless of whether ongoing at baseline
- **SAS**: PROC FREQ or custom macro; similar structure to AE by SOC/PT tables

### Footnotes

1. Safety Population.
2. Medical history coded using MedDRA version XX.X.
3. A subject is counted once in each applicable category.

---

## Table: Prior and Concomitant Therapies

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADCM |
| Orientation | LANDSCAPE |
| Filter | SAFFL = 'Y' AND (CMCAT = 'PRIOR' or start date before first dose) |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Subjects with at least one prior therapy | data | count_pct | 0 | **Bold** |
| | spacer | | 0 | |
| ATC Class | header | | 0 | Dynamic: one group per ATC class |
| Drug Name | data | count_pct | 1 | Dynamic: drugs within ATC class |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|-------------|---------|
| count_pct | xxx (xx.x) | 156 (63.7) |

### Calculation Methods

- **Prior therapy**: Start date before first dose of study drug
- **Coding**: WHO Drug Dictionary; ATC classification
- **Subject counted once**: Per ATC class and per drug name
- **SAS**: PROC FREQ; filter ADCM for prior medications

### Footnotes

1. Safety Population.
2. Prior: start date before first dose. Concomitant: overlapping with treatment period.
3. Medications coded using WHO Drug Dictionary.
