---
name: Primary Efficacy
ich_section: "14.2"
display_order: 11
version: "2.0.0"
---

# Primary Efficacy

Generate one table per primary endpoint. If the endpoint is analyzed in multiple populations (ITT, PP), generate a separate table per population. If the endpoint has review types (Central, Local), generate a separate table per review within each population.

## What Comes from the Protocol

- **Endpoint name** (e.g., "Progression-Free Survival", "Objective Response Rate")
- **Endpoint type**: time_to_event, binary, continuous, count, ordinal
- **Analysis population(s)**: ITT, PP, mITT — one table per population
- **Review types** (if applicable): Central, Local — one table per review
- **Analysis method** (if specified): Cox PH, logistic regression, ANCOVA, etc.
- **Stratification factors**: used in stratified analyses
- **Covariates**: for regression models
- **Equivalence/NI margins**: for biosimilar or NI studies
- **Response criteria**: e.g., RECIST v1.1, BICR
- **Landmark timepoints**: e.g., 6-month, 12-month survival rates
- **Censoring rules**: from protocol or SAP

## Default Analysis Method (when protocol does not specify)

| Endpoint Type | Design | Default Method |
|--------------|--------|----------------|
| time_to_event | any | cox_ph |
| binary | biosimilar/equivalence | logistic_regression |
| binary | other | clopper_pearson (exact binomial) |
| continuous | single timepoint | ancova |
| continuous | repeated measures | mmrm |
| count/rate | any | negative_binomial |
| ordinal | any | proportional_odds (CMH) |

## Column Structure

- **Two-arm study**: {Arm 1} | {Arm 2} — arm names from protocol
- **Two-arm with total**: {Arm 1} | {Arm 2} | Total
- **Three-arm**: {Arm 1} | {Arm 2} | {Arm 3} | Total
- **Single-arm**: {Drug Name} only

Arm names are substituted from `facts.arm_names[]`.

---

## Table Template: Time-to-Event Endpoint (cox_ph)

| Setting | Value |
|---------|-------|
| Population | Per endpoint definition (ITT, PP, or mITT) |
| Source | ADTTE |
| Orientation | PORTRAIT |
| Filter | PARAMCD = '{endpoint parameter code}' |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Number of subjects | data | count | 0 | N per arm from population |
| Number of events, n (%) | data | count_pct | 0 | CNSR = 0 |
| Number censored, n (%) | data | count_pct | 0 | CNSR = 1 |
| | spacer | | 0 | |
| Kaplan-Meier Estimates | header | | 0 | |
| 25th percentile [95% CI] | data | median_ci | 1 | From PROC LIFETEST |
| Median [95% CI] | data | median_ci | 1 | Brookmeyer-Crowley CI |
| 75th percentile [95% CI] | data | median_ci | 1 | From PROC LIFETEST |
| | spacer | | 0 | |
| Landmark Rates [95% CI] | header | | 0 | |
| 6-month rate [95% CI] | data | rate_ci | 1 | Optional; Greenwood SE, log-log transform |
| 12-month rate [95% CI] | data | rate_ci | 1 | Optional; included if study duration allows |
| 24-month rate [95% CI] | data | rate_ci | 1 | Optional; included if study duration allows |
| | spacer | | 0 | |
| Number at Risk | header | | 0 | Optional |
| At 6 months | data | count | 1 | Optional |
| At 12 months | data | count | 1 | Optional |
| At 24 months | data | count | 1 | Optional |
| | spacer | | 0 | |
| Treatment Comparison | header | | 0 | |
| Hazard Ratio [95% CI] | data | hr_ci | 1 | Cox model; comparison_only (not shown in single-arm) |
| P-value (stratified log-rank) | data | p_value | 1 | comparison_only |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|------------|---------|
| count | xxx | 125 |
| count_pct | xxx (xx.x) | 87 (69.6) |
| median_ci | xx.x [xx.x, xx.x] | 14.2 [11.8, 18.6] |
| rate_ci | xx.x [xx.x, xx.x] | 72.3 [65.1, 78.4] |
| hr_ci | x.xxx [x.xxx, x.xxx] | 0.752 [0.583, 0.970] |
| p_value | x.xxxx | 0.0284 |

