---
name: Figures
ich_section: varies
display_order: 18
version: "2.0.0"
---

# Figures

Figures are generated based on the endpoints, assessments, and study design. Each figure type has specific inclusion conditions.

## What Comes from the Protocol

- **Endpoints**: which time-to-event, binary, and continuous endpoints require figures
- **Treatment arms**: arm names for legend labels and curve colors
- **Assessment schedule**: visit windows for time axes
- **Tumor assessment criteria**: RECIST version for waterfall/swimmer plots (oncology)
- **QoL instruments**: for QoL score over time plots
- **PK sampling schedule**: for concentration-time profiles

---

## Figure: Kaplan-Meier Plot — {Endpoint Name}

Condition: One per time-to-event endpoint.

| Setting | Value |
|---------|-------|
| Population | Per endpoint definition (ITT or PP) |
| Source | ADTTE |
| Orientation | LANDSCAPE |

### Elements

| Element | Description |
|---------|-------------|
| Axes | X-axis: Time (months). Y-axis: Event-free probability (0 to 1.0). |
| Curves | One curve per treatment arm, distinguished by color and line style. |
| Censoring marks | Tick marks on curve at each censoring time. |
| At-risk table | Number at risk per arm displayed below x-axis at regular intervals. |
| Median lines | Dashed horizontal line at 0.5, vertical to x-axis at median per arm. |
| Legend | Treatment arm names with corresponding line style/color. |
| Annotation | HR [95% CI] and p-value displayed on the plot. |

### Calculation Methods

- **KM curves**: PROC LIFETEST with ODS GRAPHICS
- **Number at risk**: Count at each tick mark interval (e.g., every 3 or 6 months)
- **Censoring**: Tick marks at censored observations on the step function
- **Median lines**: Dashed from probability 0.5 to the x-axis at each arm's median

### Footnotes

1. {Population} Population.
2. Kaplan-Meier method. Tick marks indicate censored observations.
3. Number at risk shown at {interval} month intervals.

---

## Figure: Forest Plot — Subgroup Analysis of {Endpoint Name}

Condition: One per primary/key secondary endpoint with pre-specified subgroup analyses.

| Setting | Value |
|---------|-------|
| Population | ITT |
| Source | ADTTE, ADRS, or ADEFF |
| Orientation | LANDSCAPE |

### Elements

| Element | Description |
|---------|-------------|
| Rows | One row per subgroup, grouped by subgroup variable. |
| Point estimate | Diamond or square at the treatment effect estimate (HR or difference). |
| CI bars | Horizontal bars showing 95% CI. |
| Reference line | Vertical line at HR=1.0 (time-to-event) or difference=0 (binary/continuous). |
| n per arm | Displayed to the left of each row. |
| Estimate and CI | Numeric values displayed to the right of each row. |
| Interaction p | Interaction p-value per subgroup variable. |
| Favors labels | "Favors {Arm 1}" and "Favors {Arm 2}" below the plot area. |

### Calculation Methods

- **Treatment effect**: Unstratified Cox HR (TTE) or risk difference (binary) within each subgroup
- **95% CI**: Wald-type CI from the model within each subgroup
- **Interaction p-value**: From treatment×subgroup interaction term in the overall model
- **SAS**: PROC SGPLOT or custom macro; data from subgroup analysis tables

### Footnotes

1. ITT Population.
2. Treatment effect and 95% CI within each subgroup.
3. Interaction p-value from treatment-by-subgroup interaction test.
4. Subgroup analyses are exploratory; not adjusted for multiplicity.

---

## Figure: Waterfall Plot — Best Change from Baseline in Tumor Size

Condition: Oncology studies with measurable disease (RECIST).

| Setting | Value |
|---------|-------|
| Population | ITT (subjects with baseline and ≥1 post-baseline tumor assessment) |
| Source | ADRS or ADTR |
| Orientation | LANDSCAPE |

### Elements

| Element | Description |
|---------|-------------|
| Bars | One bar per subject, sorted by best percentage change (ascending). |
| X-axis | Subjects (ordered). |
| Y-axis | Best percentage change from baseline in sum of target lesion diameters (%). |
| Reference lines | Horizontal lines at -30% (PR threshold) and +20% (PD threshold). |
| Color coding | Bars colored by best overall response (CR, PR, SD, PD). |
| Legend | Response category colors. |

### Calculation Methods

- **Best percentage change**: Minimum percentage change across all post-baseline assessments per subject
- **Target lesion sum**: Sum of longest diameters of target lesions per RECIST v1.1
- **Response categories**: From best overall response (PARAMCD = 'BOR' in ADRS)
- **Truncation**: Bars may be truncated at +100% for subjects with large increases

### Footnotes

1. ITT Population with measurable disease at baseline.
2. Best percentage change from baseline in sum of longest diameters of target lesions.
3. Reference lines: -30% (partial response threshold), +20% (progressive disease threshold) per RECIST v1.1.

---

## Figure: Swimmer Plot — {Endpoint Name}

Condition: Oncology studies with time-to-event endpoints.

| Setting | Value |
|---------|-------|
| Population | ITT |
| Source | ADTTE, ADRS |
| Orientation | LANDSCAPE |

### Elements

| Element | Description |
|---------|-------------|
| Bars | One horizontal bar per subject, length = time on study. |
| Y-axis | Subjects, sorted by duration on study (longest at top). |
| X-axis | Time (weeks or months). |
| Symbols | Response events marked on bars (onset of response, progression, death). |
| Color coding | Bar color by treatment arm. |
| Ongoing marker | Arrow at end of bar for subjects still on treatment. |

### Calculation Methods

- **Bar length**: Time from randomization to last assessment or event
- **Response symbols**: From ADRS — dates of CR, PR, PD
- **Ongoing**: Subjects without event and still on study

