---
name: Backbone Therapy
ich_section: "14.3"
display_order: 16
version: "2.0.0"
---

# Backbone Therapy

Only included when the protocol specifies a backbone (background) therapy that all subjects receive alongside the study drug (e.g., methotrexate in rheumatoid arthritis, chemotherapy backbone in oncology). All tables use Safety population.

For each backbone drug, repeat the full set of tables below.

## What Comes from the Protocol

- **Backbone drug name(s)**: e.g., methotrexate, chemotherapy regimen (docetaxel, cisplatin)
- **Dosing regimen**: planned dose, frequency, route for the backbone
- **Dose modification rules**: protocol-defined rules for backbone dose reduction/interruption/discontinuation
- **Duration**: planned duration of backbone therapy
- **Stable dose requirement**: whether a stable dose period is required before randomization

## Column Structure

- **Two-arm with total**: {Arm 1} | {Arm 2} | Total
- Arm names from `facts.arm_names[]`.

---

## Table: Backbone Drug Exposure — {Drug Name}

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADEX |
| Orientation | LANDSCAPE |
| Filter | SAFFL = 'Y' |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Subjects treated with {Drug Name}, n (%) | data | count_pct | 0 | |
| | spacer | | 0 | |
| Duration of Exposure (weeks) | header | | 0 | |
| n | data | count | 1 | |
| Mean (SD) | data | mean_sd | 1 | |
| Median | data | median | 1 | |
| Min, Max | data | min_max | 1 | |
| | spacer | | 0 | |
| Duration Category | header | | 0 | |
| <4 weeks, n (%) | data | count_pct | 1 | |
| ≥4 to <12 weeks, n (%) | data | count_pct | 1 | |
| ≥12 to <24 weeks, n (%) | data | count_pct | 1 | |
| ≥24 weeks, n (%) | data | count_pct | 1 | |
| | spacer | | 0 | |
| Cumulative Dose ({Unit}) | header | | 0 | Unit from protocol |
| n | data | count | 1 | |
| Mean (SD) | data | mean_sd | 1 | |
| Median | data | median | 1 | |
| Min, Max | data | min_max | 1 | |
| | spacer | | 0 | |
| Relative Dose Intensity (%) | header | | 0 | |
| n | data | count | 1 | |
| Mean (SD) | data | mean_sd | 1 | |
| Median | data | median | 1 | |
| Min, Max | data | min_max | 1 | |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|-------------|---------|
| count_pct | xxx (xx.x) | 240 (98.0) |
| mean_sd | xx.x (xx.xx) | 18.7 (6.34) |
| median | xx.x | 20.0 |
| min_max | xx.x-xx.x | 1.0-36.0 |

### Calculation Methods

- **Duration of exposure**: (Date of last dose − Date of first dose + 1) / 7 (in weeks)
- **Duration categories**: Fixed bins as shown; may be adjusted per protocol duration
- **Cumulative dose**: Sum of all backbone doses per subject
- **Relative dose intensity**: 100 × (actual cumulative dose / planned cumulative dose per protocol)
- **SAS**: PROC MEANS for continuous; PROC FREQ for categorical

### Footnotes

1. Safety Population.
2. Duration of exposure = date of last dose minus date of first dose + 1 day.
3. Relative dose intensity = (actual cumulative dose / planned cumulative dose) x 100%.

---

## Table: Backbone Drug Dose Modifications — {Drug Name}

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADEX |
| Orientation | PORTRAIT |
| Filter | SAFFL = 'Y' |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Subjects with any dose modification, n (%) | data | count_pct | 0 | **Bold** |
| | spacer | | 0 | |
| Type of Modification | header | | 0 | |
| Dose reduction, n (%) | data | count_pct | 1 | EXADJ = 'DOSE REDUCED' |
| Dose interruption, n (%) | data | count_pct | 1 | EXADJ = 'DRUG INTERRUPTED' |
| Dose delay, n (%) | data | count_pct | 1 | EXADJ = 'DOSE DELAYED' |
| Discontinuation of {Drug Name}, n (%) | data | count_pct | 1 | |
| | spacer | | 0 | |
| Reason for Discontinuation | header | | 0 | |
| Adverse event, n (%) | data | count_pct | 1 | |
| Disease progression, n (%) | data | count_pct | 1 | |
| Subject decision, n (%) | data | count_pct | 1 | |
| Other, n (%) | data | count_pct | 1 | |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|-------------|---------|
| count_pct | xxx (xx.x) | 45 (18.4) |

### Calculation Methods

- **Dose modification**: Any change from planned backbone dose (reduction, interruption, delay)
- **Subject counted once**: Per modification type
- **Discontinuation reasons**: From exposure dataset or ADSL backbone-specific discontinuation variables
- **SAS**: PROC FREQ on backbone-specific exposure flags

### Footnotes

1. Safety Population.
2. A subject may have more than one type of dose modification.
3. Dose modifications per protocol-defined rules.
