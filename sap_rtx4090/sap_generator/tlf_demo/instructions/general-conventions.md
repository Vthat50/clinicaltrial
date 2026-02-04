# General Conventions

Apply to all TLF shells produced by the demo generator.

## SAP-Driven Content

The SAP is the source of truth. Include ONLY what the SAP specifies:
- Statistics: Use only the statistics the SAP defines for each table type
- Visits: Use only the visits/timepoints the SAP specifies
- Footnotes: If the SAP states p-values are descriptive or no multiplicity adjustment applies, include this in a footnote
- CFB: Change from Baseline uses the same descriptive statistics definition as actual values

When the SAP uses general terms without defining them in a specific section, look for definitions in the SAP's General Methodology section.

## Output Format

Shells are rendered as monospaced text (Courier New), not Word tables:
- Columns aligned by character position
- Horizontal rules made of underscore characters
- No cell borders or gridlines
- Opens identically in Word, Google Docs, or any text editor

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

## Numbering

Use the EXACT numbering from the SAP's TLF index. Do not add sub-levels or change the numbering scheme. The SAP index is the source of truth for TLF numbers.

## Footnote Ordering

1. Population definition (full definition, not just the name)
2. Statistical method (exact test, model, stratification factors)
3. Domain-specific (coding dictionary, grading scale, baseline definition, censoring rules)
4. Percentage denomination
5. Abbreviations

## Comparison Statistics

Hazard ratio, p-value, treatment difference, and odds ratio are single comparison values. They are placed in rows that span all treatment arm columns or in a dedicated "Treatment Comparison" section. They are NOT displayed per-arm.

## Format Codes

Use ### notation to show field width and decimal precision. Each # represents a digit position.

| Format | Placeholder |
|--------|------------|
| count | ### |
| count_pct | ### (##.#%) |
| mean | ###.# |
| sd | ##.## |
| mean_sd | ###.# (##.##) |
| median | ###.# |
| q1_q3 | ###.#, ###.# |
| median_ci | ###.# (###.#, ###.#) |
| min_max | ###-### |
| median_range | ###.# (###-###) |
| ci_95 | (###.#, ###.#) |
| hr_ci | #.## (##.##, ##.##) |
| diff_ci | ##.# (##.#, ##.#) |
| ratio_ci | #.## (##.##, ##.##) |
| p_value | #.#### |
| percentage | ##.#% |
| events_rate | ### (##.#%) |

Both () and [] are acceptable for confidence intervals.

## Column Templates by Study Design

- 2-arm: Parameter | Arm1 (N=###) | Arm2 (N=###) | Total (N=###)
- 3+ arm: Parameter | Arm1 (N=###) | Arm2 (N=###) | Arm3 (N=###) | Total (N=###)
- Single-arm: Parameter | Treatment (N=###)
- Descriptive/continuous stats (labs, vitals): Parameter / Statistic | Arm1 | Arm2 (no Total)
- Dose-escalation: Parameter | Cohort 1 (N=###) | Cohort 2 (N=###) | ... | Overall (N=###)

## Listing Column Abbreviations

For listings with many columns, use standard abbreviations to prevent truncation. Add a footnote defining all abbreviations used.

Common abbreviations:
- Subj ID (Subject ID)
- Trt Grp (Treatment Group)
- Assess Dt (Assessment Date)
- Coll Dt (Collection Date)
- BOR (Best Overall Response)
- CFB (Change from Baseline)
- BL (Baseline)
- Grade (CTCAE Grade)
- Ref Rng (Reference Range)
- Abn Flag (Abnormal Flag)