### Calculation Methods

- **KM estimates**: PROC LIFETEST; 95% CI for median by Brookmeyer-Crowley method
- **Landmark rates**: KM estimate at timepoint; 95% CI by Greenwood formula with log-log transformation
- **Hazard ratio**: PROC PHREG; Cox model stratified by randomization stratification factors; ties by Efron method
- **P-value**: Stratified log-rank test from PROC LIFETEST
- **Censoring**: Subjects without events censored at date of last known alive or last adequate assessment

### Footnotes

1. {Population} Population.
2. Kaplan-Meier method used for event-free survival estimation.
3. Cox proportional hazards model; HR <1 favors {Arm 1}.
4. Stratified by {stratification factors from protocol}.
5. P-value from stratified log-rank test.
6. 95% CI for median by Brookmeyer-Crowley method.
7. 95% CI for rates by Greenwood formula with log-log transformation.

### Figures

- **Kaplan-Meier plot**: One per time-to-event endpoint. Curves by arm, censoring tick marks, number-at-risk table below x-axis, median lines, HR + p-value annotation.
- **Forest plot**: If subgroups pre-specified, one forest plot per primary TTE endpoint.

---

## Table Template: Binary Response Endpoint (clopper_pearson)

| Setting | Value |
|---------|-------|
| Population | Per endpoint definition |
| Source | ADRS |
| Orientation | PORTRAIT |
| Filter | PARAMCD = '{endpoint parameter code}' |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Evaluable subjects, N | data | count | 0 | N with non-missing assessment |
| | spacer | | 0 | |
| Responders, n (%) | data | count_pct | 0 | **Bold**; AVALC = 'Y' or CR+PR |
| [95% CI] | data | ci_95 | 1 | Clopper-Pearson exact CI |
| | spacer | | 0 | |
| Non-responders, n (%) | data | count_pct | 0 | |
| | spacer | | 0 | |
| Treatment Comparison | header | | 0 | |
| Difference [95% CI] | data | diff_ci | 1 | comparison_only; Newcombe method |
| Odds Ratio [95% CI] | data | or_ci | 1 | comparison_only |
| P-value | data | p_value | 1 | comparison_only; Fisher's exact or CMH |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|------------|---------|
| count | xxx | 198 |
| count_pct | xxx (xx.x) | 138 (69.7) |
| ci_95 | [xx.x, xx.x] | [62.8, 76.0] |
| diff_ci | xx.x [xx.x, xx.x] | -2.3 [-11.0, 6.4] |
| or_ci | x.xxx [x.xxx, x.xxx] | 0.921 [0.584, 1.453] |
| p_value | x.xxxx | 0.7281 |

### Calculation Methods

- **Response rate**: n responders / N evaluable × 100
- **95% CI for rate**: Exact binomial (Clopper-Pearson) method
- **Difference**: Rate(Arm 1) − Rate(Arm 2); 95% CI by Newcombe method
- **Odds Ratio**: From 2×2 table or logistic model; profile likelihood CI
- **P-value**: Fisher's exact test or stratified CMH test

### Footnotes

1. {Population} Population.
2. Response rate with exact (Clopper-Pearson) 95% CI.
3. Risk difference with 95% CI by Newcombe method.
4. Fisher's exact test for comparison (or stratified CMH test stratified by {stratification factors}).
5. Response defined as: {response criteria from protocol}.

---

## Table Template: Binary Response Endpoint (logistic_regression)

For biosimilar/equivalence studies.

| Setting | Value |
|---------|-------|
| Population | Per endpoint definition |
| Source | ADRS |
| Orientation | PORTRAIT |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Evaluable subjects, N | data | count | 0 | |
| Responders, n (%) | data | count_pct | 0 | |
| [95% CI] | data | ci_95 | 1 | Clopper-Pearson |
| | spacer | | 0 | |
| Logistic Regression | header | | 0 | |
| Odds Ratio [95% CI] | data | or_ci | 1 | comparison_only |
| P-value | data | p_value | 1 | comparison_only |
| | spacer | | 0 | |
| Covariates in Model | header | | 0 | List from SAP |

