# First Table from the SAP Index

Generates one table for the first entry in the SAP TLF index. The endpoint type determines the row structure.

## How to Read the Protocol for This Table

Read the protocol and SAP to extract:

1. **Endpoint identification**: Find the primary endpoint definition in the protocol. The SAP title tells you the endpoint name. Read the full definition including how it is measured, assessment schedule, and criteria.
2. **Endpoint type**: Determine from the endpoint definition whether it is time-to-event, binary, continuous, count, or ordinal. The SAP methodology section usually states the analysis method which confirms the type.
3. **Analysis population**: Read the population definition section. Look for the full inclusion criteria for the population named in the SAP index — not just the name, but the complete definition.
4. **Treatment arms**: Extract the exact arm names as written in the protocol. Include the dosing regimen if it appears in the arm name. Use these exact names in column headers.
5. **Stratification factors**: Look in the randomization section and the statistical methods section. List all stratification factors — these appear in footnotes and determine which model adjustments apply.
6. **Covariates**: For regression models, check if the SAP specifies covariates beyond stratification factors.
7. **Equivalence/NI margins**: For biosimilar or non-inferiority studies, find the pre-specified margin and the direction of the comparison.
8. **Response criteria**: For binary endpoints, find the exact response definition. Look for the assessment criteria name and version used.
9. **Landmark timepoints**: For time-to-event endpoints, check if the SAP specifies landmark analysis timepoints. If not stated, derive from the study duration.
10. **Censoring rules**: For time-to-event endpoints, find the censoring rules — what happens when a subject is lost to follow-up, starts new therapy, or dies without an event.
11. **Event breakdown**: For time-to-event endpoints, identify the types of events that constitute the composite endpoint so they can be listed as sub-rows.

## Decision Rules

- If the SAP specifies the analysis method, use it. If not, use the default method table below.
- If the protocol defines multiple analysis populations for the primary endpoint, generate the table for the population specified in the SAP index entry.
- If the study has multiple treatment periods, generate the table for the period relevant to the endpoint.
- For event counts and censored counts, always use count_pct format and include breakdown by reason as indented sub-rows.
- 95% CIs must be shown inline with the statistic they belong to (inside the same format code). Do NOT create standalone CI rows.

## Default Analysis Method

| Endpoint Type | Design | Default Method |
|--------------|--------|----------------|
| time_to_event | any | cox_ph |
| binary | biosimilar/equivalence | logistic_regression |
| binary | other | clopper_pearson (exact binomial) |
| continuous | single timepoint | ancova |
| continuous | repeated measures | mmrm |
| count/rate | any | negative_binomial |
| ordinal | any | proportional_odds (CMH) |

---

## Time-to-Event Endpoint (cox_ph)

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
| {Event reason 1}, n (%) | data | count_pct | 1 | Breakdown by event type from endpoint definition |
| {Event reason 2}, n (%) | data | count_pct | 1 | Include all event types in the composite |
| Number censored, n (%) | data | count_pct | 0 | CNSR = 1 |
| | spacer | | 0 | |
| Kaplan-Meier Estimates | header | | 0 | |
| 25th percentile [95% CI] | data | median_ci | 1 | From PROC LIFETEST |
| Median [95% CI] | data | median_ci | 1 | Brookmeyer-Crowley CI |
| 75th percentile [95% CI] | data | median_ci | 1 | From PROC LIFETEST |
| | spacer | | 0 | |
| Landmark Rates [95% CI] | header | | 0 | |
| 6-month rate [95% CI] | data | rate_ci | 1 | Greenwood SE, log-log transform |
| 12-month rate [95% CI] | data | rate_ci | 1 | Included if study duration allows |
| 24-month rate [95% CI] | data | rate_ci | 1 | Included if study duration allows |
| | spacer | | 0 | |
| Number at Risk (recommended) | header | | 0 | Commonly shown in KM figures; optional in summary tables |
| At 6 months | data | count | 1 | |
| At 12 months | data | count | 1 | |
| At 24 months | data | count | 1 | |
| | spacer | | 0 | |
| Treatment Comparison | header | | 0 | |
| Hazard Ratio [95% CI] | data | hr_ci | 1 | Single comparison value, NOT per-arm |
| P-value (stratified log-rank) | data | p_value | 1 | Single comparison value |

