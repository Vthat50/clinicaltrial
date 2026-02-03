---
name: Demographics & Baseline Characteristics
ich_section: "14.1"
display_order: 2
version: "2.0.0"
---

# Demographics & Baseline Characteristics

Always included, every study.

## What Comes from the Protocol

- **Disease indication**: determines disease-specific baseline variables (e.g., tumor stage, ECOG, prior lines)
- **Stratification factors**: often overlap with baseline variables
- **Age restrictions**: whether elderly (≥75) subgroup is relevant
- **Geographic scope**: whether region is collected
- **Baseline assessments**: physical exam, ECOG, pregnancy test, viral serology, genetic screening

## Column Structure

- **Two-arm with total**: {Arm 1} | {Arm 2} | Total
- **Three-arm with total**: {Arm 1} | {Arm 2} | {Arm 3} | Total
- Arm names from `facts.arm_names[]`.

---

## Table: Demographics and Baseline Characteristics

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADSL |
| Orientation | PORTRAIT |
| Filter | SAFFL = 'Y' |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Age (years) | header | | 0 | |
| n | data | count | 1 | |
| Mean (SD) | data | mean_sd | 1 | |
| Median | data | median | 1 | |
| Min, Max | data | min_max | 1 | |
| | spacer | | 0 | |
| Age Group, n (%) | header | | 0 | |
| <65 years | data | count_pct | 1 | |
| ≥65 years | data | count_pct | 1 | |
| ≥75 years | data | count_pct | 1 | Optional: included when elderly subgroup is relevant |
| | spacer | | 0 | |
| Sex, n (%) | header | | 0 | |
| Male | data | count_pct | 1 | |
| Female | data | count_pct | 1 | |
| | spacer | | 0 | |
| Race, n (%) | header | | 0 | Dynamic: categories from data or protocol |
| (categories from data) | data | count_pct | 1 | e.g., White, Black or African American, Asian, Other |
| | spacer | | 0 | |
| Ethnicity, n (%) | header | | 0 | |
| Hispanic or Latino | data | count_pct | 1 | |
| Not Hispanic or Latino | data | count_pct | 1 | |
| Not Reported | data | count_pct | 1 | |
| | spacer | | 0 | |
| Weight (kg) | header | | 0 | |
| n | data | count | 1 | |
| Mean (SD) | data | mean_sd | 1 | |
| Median | data | median | 1 | |
| | spacer | | 0 | |
| Height (cm) | header | | 0 | |
| n | data | count | 1 | |
| Mean (SD) | data | mean_sd | 1 | |
| Median | data | median | 1 | |
| | spacer | | 0 | |
| BMI (kg/m²) | header | | 0 | |
| n | data | count | 1 | |
| Mean (SD) | data | mean_sd | 1 | |
| Median | data | median | 1 | |
| | spacer | | 0 | |
| DISEASE-SPECIFIC BASELINE | placeholder | | 0 | Rows appended from therapeutic area config or Claude extraction |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|-------------|---------|
| count | xxx | 245 |
| mean_sd | xx.x (xx.xx) | 58.3 (12.45) |
| median | xx.x | 59.0 |
| min_max | xx.x-xx.x | 22.0-84.0 |
| count_pct | xxx (xx.x) | 156 (63.7) |

### Calculation Methods

- **Continuous variables** (Age, Weight, Height, BMI): PROC MEANS / PROC UNIVARIATE for n, Mean, SD, Median, Min, Max
- **Categorical variables** (Age Group, Sex, Race, Ethnicity): PROC FREQ for n and percentage
- **Percentages**: Based on non-missing N per column (denominator = N in column header)
- **Race categories**: Dynamic from data; standard categories per OMB/FDA guidance
- **Disease-specific rows**: Appended from therapeutic area config (e.g., oncology adds tumor stage, histology, prior lines; RA adds DAS28, disease duration)
- **BMI**: Calculated as Weight (kg) / Height (m)² if not directly available

### Footnotes

1. Safety Population: All subjects who received at least one dose of study treatment.
2. Percentages based on N in column header.
3. Disease-specific variables appended from therapeutic area config.

---

## Table: Physical Examination - Shift Table

Condition: Only if physical exam is collected.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADSL |
| Orientation | LANDSCAPE |
| Filter | SAFFL = 'Y' |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Body System | header | | 0 | Dynamic: one block per body system |
| Normal → Normal | data | count | 1 | Baseline Normal, Post-baseline Normal |
| Normal → Abnormal NCS | data | count | 1 | NCS = Not Clinically Significant |
| Normal → Abnormal CS | data | count | 1 | CS = Clinically Significant |
| Abnormal → Normal | data | count | 1 | |
| Abnormal → Abnormal NCS | data | count | 1 | |
| Abnormal → Abnormal CS | data | count | 1 | |

### Calculation Methods

- **Shift**: Baseline finding → worst post-baseline finding per body system per subject
- **Categories**: Normal, Abnormal NCS (Not Clinically Significant), Abnormal CS (Clinically Significant)
- **Baseline**: Last assessment on or before first dose
- **Post-baseline**: Worst post-baseline assessment
- **SAS**: PROC FREQ cross-tabulation (baseline × post-baseline)

### Footnotes

1. Safety Population.
2. NCS = Not Clinically Significant; CS = Clinically Significant.

---

## Table: ECOG Performance Status by Visit

Condition: Only if ECOG PS is assessed.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADSL |
| Orientation | PORTRAIT |
| Filter | SAFFL = 'Y' |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| ECOG PS, n (%) | header | | 0 | |
| 0 - Fully active | data | count_pct | 1 | |
| 1 - Restricted | data | count_pct | 1 | |
| 2 - Ambulatory | data | count_pct | 1 | |
| 3 - Limited self-care | data | count_pct | 1 | |
| 4 - Completely disabled | data | count_pct | 1 | |

### Calculation Methods

- **ECOG PS**: From ADSL baseline ECOG (ECOGBL) or ADQS
- **Categories**: ECOG 0–4 per Oken et al. 1982
- **SAS**: PROC FREQ

### Footnotes

1. Safety Population.

---

## Table: ECOG Performance Status - Shift Table

Condition: Only if ECOG PS is assessed.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADSL |
| Orientation | LANDSCAPE |
| Filter | SAFFL = 'Y' |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Baseline ECOG → Post-baseline ECOG | header | | 0 | |
| Improved | data | count_pct | 1 | Decrease in ECOG PS score |
| Stable | data | count_pct | 1 | No change |
| Worsened | data | count_pct | 1 | Increase in ECOG PS score |

### Calculation Methods

- **Improved**: Post-baseline ECOG < Baseline ECOG
- **Stable**: Post-baseline ECOG = Baseline ECOG
- **Worsened**: Post-baseline ECOG > Baseline ECOG
- **Post-baseline**: Worst (highest) post-baseline ECOG score per subject
- **SAS**: Derived variable, then PROC FREQ

### Footnotes

1. Safety Population.
2. Improved = decrease in ECOG PS score; Worsened = increase in ECOG PS score.
