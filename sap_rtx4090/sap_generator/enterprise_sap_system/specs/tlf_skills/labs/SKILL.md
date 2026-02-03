---
name: Labs
ich_section: "14.3"
display_order: 6
version: "2.0.0"
---

# Labs

All tables use Safety population. Only included when laboratory assessments are collected.

## What Comes from the Protocol

- **Lab panels collected**: Hematology, Clinical Chemistry, Urinalysis, Coagulation, Thyroid
- **Central or local lab**: determines normal ranges source
- **CTCAE grading**: whether CTCAE toxicity grades are applied to lab parameters
- **Liver function monitoring**: whether Hy's Law evaluation is required
- **Special parameters**: any protocol-specific lab parameters of interest

## Column Structure

- **Two-arm**: {Arm 1} | {Arm 2} (for summary by visit)
- **Two-arm with total**: {Arm 1} | {Arm 2} | Total (for shift tables)
- **Shift table columns**: Baseline Category rows × Post-baseline Category columns per arm

---

## Table: Laboratory Parameters - Summary Statistics by Visit

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADLB |
| Orientation | LANDSCAPE |
| Filter | SAFFL = 'Y' |

### Rows

Repeat per parameter (Hematology: Hemoglobin, Hematocrit, WBC, Platelets, Neutrophils, Lymphocytes; Chemistry: ALT, AST, Total Bilirubin, ALP, Creatinine, BUN, Glucose, Albumin, Sodium, Potassium):

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| {Parameter} ({Unit}) | header | | 0 | Dynamic; one block per lab parameter |
| n | data | count | 1 | Subjects with non-missing result at visit |
| Mean (SD) | data | mean_sd | 1 | |
| Median | data | median | 1 | |
| Min, Max | data | min_max | 1 | |
| Change from Baseline: Mean (SD) | data | mean_sd | 1 | AVAL − BASE |
| Change from Baseline: Median | data | median | 1 | |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|------------|---------|
| mean_sd | xx.x (xx.xx) | 13.2 (1.85) |
| min_max | xx.x-xx.x | 8.1-18.4 |

### Calculation Methods

- **Descriptive**: PROC MEANS / PROC UNIVARIATE by AVISIT and treatment
- **Baseline**: Last non-missing value prior to first dose (ABLFL = 'Y')
- **Change from baseline**: AVAL − BASE (CHG variable in ADLB)
- **Units**: SI units throughout
- **Visits**: Summarized by scheduled analysis visit (AVISIT)

### Footnotes

1. Safety Population.
2. Laboratory values summarized by scheduled analysis visit.
3. Change from baseline = post-baseline value minus baseline value.
4. Baseline defined by ABLFL = 'Y'.
5. SI units used throughout.

---

## Table: Laboratory Parameters - Shift Table

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADLB |
| Orientation | LANDSCAPE |
| Filter | SAFFL = 'Y' |

### Structure

This is a cross-tabulation, NOT a simple row table. For each parameter, the table has:
- **Row dimension**: Baseline category (Normal, Low, High)
- **Column dimension**: Post-baseline worst category (Normal, Low, High) — nested within treatment arms

### Rows

Repeat per parameter:

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| {Parameter} ({Unit}) | header | | 0 | Dynamic; one block per lab parameter |
| Baseline Category | subheader | | 1 | |
| Normal | data | count | 2 | Count of subjects with baseline Normal AND worst post-baseline = {column category} |
| Low | data | count | 2 | Count of subjects with baseline Low AND worst post-baseline = {column category} |
| High | data | count | 2 | Count of subjects with baseline High AND worst post-baseline = {column category} |

### Column Structure (shift_table)

| Baseline Category | {Arm 1} Normal | {Arm 1} Low | {Arm 1} High | {Arm 2} Normal | {Arm 2} Low | {Arm 2} High | Total Normal | Total Low | Total High |

### Calculation Methods

- **Baseline category**: From BNRIND (baseline normal range indicator) — Normal, Low, High
- **Post-baseline category**: Worst post-baseline ANRIND per subject per parameter
- **Normal ranges**: Per central laboratory reference ranges
- **Cross-tabulation**: PROC FREQ with baseline × post-baseline categories
- **Each cell**: Count of subjects in that (baseline → post-baseline) combination

### Footnotes

1. Safety Population.
2. Baseline: last non-missing value prior to first dose.
3. Post-baseline: worst post-baseline value.
4. Normal ranges per central laboratory.

---

## Table: Liver Function Tests (Hy's Law Evaluation)

Condition: Only if liver function is assessed.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADLB |
| Orientation | PORTRAIT |
| Filter | SAFFL = 'Y' AND PARAMCD in ('ALT', 'AST', 'BILI') |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| ALT or AST ≥3x ULN, n (%) | data | count_pct | 0 | Max post-baseline ALT or AST ≥ 3 × ANRHI |
| ALT or AST ≥5x ULN, n (%) | data | count_pct | 0 | |
| ALT or AST ≥10x ULN, n (%) | data | count_pct | 0 | |
| ALT or AST ≥20x ULN, n (%) | data | count_pct | 0 | |
| | spacer | | 0 | |
| Total Bilirubin ≥2x ULN, n (%) | data | count_pct | 0 | |
| | spacer | | 0 | |
| Hy's Law Cases | header | | 0 | |
| ALT or AST ≥3x ULN AND Total Bilirubin ≥2x ULN, n (%) | data | count_pct | 1 | Concurrent elevations |

### Calculation Methods

- **ULN**: Upper Limit of Normal per central laboratory (ANRHI)
- **Multiples of ULN**: AVAL / ANRHI for each parameter
- **ALT or AST**: Maximum post-baseline value across ALT and AST
- **Hy's Law**: ALT or AST ≥3× ULN with concurrent (same visit or within window) total bilirubin ≥2× ULN, excluding subjects with ALP ≥2× ULN (cholestatic cause)
- **Subject counted once**: Using maximum post-baseline value per subject

### Footnotes

1. Safety Population.
2. ULN = Upper Limit of Normal per central laboratory.
3. Hy's Law: ALT or AST ≥3x ULN with concurrent total bilirubin ≥2x ULN.

---

## Table: Laboratory Parameters - CTCAE Grade Summary

Condition: Only if CTCAE grading is applied to labs.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADLB |
| Orientation | LANDSCAPE |
| Filter | SAFFL = 'Y' |

### Rows

Repeat per parameter:

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| {Parameter} | header | | 0 | |
| Grade 0 (Normal), n (%) | data | count_pct | 1 | ATOXGR = 0 or missing |
| Grade 1, n (%) | data | count_pct | 1 | |
| Grade 2, n (%) | data | count_pct | 1 | |
| Grade 3, n (%) | data | count_pct | 1 | |
| Grade 4, n (%) | data | count_pct | 1 | |

### Calculation Methods

- **CTCAE grade**: Maximum post-baseline CTCAE grade per subject per parameter
- **Grading**: Per NCI CTCAE version 5.0 criteria
- **ATOXGR variable**: Analysis toxicity grade from ADLB
- **Subject counted once**: Using worst (maximum) post-baseline grade

### Footnotes

1. Safety Population.
2. Maximum post-baseline CTCAE grade per subject per parameter.
3. Graded per NCI CTCAE version 5.0.