Do NOT include Mean (SD). Censored survival data uses Kaplan-Meier median + CI, not mean.

### Calculation Methods

- KM estimates: PROC LIFETEST; 95% CI for median by Brookmeyer-Crowley method
- Landmark rates: KM estimate at timepoint; 95% CI by Greenwood formula with log-log transformation
- Hazard ratio: PROC PHREG; Cox model stratified by randomization stratification factors; ties by Efron method
- P-value: Stratified log-rank test from PROC LIFETEST
- Censoring: Subjects without events censored at date of last known alive or last adequate assessment

### Footnotes

1. {Population} Population defined as {full definition from protocol}.
2. Kaplan-Meier method used for event-free survival estimation.
3. Cox proportional hazards model; HR <1 favors {Arm 1}.
4. Stratified by {stratification factors from protocol}.
5. P-value from stratified log-rank test.
6. 95% CI for median by Brookmeyer-Crowley method.
7. 95% CI for rates by Greenwood formula with log-log transformation.

### Programming Notes

PARAMCD = {endpoint code}, CNSR = 0 for events, CNSR = 1 for censored. AVAL = time to event in days/months. Stratification factors mapped to ADTTE variables.

---

## Binary Response Endpoint (clopper_pearson)

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
| Responders, n (%) | data | count_pct | 0 | Bold; AVALC = 'Y' or per response criteria |
| [95% CI] | data | ci_95 | 1 | Clopper-Pearson exact CI |
| | spacer | | 0 | |
| Response Categories | header | | 0 | Include all categories from the response criteria |
| {Category 1}, n (%) | data | count_pct | 1 | Each response category as defined in protocol |
| {Category 2}, n (%) | data | count_pct | 1 | |
| {Category 3}, n (%) | data | count_pct | 1 | |
| | spacer | | 0 | |
| Non-responders, n (%) | data | count_pct | 0 | |
| | spacer | | 0 | |
| Treatment Comparison | header | | 0 | |
| Difference [95% CI] | data | diff_ci | 1 | Single comparison value; Newcombe method |
| Odds Ratio [95% CI] | data | ratio_ci | 1 | Single comparison value |
| P-value | data | p_value | 1 | Single comparison value; Fisher's exact or CMH |

### Calculation Methods

- Response rate: n responders / N evaluable x 100
- 95% CI for rate: Exact binomial (Clopper-Pearson) method
- Difference: Rate(Arm 1) - Rate(Arm 2); 95% CI by Newcombe method
- Odds Ratio: From 2x2 table or logistic model; profile likelihood CI
- P-value: Fisher's exact test or stratified CMH test

### Footnotes

1. {Population} Population defined as {full definition from protocol}.
2. Response rate with exact (Clopper-Pearson) 95% CI.
3. Risk difference with 95% CI by Newcombe method.
4. Fisher's exact test for comparison (or stratified CMH test stratified by {stratification factors}).
5. Response defined as: {response criteria from protocol}.

---

## Continuous Endpoint (ancova)

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
| LS Mean Difference [95% CI] | data | diff_ci | 1 | Single comparison value |
| P-value | data | p_value | 1 | Single comparison value |

### Calculation Methods

- Descriptive: PROC MEANS for n, mean, SD, median
- ANCOVA: PROC GLM or PROC MIXED; MODEL: change = treatment baseline strat_factors
- LS Means: LSMEANS treatment / PDIFF CL
- Baseline: Last non-missing value on or before first dose (ABLFL = 'Y')

### Footnotes

1. {Population} Population defined as {full definition from protocol}.
2. ANCOVA model with treatment as fixed effect and baseline value as covariate.
3. Additional covariates: {stratification factors from protocol}.
4. LS = least squares; SE = standard error.
