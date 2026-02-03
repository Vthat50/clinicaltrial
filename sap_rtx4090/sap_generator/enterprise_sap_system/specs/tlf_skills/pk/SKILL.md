---
name: Pharmacokinetics
ich_section: "14.4"
display_order: 9
version: "2.0.0"
---

# Pharmacokinetics

Only included when PK samples are collected.

## What Comes from the Protocol

- **Analyte name(s)**: e.g., bevacizumab, drug X
- **Sampling schedule**: nominal timepoints for concentration-time profiles
- **PK parameters of interest**: Cmax, AUC0-t, AUC0-inf, Tmax, t1/2, CL/F, Vd/F
- **Bioanalytical method**: assay LLOQ (lower limit of quantification)
- **Bioequivalence criteria**: [0.80, 1.25] for comparative studies
- **NCA or compartmental method**: typically NCA (non-compartmental analysis)

## Column Structure

- **Two-arm**: {Arm 1} | {Arm 2}
- **Single-arm**: {Drug Name}
- Arm names from `facts.arm_names[]`.

---

## Table: Plasma Drug Concentration by Visit - Summary Statistics

| Setting | Value |
|---------|-------|
| Population | PK Evaluable |
| Source | ADPC |
| Orientation | LANDSCAPE |
| Filter | PKFL = 'Y' |

### Rows

Repeat per timepoint (from protocol sampling schedule):

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| {Timepoint} | header | | 0 | Dynamic; one block per nominal timepoint |
| n | data | count | 1 | Subjects with non-missing result |
| Mean (SD) | data | mean_sd | 1 | Arithmetic mean |
| Median | data | median | 1 | |
| Min, Max | data | min_max | 1 | |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|------------|---------|
| mean_sd | xx.x (xx.xx) | 142.3 (45.67) |
| min_max | xx.x-xx.x | 23.1-298.4 |

### Calculation Methods

- **BLQ handling**: Concentrations below LLOQ set to zero for mean calculations
- **Descriptive statistics**: PROC MEANS / PROC UNIVARIATE
- **Pre-dose**: Samples within allowable window per protocol

### Footnotes

1. PK Evaluable Population: All subjects who received study treatment and had at least one evaluable PK sample.
2. Concentrations below the lower limit of quantification (BLQ) are set to zero for summary statistics.
3. Pre-dose samples collected within the allowable window per protocol.

### Figures

- **Mean Plasma Concentration-Time Profile**: Mean ± SD by treatment arm; linear and semi-log scales as separate panels. X-axis: Time (hours), Y-axis: Concentration.

---

## Table: PK Parameters - Summary Statistics

| Setting | Value |
|---------|-------|
| Population | PK Evaluable |
| Source | ADPP |
| Orientation | LANDSCAPE |
| Filter | PKFL = 'Y' |

### Rows

Repeat per PK parameter (Cmax, AUC0-t, AUC0-inf, Tmax, t1/2, CL/F, Vd/F — as applicable):

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| {Parameter} | header | | 0 | Dynamic; one block per PK parameter |
| n | data | count | 1 | |
| Mean (SD) | data | mean_sd | 1 | Arithmetic mean |
| CV% | data | percentage | 1 | Arithmetic coefficient of variation = 100 × SD / Mean |
| Median | data | median | 1 | For Tmax, use median only (not mean) |
| Min, Max | data | min_max | 1 | |
| Geometric Mean | data | mean | 1 | exp(mean of log-transformed values) |
| Geometric CV% | data | percentage | 1 | 100 × sqrt(exp(variance of log) − 1) |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|------------|---------|
| mean_sd | xxxx.x (xxxx.xx) | 1423.5 (456.78) |
| percentage | xx.x% | 32.1% |
| median | xxxx.x | 1289.4 |
| min_max | xxxx.x-xxxx.x | 234.1-3298.4 |
| mean (geometric) | xxxx.x | 1312.7 |

### Calculation Methods

- **Arithmetic CV%**: 100 × SD / Mean
- **Geometric Mean**: exp(mean of ln-transformed values)
- **Geometric CV%**: 100 × sqrt(exp(s² − 1)) where s² = variance of ln-transformed values
- **Tmax**: Summarized as median (min, max), NOT mean
- **NCA derivation**: Non-compartmental analysis using WinNonlin or equivalent
- **Cmax**: Maximum observed concentration (directly from concentration-time data)
- **AUC0-t**: Area under curve from time 0 to last measurable concentration (linear trapezoidal)
- **AUC0-inf**: AUC0-t + Clast/λz
- **t1/2**: 0.693 / λz (terminal elimination rate constant)
- **CL/F**: Dose / AUC0-inf (apparent clearance for extravascular)
- **Vd/F**: CL/F × t1/2 / 0.693 (apparent volume of distribution)

### Footnotes

1. PK Evaluable Population.
2. PK parameters derived using non-compartmental analysis.
3. Geometric statistics presented for log-normally distributed parameters.
4. Tmax presented as median (min, max).
5. Cmax = maximum observed concentration; AUC0-t = area under the curve from time 0 to last measurable concentration; AUC0-inf = area under the curve extrapolated to infinity; Tmax = time to Cmax; t1/2 = terminal elimination half-life; CL/F = apparent clearance; Vd/F = apparent volume of distribution.

---

## Table: Statistical Comparison of PK Parameters

Condition: Only for comparative PK studies (bioequivalence, biosimilar).

| Setting | Value |
|---------|-------|
| Population | PK Evaluable |
| Source | ADPP |
| Orientation | LANDSCAPE |
| Filter | PKFL = 'Y' |

### Rows

Repeat per parameter (Cmax, AUC0-t, AUC0-inf):

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| {Parameter} | header | | 0 | |
| Geometric LS Mean — {Arm 1} | data | fixed | 1 | Back-transformed |
| Geometric LS Mean — {Arm 2} | data | fixed | 1 | Back-transformed |
| Ratio (Test/Reference) | data | fixed | 1 | |
| 90% CI for Ratio | data | ratio_ci | 1 | Note: 90% CI, not 95% |

### Calculation Methods

- **ANOVA model**: Log-transformed data; treatment as fixed effect (plus sequence, period for crossover)
- **Back-transformation**: Geometric LS means = exp(LS mean on log scale)
- **Ratio**: Geometric LS mean(Test) / Geometric LS mean(Reference)
- **90% CI**: Back-transformed from log scale; corresponds to two one-sided tests at α = 0.05
- **BE conclusion**: Bioequivalence if 90% CI entirely within [0.80, 1.25]

### Footnotes

1. PK Evaluable Population.
2. Analysis performed on log-transformed data using ANOVA model with treatment as fixed effect.
3. Geometric LS means and 90% CI back-transformed from log scale.
4. Bioequivalence concluded if 90% CI for the ratio is entirely within [0.80, 1.25].