### Footnotes

1. ITT Population.
2. Each bar represents one subject. Length = time from randomization to last assessment or event.
3. Symbols indicate response events per RECIST v1.1.

---

## Figure: Mean Change from Baseline Over Time — {Endpoint Name}

Condition: One per primary continuous endpoint.

| Setting | Value |
|---------|-------|
| Population | Per endpoint definition |
| Source | ADEFF |
| Orientation | LANDSCAPE |

### Elements

| Element | Description |
|---------|-------------|
| X-axis | Visit / time. |
| Y-axis | Mean change from baseline (with error bars). |
| Lines | One line per treatment arm, distinguished by color/style. |
| Error bars | ± SE or 95% CI at each timepoint. |
| Legend | Treatment arm names. |

### Calculation Methods

- **LS Mean**: From MMRM LSMEANS statement at each visit
- **Error bars**: ± SE from the MMRM model (or ± 95% CI)
- **SAS**: PROC SGPLOT with SERIES and SCATTER; data from MMRM output

### Footnotes

1. {Population} Population.
2. Mean ± SE at each scheduled visit.
3. Baseline = last value prior to first dose.

---

## Figure: Mean Plasma Concentration-Time Profile

Condition: Only when PK samples are collected.

| Setting | Value |
|---------|-------|
| Population | PK |
| Source | ADPC |
| Orientation | LANDSCAPE |

### Elements

| Element | Description |
|---------|-------------|
| X-axis | Time after dose (hours). |
| Y-axis | Mean plasma concentration (log-linear and linear scales, separate panels). |
| Lines | One line per treatment arm. |
| Error bars | ± SD at each nominal timepoint. |
| Legend | Treatment arm names. |

### Calculation Methods

- **Concentration summary**: Mean ± SD at each nominal sampling time from ADPC
- **BLQ handling**: Below LLOQ set to zero for mean calculations
- **Two panels**: Linear scale and semi-log (y-axis log10) scale
- **SAS**: PROC SGPANEL or PROC SGPLOT

### Footnotes

1. PK Population.
2. Mean ± SD at each nominal sampling time.
3. BLQ values set to zero for mean calculations.

---

## Figure: CONSORT Flow Diagram

Condition: Randomized studies.

| Setting | Value |
|---------|-------|
| Population | All Screened |
| Source | ADSL |
| Orientation | PORTRAIT |

### Elements

| Element | Description |
|---------|-------------|
| Boxes | Enrollment → Screening → Randomization → Treatment Arms → Completed/Discontinued. |
| Numbers | n at each stage. |
| Discontinuation reasons | Listed per arm with n for each reason. |
| Population boxes | ITT, PP, Safety population counts per arm. |

### Footnotes

1. All screened subjects.
2. Reasons for screen failure and discontinuation shown per arm.

---

## Figure: Mean Laboratory Values Over Time

Condition: When lab data is collected. One plot per selected parameter.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADLB |
| Orientation | LANDSCAPE |

### Elements

| Element | Description |
|---------|-------------|
| X-axis | Visit / time. |
| Y-axis | Mean value (SI units). |
| Lines | One line per treatment arm. |
| Error bars | ± SE at each visit. |
| Reference lines | Upper and lower limits of normal (horizontal dashed lines). |
| Legend | Treatment arm names. |

### Calculation Methods

- **Mean values**: PROC MEANS by AVISIT and treatment
- **Reference lines**: ANRLO and ANRHI from central laboratory
- **Parameters**: Selected parameters of clinical interest (e.g., ALT, AST, Creatinine, Hemoglobin)

### Footnotes

1. Safety Population.
2. Mean ± SE by scheduled visit.
3. Dashed lines represent upper and lower limits of normal per central laboratory.

---

## Figure: QoL Score Over Time — {Instrument}

Condition: One per QoL/PRO instrument.

| Setting | Value |
|---------|-------|
| Population | ITT |
| Source | ADQS |
| Orientation | LANDSCAPE |

### Elements

| Element | Description |
|---------|-------------|
| X-axis | Visit / time. |
| Y-axis | Mean score (with error bars). |
| Lines | One line per treatment arm. |
| Error bars | ± SE at each visit. |
| MID reference | Horizontal dashed line at baseline ± MID (if applicable). |

### Calculation Methods

- **Mean scores**: LS mean from MMRM (if applicable) or observed mean from PROC MEANS
- **Error bars**: ± SE
- **MID line**: Dashed line at baseline mean ± MID threshold

### Footnotes

1. ITT Population.
2. Mean ± SE by scheduled assessment visit.
3. Higher scores indicate {better/worse} outcome per scoring convention.

---

## Figure: Tipping Point Analysis — {Endpoint Name}

Condition: Biosimilar/equivalence studies, primary efficacy endpoint.

| Setting | Value |
|---------|-------|
| Population | ITT |
| Source | ADRS or ADEFF |
| Orientation | LANDSCAPE |

### Elements

| Element | Description |
|---------|-------------|
| X-axis | Imputed response rate for missing subjects in {Arm 1}. |
| Y-axis | Imputed response rate for missing subjects in {Arm 2}. |
| Shaded region | Combinations where equivalence conclusion holds. |
| Observed point | Marker at the observed response rates. |
| Boundary | Equivalence margin boundary. |

### Calculation Methods

- **Tipping point**: Systematically vary imputed values for missing subjects and re-evaluate equivalence
- **Equivalence**: Conclusion holds if risk difference CI within margins at each imputed combination
- **Observed**: Marker at the actual observed rates

### Footnotes

1. ITT Population.
2. Tipping point analysis assessing sensitivity of equivalence conclusion to missing data assumptions.
3. Equivalence margin: [{lower}, {upper}] for the risk ratio.
