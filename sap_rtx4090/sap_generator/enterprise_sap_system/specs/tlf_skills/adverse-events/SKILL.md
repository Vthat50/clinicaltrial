---
name: Adverse Events
ich_section: "14.3"
display_order: 5
version: "2.0.0"
---

# Adverse Events

Always included, every study. All tables use Safety population.

## What Comes from the Protocol

- **Safety follow-up window**: defines TEAE window (onset after first dose through last dose + X days)
- **AE coding dictionary**: MedDRA version
- **Severity grading**: NCI CTCAE version (typically 5.0) or mild/moderate/severe
- **Relatedness assessment**: investigator-assessed, categories (related, not related, or 5-point scale)
- **Frequency threshold**: for the "TEAEs with incidence ≥X%" table (typically 5% or 10%)
- **AESIs**: if protocol-defined, handled in the AESI skill

## Column Structure

- **Two-arm with total**: {Arm 1} | {Arm 2} | Total
- **Three-arm with total**: {Arm 1} | {Arm 2} | {Arm 3} | Total
- Arm names from `facts.arm_names[]`.

---

## Table: Overview of Treatment-Emergent Adverse Events

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADAE |
| Orientation | PORTRAIT |
| Population Filter | ADSL.SAFFL = 'Y' |
| Event Filter | ADAE.TRTEMFL = 'Y' |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Subjects with at least one: | header | | 0 | |
| TEAE | data | count_pct | 1 | Any TEAE |
| Grade ≥3 TEAE | data | count_pct | 1 | AETOXGR ≥ 3 |
| Grade 4 TEAE | data | count_pct | 1 | AETOXGR = 4 |
| Grade 5 TEAE (Death) | data | count_pct | 1 | AETOXGR = 5 |
| Serious TEAE | data | count_pct | 1 | AESER = 'Y' |
| Treatment-related TEAE | data | count_pct | 1 | AREL = 'Y' (or AEREL per study) |
| Treatment-related Serious TEAE | data | count_pct | 1 | AREL = 'Y' AND AESER = 'Y' |
| TEAE leading to study drug discontinuation | data | count_pct | 1 | AEACN = 'DRUG WITHDRAWN' |
| TEAE leading to dose modification | data | count_pct | 1 | AEACN in ('DOSE REDUCED', 'DRUG INTERRUPTED', 'DOSE INCREASED') |
| TEAE leading to dose interruption | data | count_pct | 1 | AEACN = 'DRUG INTERRUPTED' |
| TEAE leading to death | data | count_pct | 1 | AEOUT = 'FATAL' (distinct from Grade 5 which uses AETOXGR = '5') |
| | spacer | | 0 | |
| Maximum CTCAE Grade: | header | | 0 | |
| Grade 1 (Mild) | data | count_pct | 1 | Worst grade per subject = 1 |
| Grade 2 (Moderate) | data | count_pct | 1 | Worst grade per subject = 2 |
| Grade 3 (Severe) | data | count_pct | 1 | Worst grade per subject = 3 |
| Grade 4 (Life-threatening) | data | count_pct | 1 | Worst grade per subject = 4 |
| Grade 5 (Death) | data | count_pct | 1 | Worst grade per subject = 5 |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|-------------|---------|
| count_pct | xxx (xx.x) | 189 (77.1) |

### Calculation Methods

- **TEAE definition**: Onset on or after first dose of study drug through safety follow-up period (TRTEMFL = 'Y')
- **Subject counted once**: Per category, using worst event (highest grade, most severe action)
- **Maximum CTCAE Grade**: Mutually exclusive categories — each subject counted once at their worst grade
- **Grade 5 vs TEAE leading to death**: Grade 5 uses AETOXGR = '5'; TEAE leading to death uses AEOUT = 'FATAL'. These may differ.
- **Denominator**: N = number of subjects in Safety population per arm
- **SAS**: PROC FREQ or custom AE macro; subject-level flags derived from ADAE

### Footnotes

1. Safety Population: All subjects who received at least one dose of study treatment.
2. Treatment-emergent: onset on or after first dose of study drug through safety follow-up.
3. Adverse events coded using MedDRA version XX.X.
4. Severity graded per NCI CTCAE version 5.0.
5. A subject is counted once in each applicable category.

---

## Table: TEAEs by SOC and PT

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADAE |
| Orientation | LANDSCAPE |
| Filter | TRTEMFL = 'Y' |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| System Organ Class | header | | 0 | Dynamic: one group per SOC from data |
| Preferred Term | data | count_pct | 1 | Dynamic: PTs within each SOC, sorted by decreasing frequency |

### Calculation Methods

- **Hierarchy**: MedDRA SOC → PT
- **Sorting**: SOC by decreasing frequency of total column (or international SOC order); PT by decreasing frequency within SOC
- **Subject counted once**: Per SOC and per PT, regardless of number of events
- **Threshold**: All PTs shown unless SAP specifies a frequency threshold
- **SAS**: PROC FREQ or custom AE macro

### Footnotes

1. Safety Population.
2. Adverse events coded using MedDRA version XX.X.
3. A subject is counted once in each applicable category.
4. Sorted by decreasing frequency of total column within SOC.

