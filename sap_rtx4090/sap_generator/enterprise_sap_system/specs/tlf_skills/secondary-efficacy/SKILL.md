---
name: Secondary Efficacy
ich_section: "14.2"
display_order: 12
version: "2.0.0"
---

# Secondary Efficacy

Generate one table per secondary or exploratory endpoint. Same rules as primary efficacy: one table per endpoint × population × review combination.

For exploratory endpoints, p-values are typically labeled as nominal (not adjusted for multiplicity).

## What Comes from the Protocol

Same as primary efficacy:
- Endpoint name, type, populations, review types, analysis method, stratification factors, covariates, response criteria, landmark timepoints, censoring rules.

## Default Analysis Methods

Same defaults as primary efficacy. See primary-efficacy/SKILL.md for the full table.

## Column Structure

Same as primary efficacy. Arm names from `facts.arm_names[]`.

---

## Table Template: Time-to-Event Endpoint (cox_ph)

Identical structure to primary efficacy time-to-event template.

| Setting | Value |
|---------|-------|
| Population | Per endpoint definition |
| Source | ADTTE |
| Orientation | PORTRAIT |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Number of subjects | data | count | 0 | |
| Number of events, n (%) | data | count_pct | 0 | |
| Number censored, n (%) | data | count_pct | 0 | |
| | spacer | | 0 | |
| Kaplan-Meier Estimates | header | | 0 | |
| 25th percentile [95% CI] | data | median_ci | 1 | |
| Median [95% CI] | data | median_ci | 1 | |
| 75th percentile [95% CI] | data | median_ci | 1 | |
| | spacer | | 0 | |
| Landmark Rates [95% CI] | header | | 0 | |
| 6-month rate [95% CI] | data | rate_ci | 1 | Optional |
| 12-month rate [95% CI] | data | rate_ci | 1 | Optional |
| 24-month rate [95% CI] | data | rate_ci | 1 | Optional |
| | spacer | | 0 | |
| Treatment Comparison | header | | 0 | |
| Hazard Ratio [95% CI] | data | hr_ci | 1 | comparison_only |
| P-value (stratified log-rank) | data | p_value | 1 | comparison_only |

### Calculation Methods

Same as primary efficacy cox_ph. See primary-efficacy/SKILL.md.

### Footnotes

1. {Population} Population.
2. Kaplan-Meier method used for event-free survival estimation.
3. Cox proportional hazards model; HR <1 favors {Arm 1}.
4. Stratified by {stratification factors}.
5. P-value from stratified log-rank test.

---

## Table Template: Binary Response Endpoint (clopper_pearson)

| Setting | Value |
|---------|-------|
| Population | Per endpoint definition |
| Source | ADRS |
| Orientation | PORTRAIT |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Evaluable subjects, N | data | count | 0 | |
| | spacer | | 0 | |
| Responders, n (%) | data | count_pct | 0 | **Bold** |
| [95% CI] | data | ci_95 | 1 | Clopper-Pearson |
| | spacer | | 0 | |
| Non-responders, n (%) | data | count_pct | 0 | |
| | spacer | | 0 | |
| Treatment Comparison | header | | 0 | |
| Difference [95% CI] | data | diff_ci | 1 | comparison_only |
| Odds Ratio [95% CI] | data | or_ci | 1 | comparison_only |
| P-value | data | p_value | 1 | comparison_only |

### Calculation Methods

Same as primary efficacy clopper_pearson. See primary-efficacy/SKILL.md.

### Footnotes

1. {Population} Population.
2. Response rate with exact (Clopper-Pearson) 95% CI.
3. Risk difference with 95% CI by Newcombe method.
4. P-value from CMH test stratified by {stratification factors}.

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
| Post-baseline (Week {X}) | header | | 0 | |
| n | data | count | 1 | |
| Mean (SD) | data | mean_sd | 1 | |
| | spacer | | 0 | |
| Change from Baseline | header | | 0 | |
| n | data | count | 1 | |
| Mean (SD) | data | mean_sd | 1 | |
| | spacer | | 0 | |
| ANCOVA Results | header | | 0 | |
| LS Mean (SE) | data | mean_se | 1 | |
| LS Mean Difference [95% CI] | data | diff_ci | 1 | comparison_only |
| P-value | data | p_value | 1 | comparison_only |

### Calculation Methods

Same as primary efficacy ancova. See primary-efficacy/SKILL.md.

### Footnotes

1. {Population} Population.
2. ANCOVA model with treatment as fixed effect and baseline value as covariate.
3. LS = least squares; SE = standard error.

---

## Table Template: Best Overall Response (Oncology)

Condition: Only for oncology studies with tumor assessment (RECIST). This is a secondary endpoint table showing the full response distribution.

| Setting | Value |
|---------|-------|
| Population | Per endpoint definition |
| Source | ADRS |
| Orientation | PORTRAIT |
| Filter | PARAMCD = 'BOR' |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Evaluable subjects, N | data | count | 0 | |
| | spacer | | 0 | |
| Best Overall Response | header | | 0 | Categories from RECIST |
| CR, n (%) | data | count_pct | 1 | AVALC = 'CR' |
| PR, n (%) | data | count_pct | 1 | AVALC = 'PR' |
| SD, n (%) | data | count_pct | 1 | AVALC = 'SD' |
| PD, n (%) | data | count_pct | 1 | AVALC = 'PD' |
| NE, n (%) | data | count_pct | 1 | AVALC = 'NE' |
| | spacer | | 0 | |
| ORR (CR+PR), n (%) | data | count_pct | 0 | **Bold** |
| [95% CI] | data | ci_95 | 1 | Clopper-Pearson |
| | spacer | | 0 | |
| DCR (CR+PR+SD), n (%) | data | count_pct | 0 | |
| [95% CI] | data | ci_95 | 1 | |

### Calculation Methods

- **Response categories**: From RECIST v1.1 (or protocol-specified criteria)
- **ORR**: (CR + PR) / N evaluable × 100
- **DCR**: (CR + PR + SD) / N evaluable × 100
- **95% CI**: Exact Clopper-Pearson for each rate
- **Subjects without post-baseline assessment**: Counted as NE

### Footnotes

1. {Population} Population.
2. Response assessed per RECIST v1.1 (or {criteria from protocol}).
3. 95% CI calculated using exact (Clopper-Pearson) method.
4. CR = complete response; PR = partial response; SD = stable disease; PD = progressive disease; NE = not evaluable.
