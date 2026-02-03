# General Conventions

Apply to all TLF shells produced by the demo generator.

## Display Standards

| Convention | Value |
|-----------|-------|
| Font | 9pt Courier New |
| Date format | DDMONYYYY |
| Missing values | "--" (em-dash) or "NC" (not calculable) |
| Page header | Study number / CONFIDENTIAL / Page x of y |

## Decimal Precision

| Data Type | Precision |
|-----------|-----------|
| Continuous variables | One more decimal place than collected data |
| Percentages | xx.x% |
| P-values | x.xxxx |
| Hazard ratios / odds ratios | x.xx |

## Standard Statistics

- Continuous variables: n, Mean, SD, Median, Q1, Q3, Min, Max
- Categorical variables: n (xx.x%) where % denominator is the column N

## Source Line

Every table and listing includes:

```
Source: [ADaM dataset] Program: [program_name].sas Date: DDMONYYYY
```

## ICH E3 Numbering

- Tables: 14.x.x (14.1 = demographics, 14.2 = efficacy, 14.3 = safety)
- Figures: 14.x.Fx
- Listings: 16.2.x

## Footnote Ordering

1. Population definition (full definition, not just the name)
2. Statistical method (exact test, model, stratification factors)
3. Domain-specific (coding dictionary, grading scale, baseline definition, censoring rules)
4. Percentage denomination
5. Abbreviations

## Comparison Statistics

Hazard ratio, p-value, treatment difference, and odds ratio are single comparison values. They are placed in rows that span all treatment arm columns or in a dedicated "Treatment Comparison" section. They are NOT displayed per-arm.

## Format Codes

| Format | Placeholder |
|--------|------------|
| count | xx |
| count_pct | n (xx.x%) |
| mean | xx.x |
| sd | xx.xx |
| mean_sd | xx.x (xx.xx) |
| median | xx.x |
| q1_q3 | xx.x, xx.x |
| median_ci | xx.x (xx.x, xx.x) or xx.x [xx.x, xx.x] |
| min_max | xx-xx |
| median_range | xx.x (xx-xx) |
| ci_95 | (xx.x, xx.x) or [xx.x, xx.x] |
| hr_ci | x.xx (xx.x, xx.x) or x.xx [xx.x, xx.x] |
| diff_ci | xx.x (xx.x, xx.x) or xx.x [xx.x, xx.x] |
| ratio_ci | x.xx (xx.x, xx.x) or x.xx [xx.x, xx.x] |
| p_value | x.xxxx |
| percentage | xx.x% |
| events_rate | n (xx.x%) |

Both () and [] are acceptable for confidence intervals.

## Column Templates by Study Design

- 2-arm: Parameter | Arm1 (N=xxx) | Arm2 (N=xxx) | Total (N=xxx)
- 3+ arm: Parameter | Arm1 (N=xxx) | Arm2 (N=xxx) | Arm3 (N=xxx) | Total (N=xxx)
- Single-arm: Parameter | Treatment (N=xxx)
- Descriptive/continuous stats (labs, vitals): Parameter / Statistic | Arm1 | Arm2 (no Total)
- Dose-escalation: Parameter | Cohort 1 (N=xxx) | Cohort 2 (N=xxx) | ... | Overall (N=xxx)
