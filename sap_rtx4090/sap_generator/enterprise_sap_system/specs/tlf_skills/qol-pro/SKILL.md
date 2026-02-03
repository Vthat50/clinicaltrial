---
name: Quality of Life / PRO
ich_section: "14.2"
display_order: 15
version: "2.0.0"
---

# Quality of Life / PRO

Only included when the protocol specifies QoL or PRO instruments. All tables use ITT population.

For each instrument in the protocol (e.g., EORTC QLQ-C30, EQ-5D-5L, FACT-G, SF-36), generate the tables below. Repeat the full set per instrument.

## What Comes from the Protocol

- **Instrument name(s)**: validated PRO instruments specified (e.g., EORTC QLQ-C30, EQ-5D-5L, FACT-G)
- **Domains/subscales**: which domains are scored (e.g., Global Health Status, Physical Functioning, Pain)
- **Scoring direction**: whether higher scores = better or worse outcome
- **Assessment schedule**: which visits the instrument is administered
- **MID (minimally important difference)**: published threshold for clinically meaningful change
- **Primary PRO endpoint**: if PRO is a key secondary or exploratory endpoint
- **Missing data handling**: approach for missing questionnaires (e.g., MMRM, pattern mixture)

## Column Structure

- **Two-arm**: {Arm 1} | {Arm 2} (for by-visit summaries)
- **Two-arm with total**: {Arm 1} | {Arm 2} | Total (for responder analysis)
- Arm names from `facts.arm_names[]`.

---

## Table: {Instrument} — Summary by Visit

| Setting | Value |
|---------|-------|
| Population | ITT |
| Source | ADQS |
| Orientation | LANDSCAPE |

### Rows

Repeat per domain/subscale of the instrument:

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| {Domain/Subscale Name} | header | | 0 | Dynamic: one block per domain |
| n | data | count | 1 | Subjects with evaluable score at visit |
| Mean (SD) | data | mean_sd | 1 | |
| Median | data | median | 1 | |
| Min, Max | data | min_max | 1 | |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|-------------|---------|
| mean_sd | xx.x (xx.xx) | 68.4 (18.23) |
| median | xx.x | 70.0 |
| min_max | xx.x-xx.x | 8.3-100.0 |

### Calculation Methods

- **Scoring**: Per validated scoring manual for each instrument
- **Descriptive**: PROC MEANS by AVISIT and treatment arm
- **Missing items**: Handle per scoring manual rules (e.g., half-rule for EORTC)
- **Visits**: Summarized by scheduled assessment visit (AVISIT)

### Footnotes

1. ITT Population.
2. {Instrument full name and citation}.
3. Higher scores indicate {better/worse} {domain} per scoring manual.
4. Scores summarized by scheduled assessment visit.

---

## Table: {Instrument} — Change from Baseline

| Setting | Value |
|---------|-------|
| Population | ITT |
| Source | ADQS |
| Orientation | LANDSCAPE |

### Rows

Repeat per domain/subscale:

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| {Domain/Subscale Name} | header | | 0 | Dynamic: one block per domain |
| Baseline | header | | 1 | |
| n | data | count | 2 | |
| Mean (SD) | data | mean_sd | 2 | |
| | spacer | | 0 | |
| Change from Baseline at {Visit} | header | | 1 | |
| n | data | count | 2 | |
| Mean (SD) | data | mean_sd | 2 | |
| Median | data | median | 2 | |
| Min, Max | data | min_max | 2 | |
| | spacer | | 0 | |
| MMRM Results (if applicable) | header | | 1 | Only when MMRM is the pre-specified analysis |
| LS Mean (SE) | data | mean_se | 2 | |
| LS Mean Difference ({Arm 1} minus {Arm 2}) | data | diff_ci | 2 | comparison_only |
| 95% CI for difference | data | ci | 2 | comparison_only |
| p-value | data | pvalue | 2 | comparison_only |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|-------------|---------|
| mean_sd | xx.x (xx.xx) | -5.2 (14.78) |
| mean_se | xx.x (xx.xx) | -3.8 (1.42) |
| diff_ci | xx.x (xx.x, xx.x) | -4.2 (-8.1, -0.3) |

### Calculation Methods

- **Change from baseline**: Post-baseline score minus baseline score (CHG = AVAL − BASE)
- **Baseline**: Last evaluable score before first dose (ABLFL = 'Y')
- **MMRM model**: Change from baseline as dependent variable; treatment, visit, treatment×visit as fixed effects; baseline score as covariate; unstructured covariance; Kenward-Roger degrees of freedom
- **LS Mean Difference**: From LSMEANS statement with PDIFF CL option
- **SAS**: PROC MIXED for MMRM; PROC MEANS for descriptive

### Footnotes

1. ITT Population.
2. Change from baseline = post-baseline score minus baseline score.
3. MMRM model: change from baseline as dependent variable; treatment, visit, treatment-by-visit interaction as fixed effects; baseline score as covariate; unstructured covariance.
4. A positive change indicates {improvement/deterioration} per scoring convention.
5. Minimally important difference (MID) for {Instrument}: {value from literature}.

---

## Table: {Instrument} — Responder Analysis

Condition: Only when a validated MID or responder threshold exists.

| Setting | Value |
|---------|-------|
| Population | ITT |
| Source | ADQS |
| Orientation | PORTRAIT |

### Rows

Repeat per domain/subscale with a defined MID:

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| {Domain/Subscale Name} | header | | 0 | |
| Improved (change ≥ MID), n (%) | data | count_pct | 1 | Change ≥ +MID |
| Stable, n (%) | data | count_pct | 1 | Change between -MID and +MID |
| Deteriorated (change ≤ -MID), n (%) | data | count_pct | 1 | Change ≤ -MID |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|-------------|---------|
| count_pct | xxx (xx.x) | 87 (35.5) |

### Calculation Methods

- **MID**: Minimally important difference from published validation studies
- **Improved**: Change from baseline ≥ +MID (direction depends on scoring convention)
- **Stable**: Change between -MID and +MID (exclusive)
- **Deteriorated**: Change from baseline ≤ -MID
- **Assessment timepoint**: Typically at primary endpoint assessment visit
- **SAS**: PROC FREQ on derived responder categories

### Footnotes

1. ITT Population.
2. MID = minimally important difference; {value} points for {domain}.
3. Improved: change from baseline ≥ {MID}; Deteriorated: change from baseline ≤ -{MID}.

---

## Table: {Instrument} — Compliance/Completion Rates

| Setting | Value |
|---------|-------|
| Population | ITT |
| Source | ADQS |
| Orientation | PORTRAIT |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| {Visit 1}: Expected, n | data | count | 0 | Subjects still on study at visit |
| {Visit 1}: Completed, n (%) | data | count_pct | 0 | Subjects who returned evaluable questionnaire |
| {Visit 2}: Expected, n | data | count | 0 | |
| {Visit 2}: Completed, n (%) | data | count_pct | 0 | |

### Calculation Methods

- **Expected**: Subjects still on study at the scheduled assessment visit (not discontinued)
- **Completed**: Subjects who returned an evaluable questionnaire at the visit
- **Completion rate**: 100 × Completed / Expected
- **SAS**: PROC FREQ; expected counts from ADSL visit windows

### Footnotes

1. ITT Population.
2. Expected: subjects still on study at the scheduled assessment visit.
3. Completed: subjects who returned an evaluable questionnaire.
