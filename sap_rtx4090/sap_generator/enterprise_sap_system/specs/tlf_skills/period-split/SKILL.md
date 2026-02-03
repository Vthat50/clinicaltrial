---
name: Period-Split Safety
ich_section: "14.3"
display_order: 17
version: "2.0.0"
---

# Period-Split Safety

Only included when the study has more than one treatment period (e.g., Induction + Maintenance, Treatment + Extension, Open-label + Double-blind). All tables use Safety population.

For each treatment period, generate a full set of safety tables filtered to events occurring within that period. The tables below are repeated per period.

## What Comes from the Protocol

- **Period names**: e.g., "Induction", "Maintenance", "Open-Label Extension"
- **Period definitions**: start and end dates for each period (e.g., Week 0 to Week 24, Week 24 to Week 52)
- **Period variable**: APERIOD or APHASE in ADaM datasets
- **Treatment changes**: whether treatment assignment changes across periods (e.g., re-randomization)
- **Population changes**: whether the Safety population is redefined for each period

## Column Structure

- **Two-arm with total**: {Arm 1} | {Arm 2} | Total (per period)
- Arm names from `facts.arm_names[]`; may differ per period if re-randomized.

---

## Table: Overview of TEAEs — {Period Name} Period

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADAE |
| Orientation | PORTRAIT |
| Filter | APERIOD = {period number} or APHASE = '{Period Name}' |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Subjects with at least one: | header | | 0 | |
| TEAE | data | count_pct | 1 | Events within period window |
| Grade ≥3 TEAE | data | count_pct | 1 | |
| Serious TEAE | data | count_pct | 1 | |
| Treatment-related TEAE | data | count_pct | 1 | |
| TEAE leading to study drug discontinuation | data | count_pct | 1 | |
| TEAE leading to dose modification | data | count_pct | 1 | |
| TEAE leading to death | data | count_pct | 1 | |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|-------------|---------|
| count_pct | xxx (xx.x) | 156 (63.7) |

### Calculation Methods

- **Period filter**: Events with onset within the defined period window (APERIOD or APHASE)
- **Denominator**: N = subjects entering the period (may differ from overall Safety N)
- **TEAE definition**: Same as overall TEAE definition, restricted to period window
- **Subject counted once**: Per category within the period
- **SAS**: Same as overall AE overview, with period filter applied

### Footnotes

1. Safety Population.
2. {Period Name} period: {definition from protocol, e.g., Week 0 to Week 24}.
3. Treatment-emergent: onset on or after first dose within the period through end of period.
4. A subject is counted once in each applicable category.

---

## Table: TEAEs by SOC and PT — {Period Name} Period

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADAE |
| Orientation | LANDSCAPE |
| Filter | APERIOD = {period number} |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| System Organ Class | header | | 0 | Dynamic |
| Preferred Term | data | count_pct | 1 | Dynamic |

### Calculation Methods

- Same as overall TEAEs by SOC and PT, with period filter applied

### Footnotes

1. Safety Population.
2. {Period Name} period.
3. Adverse events coded using MedDRA version XX.X.
4. A subject is counted once in each applicable category.
5. Sorted by decreasing frequency of total column within SOC.

---

## Table: Serious TEAEs — {Period Name} Period

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADAE |
| Orientation | LANDSCAPE |
| Filter | APERIOD = {period number} AND AESER = 'Y' |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| System Organ Class | header | | 0 | Dynamic |
| Preferred Term | data | count_pct | 1 | Dynamic |

### Footnotes

1. Safety Population.
2. {Period Name} period.
3. Serious: meeting ICH E2A seriousness criteria.

---

## Table: Concomitant Medications — {Period Name} Period

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADCM |
| Orientation | LANDSCAPE |
| Filter | Medications overlapping with {Period Name} period |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Subjects with at least one concomitant medication, n (%) | data | count_pct | 0 | **Bold** |
| | spacer | | 0 | |
| ATC Class | header | | 0 | Dynamic |
| Generic Drug Name | data | count_pct | 1 | Dynamic |

### Footnotes

1. Safety Population.
2. {Period Name} period.
3. Medications coded using WHO Drug Dictionary.

---

## Table: Study Drug Exposure — {Period Name} Period

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADEX |
| Orientation | PORTRAIT |
| Filter | Exposure within {Period Name} period |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Duration of Exposure (weeks) | header | | 0 | |
| n | data | count | 1 | |
| Mean (SD) | data | mean_sd | 1 | |
| Median | data | median | 1 | |
| Min, Max | data | min_max | 1 | |
| | spacer | | 0 | |
| Number of Doses/Cycles | header | | 0 | |
| n | data | count | 1 | |
| Mean (SD) | data | mean_sd | 1 | |
| Median | data | median | 1 | |
| Min, Max | data | min_max | 1 | |

### Calculation Methods

- **Duration**: (Last dose date in period − First dose date in period + 1) / 7 weeks
- **Doses/cycles**: Count within the period window only

### Footnotes

1. Safety Population.
2. {Period Name} period.
3. Duration of exposure = last dose date in period minus first dose date in period + 1 day.

---

## Table: TEAEs with Incidence ≥5% — {Period Name} Period

Condition: For biosimilar/equivalence studies.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADAE |
| Orientation | LANDSCAPE |
| Filter | APERIOD = {period number} |
| Threshold | ≥5% in any group |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Preferred Term | data | count_pct | 0 | Sorted by decreasing frequency |

### Footnotes

1. Safety Population.
2. {Period Name} period.
3. Only TEAEs with incidence ≥5% in at least one treatment group are shown.
4. Sorted by decreasing frequency.

---

## Table: TEAEs Grade ≥3 by SOC and PT — {Period Name} Period

Condition: For biosimilar/equivalence studies.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADAE |
| Orientation | LANDSCAPE |
| Filter | APERIOD = {period number} AND AETOXGR >= 3 |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| System Organ Class | header | | 0 | Dynamic |
| Preferred Term | data | count_pct | 1 | Dynamic |

### Footnotes

1. Safety Population.
2. {Period Name} period.
3. Severity graded per NCI CTCAE version 5.0.