### Calculation Methods

- **Odds Ratio**: From logistic regression model with treatment and pre-specified covariates
- **95% CI**: Profile likelihood CI for OR
- **Equivalence**: Concluded if 90% CI for risk ratio or difference lies within pre-specified margins

### Footnotes

1. {Population} Population.
2. Response rate with exact (Clopper-Pearson) 95% CI.
3. Logistic regression model adjusted for {covariates from protocol}.
4. Equivalence margin: [{lower}, {upper}].
5. Response defined as: {response criteria from protocol}.

---

## Table Template: Continuous Endpoint (ancova)

| Setting | Value |
|---------|-------|
| Population | Per endpoint definition |
| Source | ADEFF |
| Orientation | PORTRAIT |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Baseline | header | | 0 | |
| n | data | count | 1 | |
| Mean (SD) | data | mean_sd | 1 | |
| Median | data | median | 1 | |
| | spacer | | 0 | |
| Post-baseline (Week {X}) | header | | 0 | Week from protocol |
| n | data | count | 1 | |
| Mean (SD) | data | mean_sd | 1 | |
| | spacer | | 0 | |
| Change from Baseline | header | | 0 | |
| n | data | count | 1 | |
| Mean (SD) | data | mean_sd | 1 | |
| | spacer | | 0 | |
| ANCOVA Results | header | | 0 | |
| LS Mean (SE) | data | mean_se | 1 | Per arm |
| LS Mean Difference [95% CI] | data | diff_ci | 1 | comparison_only |
| P-value | data | p_value | 1 | comparison_only |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|------------|---------|
| mean_sd | xx.x (xx.xx) | 24.3 (12.45) |
| mean_se | xx.x (xx.xx) | -3.2 (1.45) |
| diff_ci | xx.x [xx.x, xx.x] | -2.1 [-5.3, 1.1] |

### Calculation Methods

- **Descriptive**: PROC MEANS for n, mean, SD, median
- **ANCOVA**: PROC GLM or PROC MIXED; MODEL: change = treatment baseline strat_factors
- **LS Means**: LSMEANS treatment / PDIFF CL
- **Baseline**: Last non-missing value on or before first dose (ABLFL = 'Y')

### Footnotes

1. {Population} Population.
2. ANCOVA model with treatment as fixed effect and baseline value as covariate.
3. Additional covariates: {stratification factors from protocol}.
4. LS = least squares; SE = standard error.

---

## Table Template: Continuous Endpoint (mmrm)

For repeated measures / longitudinal endpoints.

| Setting | Value |
|---------|-------|
| Population | Per endpoint definition |
| Source | ADEFF |
| Orientation | LANDSCAPE |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Baseline | header | | 0 | |
| n | data | count | 1 | |
| Mean (SD) | data | mean_sd | 1 | |
| | spacer | | 0 | |
| Visit {X} | header | | 0 | **Repeating**: one block per visit |
| n | data | count | 1 | Repeating |
| LS Mean Change from Baseline (SE) | data | mean_se | 1 | Repeating |
| LS Mean Difference vs {Comparator} [95% CI] | data | diff_ci | 1 | comparison_only; repeating |
| P-value | data | p_value | 1 | comparison_only; repeating |

### Calculation Methods

- **MMRM**: PROC MIXED or PROC GLIMMIX
- **Model**: change = treatment visit treatment×visit baseline strat / DDFM=KR
- **Covariance**: REPEATED visit / SUBJECT=subject TYPE=UN (unstructured)
- **Degrees of freedom**: Kenward-Roger
- **LS Means**: LSMEANS treatment×visit / PDIFF CL SLICE=visit

### Footnotes

1. {Population} Population.
2. MMRM: treatment, visit, treatment×visit interaction, baseline value, stratification factors.
3. Unstructured covariance matrix. Kenward-Roger degrees of freedom.
