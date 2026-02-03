---
name: Vital Signs
ich_section: "14.3"
display_order: 7
version: "2.0.0"
---

# Vital Signs

All tables use Safety population. Only included when vital signs are collected.

## What Comes from the Protocol

- **Parameters collected**: Systolic BP, Diastolic BP, Pulse Rate, Body Temperature, Respiratory Rate, Weight
- **Measurement schedule**: which visits vital signs are assessed
- **Markedly abnormal criteria**: protocol-defined or regulatory-guidance thresholds (e.g., SBP >180 or <90 mmHg)
- **Orthostatic measurements**: whether standing/supine measurements are collected (adds orthostatic change rows)

## Column Structure

- **Two-arm**: {Arm 1} | {Arm 2} (for summary by visit)
- **Two-arm with total**: {Arm 1} | {Arm 2} | Total (for markedly abnormal)

---

## Table: Vital Signs - Summary Statistics by Visit

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADVS |
| Orientation | LANDSCAPE |
| Filter | SAFFL = 'Y' |

### Rows

Repeat per parameter (Systolic Blood Pressure (mmHg), Diastolic Blood Pressure (mmHg), Pulse Rate (beats/min), Body Temperature (°C), Respiratory Rate (breaths/min), Weight (kg)):

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| {Parameter} ({Unit}) | header | | 0 | repeat_per: parameter |
| n | data | count | 1 | Subjects with non-missing result at visit |
| Mean (SD) | data | mean_sd | 1 | Arithmetic mean and standard deviation |
| Median | data | median | 1 | |
| Min, Max | data | min_max | 1 | |
| Change from Baseline: Mean (SD) | data | mean_sd | 1 | AVAL − BASE |
| Change from Baseline: Median | data | median | 1 | |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|------------|---------|
| mean_sd | xxx.x (xx.xx) | 128.4 (14.32) |
| median | xxx.x | 126.0 |
| min_max | xxx.x-xxx.x | 92.0-186.0 |

### Calculation Methods

- **Descriptive**: PROC MEANS by AVISIT and treatment arm
- **Baseline**: Last non-missing value on or before first dose (ABLFL = 'Y')
- **Change from baseline**: AVAL − BASE (CHG variable in ADVS)
- **Visits**: Summarized by scheduled analysis visit (AVISIT)

### Footnotes

1. Safety Population.
2. Vital signs measured at each scheduled visit.
3. Change from baseline = post-baseline value minus baseline value.
4. Baseline defined by ABLFL = 'Y'.

---

## Table: Subjects with Markedly Abnormal Vital Sign Values

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADVS |
| Orientation | PORTRAIT |
| Filter | SAFFL = 'Y' |

### Rows

Repeat per parameter:

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| {Parameter} | header | | 0 | repeat_per: parameter |
| High, n (%) | data | count_pct | 1 | Post-baseline value exceeding high threshold |
| Low, n (%) | data | count_pct | 1 | Post-baseline value below low threshold |

### Calculation Methods

- **Markedly abnormal**: Defined per protocol or regulatory guidance (e.g., SBP >180 mmHg = High)
- **Subject counted once**: Per parameter, regardless of number of abnormal values
- **Post-baseline only**: At least one post-baseline value meeting criteria
- **ANRHI/ANRLO**: Or protocol-defined thresholds in ADVS

### Footnotes

1. Safety Population.
2. Markedly abnormal criteria defined per protocol or regulatory guidance.
3. Subjects counted once per parameter regardless of number of abnormal values.
