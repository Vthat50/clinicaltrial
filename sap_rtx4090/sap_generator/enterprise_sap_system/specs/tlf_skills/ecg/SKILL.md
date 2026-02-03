---
name: ECG
ich_section: "14.3"
display_order: 8
version: "2.0.0"
---

# ECG

All tables use Safety population. Only included when ECG is assessed.

## What Comes from the Protocol

- **ECG collection schedule**: which visits ECGs are performed
- **ECG type**: 12-lead standard; triplicate or single
- **QT correction method**: Fridericia (QTcF), Bazett (QTcB), or study-specific
- **ICH E14 assessment**: whether thorough QT study or standard cardiac safety monitoring
- **Categorical thresholds**: absolute QTcF thresholds (450, 480, 500 msec) and change thresholds (30, 60 msec) per ICH E14
- **Central reading**: whether ECGs are read centrally or locally

## Column Structure

- **Two-arm**: {Arm 1} | {Arm 2} (for summary by visit)
- **Two-arm with total**: {Arm 1} | {Arm 2} | Total (for categorical and qualitative tables)
- Arm names from `facts.arm_names[]`.

---

## Table: ECG Parameters - Summary Statistics by Visit

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADEG |
| Orientation | LANDSCAPE |
| Filter | SAFFL = 'Y' |

### Rows

Repeat per parameter (Heart Rate (bpm), PR Interval (msec), QRS Duration (msec), QT Interval (msec), QTcF Interval (msec)):

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| {Parameter} ({Unit}) | header | | 0 | repeat_per: parameter |
| n | data | count | 1 | Subjects with non-missing result at visit |
| Mean (SD) | data | mean_sd | 1 | |
| Median | data | median | 1 | |
| Min, Max | data | min_max | 1 | |
| Change from Baseline: Mean (SD) | data | mean_sd | 1 | AVAL − BASE |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|-------------|---------|
| mean_sd | xxx.x (xx.xx) | 72.4 (11.23) |
| median | xxx.x | 71.0 |
| min_max | xxx.x-xxx.x | 48.0-112.0 |

### Calculation Methods

- **Descriptive**: PROC MEANS / PROC UNIVARIATE by AVISIT and treatment arm
- **Baseline**: Last non-missing value on or before first dose (ABLFL = 'Y')
- **Change from baseline**: AVAL − BASE (CHG variable in ADEG)
- **Triplicate ECGs**: Mean of triplicates per timepoint used as the single value
- **Visits**: Summarized by scheduled analysis visit (AVISIT)
- **QTcF**: QT corrected by Fridericia method: QTcF = QT / RR^0.33 (where RR = 60/HR)

### Footnotes

1. Safety Population.
2. ECG parameters from 12-lead ECG.
3. QTcF = QT corrected by Fridericia method (QT/RR^0.33).
4. Change from baseline = post-baseline value minus baseline value.
5. Triplicate ECGs: mean of triplicates per timepoint.

---

## Table: QTcF Categorical Analysis (ICH E14)

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADEG |
| Orientation | PORTRAIT |
| Filter | SAFFL = 'Y' AND PARAMCD = 'QTCF' |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Maximum Post-baseline QTcF (msec) | header | | 0 | |
| <450, n (%) | data | count_pct | 1 | |
| ≥450 to <480, n (%) | data | count_pct | 1 | |
| ≥480 to <500, n (%) | data | count_pct | 1 | |
| ≥500, n (%) | data | count_pct | 1 | |
| | spacer | | 0 | |
| Maximum Change from Baseline in QTcF (msec) | header | | 0 | |
| <30, n (%) | data | count_pct | 1 | |
| ≥30 to <60, n (%) | data | count_pct | 1 | |
| ≥60, n (%) | data | count_pct | 1 | |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|-------------|---------|
| count_pct | xxx (xx.x) | 3 (1.2) |

### Calculation Methods

- **Maximum post-baseline QTcF**: Highest QTcF value across all post-baseline visits per subject
- **Maximum change from baseline**: Highest change (AVAL − BASE) across all post-baseline visits per subject
- **Subject counted once**: Using maximum post-baseline value (absolute or change)
- **Categories**: Per ICH E14 guidance — absolute thresholds at 450, 480, 500 msec; change thresholds at 30, 60 msec
- **Flag subjects**: QTcF ≥500 msec or change ≥60 msec should be flagged for narrative
- **SAS**: PROC FREQ on derived maximum post-baseline categories

### Footnotes

1. Safety Population.
2. QTcF = QT corrected by Fridericia method.
3. Categories based on ICH E14 guidance.
4. Each subject counted once using maximum post-baseline value.

---

## Table: ECG Qualitative Overall Interpretation

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADEG |
| Orientation | PORTRAIT |
| Filter | SAFFL = 'Y' |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Overall Interpretation | header | | 0 | |
| Normal, n (%) | data | count_pct | 1 | |
| Abnormal - Not Clinically Significant, n (%) | data | count_pct | 1 | |
| Abnormal - Clinically Significant, n (%) | data | count_pct | 1 | |

### Calculation Methods

- **Overall interpretation**: Investigator or central reader assessment of overall ECG (EGINTPR in ADEG)
- **Categories**: Normal, Abnormal NCS, Abnormal CS — per investigator/cardiologist assessment
- **Worst post-baseline**: Each subject classified by worst post-baseline interpretation
- **SAS**: PROC FREQ

### Footnotes

1. Safety Population.
2. Overall ECG interpretation by investigator.
