---
name: Primary Efficacy
ich_section: "14.2"
display_order: 3
types: [efficacy_binary, efficacy_continuous, efficacy_tte, subgroup]
condition: always
---

You are generating the primary efficacy endpoint table and figure shells for ICH E3 Section 14.2.

## What to Look For in the Protocol

Read the protocol to identify:
- The primary endpoint(s) — name, type (binary, continuous, time-to-event, ordinal, count)
- Statistical analysis method for each primary endpoint
- Landmark timepoints defined in the protocol
- Covariates and stratification factors used in the primary analysis model
- Non-inferiority/equivalence margin if applicable
- Multiplicity adjustment method
- Response criteria definitions
- Sensitivity analyses described for primary endpoints
- Censoring rules for time-to-event endpoints

## Tables Per Primary Endpoint

For EACH primary endpoint, generate:

### Binary Endpoints
- Response rate table with treatment comparison (CI, p-value)
- Response by visit (if longitudinal assessment)

### Continuous Endpoints
- Summary of observed values and change from baseline by visit
- Primary analysis model results (LS means, difference, CI, p-value)

### Time-to-Event Endpoints
- Time-to-event summary (events, median, 95% CI per arm)
- Hazard ratio table from Cox model (HR, CI, p-value)
- Kaplan-Meier estimates at key timepoints

### Sensitivity Analyses
- One table per sensitivity analysis described in the protocol for primary endpoint(s)

### Subgroup Analysis (Primary Endpoint Only)
- Forest plot of treatment effect by pre-specified subgroups
- Subgroup analysis table if protocol pre-specifies subgroups for primary

## Figures Per Primary Endpoint

- **Kaplan-Meier Plot**: For each time-to-event primary endpoint
- **Forest Plot**: For subgroup analysis of primary endpoint
- **Waterfall Plot**: If the protocol measures individual best response or best percent change
- **Responder Bar Chart**: For binary endpoints across visits
- **Mean Over Time Plot**: For continuous endpoints measured at multiple timepoints, include a mean (± SE or CI) over time line plot by treatment arm
- **Individual Subject Profiles**: If the protocol specifies or if the endpoint warrants individual-level visualization
- **Histogram / Distribution Plot**: If the protocol describes distribution analysis of an endpoint or if a histogram is implied by the analysis plan

## Design-Type Guidance

Design type affects column structure:
- Randomized: columns per treatment arm + total
- Single-arm: overall column only
- Crossover: generate separate tables per period; use period-specific baselines for shift tables
- Dose-escalation: group by dose/cohort

## CRITICAL: Multiple Populations — Full Cross-Product Required

Generate separate tables for EACH analysis population the protocol defines for efficacy. Every endpoint appears in every population. Do not mix — if an endpoint has a table in one population, it must have a table in all populations. If the protocol defines N populations, you must generate N complete sets of primary efficacy tables — one full set per population. Each table title must include the population name.

Read the protocol exactly. When it lists requirements, include ALL of them. Do not skip, alternate, or combine unless explicitly told to. When the protocol specifies analyses across multiple populations, create separate outputs for EVERY combination of analysis × population. Do not alternate.

Before finalizing, count: if you have P populations and E endpoints, you must have at least P × E primary efficacy tables (plus sensitivity/subgroup tables). If your count is less, you are missing tables.

## CRITICAL: Multiple Study Periods

If the protocol has multiple treatment periods where efficacy is assessed separately, generate separate efficacy tables for EACH period AND for the overall/whole study period. These are separate tables with different titles.

## CRITICAL: Equivalence/Non-Inferiority/Biosimilar

For equivalence, non-inferiority, or biosimilar studies, also include:
- Treatment difference or ratio with confidence interval relative to the margin
- Sensitivity analyses described in the protocol
- Covariate-adjusted model results if the protocol specifies a regression model

## Multiplicity

If the protocol specifies a multiplicity adjustment method for primary endpoints, the adjustment method and the adjusted significance level must appear in the table footnotes. If co-primary endpoints are used where success on all endpoints is required, state this in the footnotes.

## Censoring

For time-to-event endpoints, the footnotes must state the censoring rules used in the analysis. If the protocol defines specific censoring rules, use those. The date of last known alive or last assessment must be identified as the censoring date convention.

## Output Format — Full Shell Specification

Each table must include complete columns, rows, footnotes, source, and orientation. See the system prompt for the full JSON schema. Include `analysis_method` and `endpoint` fields.

**Row guidance by endpoint type:**

*Binary endpoint (efficacy_binary):*
- Data: Responders, n (count_pct) per arm
- Data: Non-responders, n (count_pct)
- Spacer
- Data: Response rate difference (diff_ci)
- Data: Odds ratio (ratio_ci) — if logistic regression
- Data: p-value (p_value)

*Time-to-event (efficacy_tte):*
- Data: Number of events, n (%) (events_rate)
- Data: Number censored, n (%) (events_rate)
- Data: Median time (median_ci)
- Data: 25th percentile (q1_q3)
- Data: 75th percentile (q1_q3)
- Spacer
- Header: "Censoring Reasons" → one sub-row per censoring reason defined in the protocol (count_pct, indent=1)
- Spacer
- Data: Hazard ratio (hr_ci)
- Data: p-value (p_value)
- Spacer
- Header: "Kaplan-Meier Estimates at Landmark Timepoints" → one sub-row per landmark timepoint defined or implied by the protocol assessment schedule (ci_95, indent=1). Include ALL timepoints at which subjects are assessed.

*Continuous endpoint (efficacy_continuous):*
- Header: "Baseline" → n, Mean, SD (indent=1)
- Header: "Change from Baseline" → n, LS Mean, SE, LS Mean Difference, 95% CI, p-value (indent=1)

Include the endpoint name in the table title. Include the statistical method in `analysis_method`.

**Footnotes must include:** population definition, analysis method with covariates, multiplicity adjustment if applicable.

Types: "efficacy_binary", "efficacy_continuous", "efficacy_tte", "subgroup".
Source: ADTTE (time-to-event), ADRS/ADEFF (binary/continuous). Section: "14.2". Orientation: PORTRAIT.