---

## Table: Treatment-Related TEAEs by SOC and PT

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADAE |
| Orientation | LANDSCAPE |
| Filter | TRTEMFL = 'Y' AND AREL = 'Y' |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| System Organ Class | header | | 0 | Dynamic |
| Preferred Term | data | count_pct | 1 | Dynamic |

### Calculation Methods

- Same as TEAEs by SOC and PT, filtered to AREL = 'Y' (investigator-assessed as related)

### Footnotes

1. Safety Population.
2. Related: assessed as related by investigator (AREL = 'Y').
3. Adverse events coded using MedDRA version XX.X.
4. A subject is counted once in each applicable category.

---

## Table: TEAEs Grade ≥3 by SOC and PT

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADAE |
| Orientation | LANDSCAPE |
| Filter | TRTEMFL = 'Y' AND AETOXGR >= 3 |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| System Organ Class | header | | 0 | Dynamic |
| Preferred Term | data | count_pct | 1 | Dynamic |

### Calculation Methods

- Same as TEAEs by SOC and PT, filtered to AETOXGR ≥ 3
- Subject counted once per PT using worst (maximum) grade

### Footnotes

1. Safety Population.
2. Adverse events coded using MedDRA version XX.X.
3. Severity graded per NCI CTCAE version 5.0.

---

## Table: Serious TEAEs by SOC and PT

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADAE |
| Orientation | LANDSCAPE |
| Filter | TRTEMFL = 'Y' AND AESER = 'Y' |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| System Organ Class | header | | 0 | Dynamic |
| Preferred Term | data | count_pct | 1 | Dynamic |

### Calculation Methods

- Same as TEAEs by SOC and PT, filtered to AESER = 'Y' (meeting ICH E2A seriousness criteria)

### Footnotes

1. Safety Population.
2. Serious: meeting ICH E2A seriousness criteria.
3. Adverse events coded using MedDRA version XX.X.

---

## Table: TEAEs Leading to Discontinuation of Study Treatment

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADAE |
| Orientation | LANDSCAPE |
| Filter | TRTEMFL = 'Y' AND AEACN = 'DRUG WITHDRAWN' |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| System Organ Class | header | | 0 | Dynamic |
| Preferred Term | data | count_pct | 1 | Dynamic |

### Footnotes

1. Safety Population.
2. Adverse events coded using MedDRA version XX.X.

---

## Table: TEAEs Leading to Death

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADAE |
| Orientation | LANDSCAPE |
| Filter | TRTEMFL = 'Y' AND AEOUT = 'FATAL' |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| System Organ Class | header | | 0 | Dynamic |
| Preferred Term | data | count_pct | 1 | Dynamic |

### Footnotes

1. Safety Population.
2. Adverse events coded using MedDRA version XX.X.

---

## Table: TEAEs Leading to Dose Modification

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADAE |
| Orientation | LANDSCAPE |
| Filter | TRTEMFL = 'Y' AND AEACN in ('DOSE REDUCED', 'DRUG INTERRUPTED', 'DOSE INCREASED') |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| System Organ Class | header | | 0 | Dynamic |
| Preferred Term | data | count_pct | 1 | Dynamic |

### Footnotes

1. Safety Population.
2. Adverse events coded using MedDRA version XX.X.

---

## Table: TEAEs with Incidence ≥5% in Any Treatment Group

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADAE |
| Orientation | LANDSCAPE |
| Threshold | ≥5% in any group |
| Filter | TRTEMFL = 'Y' |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Preferred Term | data | count_pct | 0 | Sorted by decreasing frequency |

### Calculation Methods

- **Threshold**: Include PTs where incidence ≥5% in at least one treatment group (threshold may vary per SAP: 5%, 10%, etc.)
- **Sorting**: By decreasing frequency in total column
- **No SOC grouping**: Flat list by PT only

### Footnotes

1. Safety Population.
2. Only TEAEs with incidence ≥5% in at least one treatment group are shown.
3. Sorted by decreasing frequency.

---

## Table: TEAEs by SOC, PT, and Maximum Severity

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADAE |
| Orientation | LANDSCAPE |
| Filter | TRTEMFL = 'Y' |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| System Organ Class | header | | 0 | Dynamic |
| Preferred Term | data | count_pct | 1 | Dynamic; overall count for this PT |
| Grade 1 | data | count_pct | 2 | Maximum severity = Grade 1 |
| Grade 2 | data | count_pct | 2 | Maximum severity = Grade 2 |
| Grade 3 | data | count_pct | 2 | Maximum severity = Grade 3 |
| Grade 4 | data | count_pct | 2 | Maximum severity = Grade 4 |
| Grade 5 | data | count_pct | 2 | Maximum severity = Grade 5 |

### Calculation Methods

- **Maximum severity per subject per PT**: Each subject counted once at their worst grade for each PT
- **Grade categories**: Mutually exclusive per subject per PT
- **SAS**: Derive worst grade per subject × PT, then PROC FREQ

### Footnotes

1. Safety Population.
2. Maximum severity per subject per PT.
3. Adverse events coded using MedDRA version XX.X.
4. Severity graded per NCI CTCAE version 5.0.
