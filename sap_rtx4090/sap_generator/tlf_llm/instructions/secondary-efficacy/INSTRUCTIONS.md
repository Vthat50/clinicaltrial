---
name: Secondary Efficacy
ich_section: "14.2"
display_order: 4
types: [efficacy_binary, efficacy_continuous, efficacy_tte]
condition: always
---

You are generating the secondary and exploratory efficacy endpoint table and figure shells for ICH E3 Section 14.2.

## What to Look For in the Protocol

Read the protocol to identify:
- All secondary endpoints — name, type, analysis method
- All exploratory/tertiary endpoints
- Whether endpoints are analyzed at multiple timepoints
- Any endpoints from a hierarchical testing strategy not covered by primary efficacy
- Patient-reported outcomes that are efficacy endpoints (not QoL instruments covered separately)
- Biomarker endpoints
- Duration of response, time to response (if applicable)

## Tables Per Secondary Endpoint

Generate tables for each secondary and exploratory endpoint, following the same pattern as primary efficacy:

### Binary Endpoints
- Response rate summary with treatment comparison

### Continuous Endpoints
- Change from baseline summary by visit
- Analysis model results

### Time-to-Event Endpoints
- Time-to-event summary table with the SAME row structure as primary efficacy TTE tables: number of events, number censored, median with CI, 25th/75th percentiles, censoring reasons breakdown, hazard ratio with CI, p-value, and Kaplan-Meier estimates at ALL landmark timepoints from the protocol assessment schedule. Do NOT omit any of these rows.

Secondary TTE tables are simpler than primary only in that they do not need sensitivity analysis tables or subgroup analyses — but the main summary table itself must contain ALL standard TTE rows.

## Figures

- **Kaplan-Meier Plot**: For time-to-event secondary endpoints (only the key ones — not every secondary TTE needs a KM plot)
- **Change from Baseline Over Time**: Line plot for key continuous endpoints measured longitudinally

## Design-Type Guidance

Design type affects column structure:
- Randomized: columns per treatment arm + total
- Single-arm: overall column only
- Crossover: generate separate tables per period; use period-specific baselines for shift tables
- Dose-escalation: group by dose/cohort

## IMPORTANT: Avoid Duplication

Do NOT generate tables for endpoints already covered in the primary-efficacy domain. Check the "Already Generated" section and skip any overlapping endpoints.

## CRITICAL: Multiple Populations — Full Cross-Product Required

If the protocol defines N analysis populations for efficacy, you must generate N complete sets of secondary efficacy tables — one full set per population. Every endpoint appears in every population. Do not mix — if an endpoint has a table in one population, it must have a table in all populations. The total number of secondary efficacy tables must equal (number of endpoints × number of populations). Each table title must include the population name.

Read the protocol exactly. When it lists requirements, include ALL of them. Do not skip, alternate, or combine unless explicitly told to. When the protocol specifies analyses across multiple populations, create separate outputs for EVERY combination of analysis × population. Do not alternate.

Before finalizing, count: if you have P populations and E endpoints, you must have at least P × E tables. If your count is less, you are missing tables.

## CRITICAL: Multiple Study Periods

If the protocol assesses secondary endpoints across multiple treatment periods, generate period-specific tables for each.

## CRITICAL: Every Endpoint Gets a Table

Generate at least one summary table for EVERY secondary and exploratory endpoint named in the protocol. Do not skip any. Time-to-event endpoints need both a summary table AND a KM figure. If the protocol specifies that the same endpoint is evaluated by more than one reviewer or method, each reviewer counts as a separate endpoint for purposes of the population cross-product.

## Nominal P-Values

Secondary endpoint p-values are nominal (not adjusted for multiplicity) unless the protocol specifies a hierarchical testing strategy that includes secondary endpoints. If nominal, state in the footnotes that p-values are nominal and not adjusted for multiplicity. If the protocol includes secondary endpoints in a formal testing hierarchy, state the adjustment method in the footnotes.

## Output Format — Full Shell Specification

Each table must include complete columns, rows, footnotes, source, and orientation. See the system prompt for the full JSON schema. Include `analysis_method` and `endpoint` fields.

Follow the EXACT same row guidance as primary-efficacy for all endpoint types (binary, continuous, time-to-event). Every TTE table must have ALL standard rows: events, censored, median with CI, quartiles, censoring reasons, hazard ratio with CI, p-value, and landmark estimates. The only simplification versus primary is that secondary endpoints do not need sensitivity analysis tables or subgroup tables.

Include the endpoint name in the table title. Include the statistical method in `analysis_method`.

Types: "efficacy_binary", "efficacy_continuous", "efficacy_tte".
Source: ADTTE (TTE), ADRS/ADEFF (binary/continuous). Section: "14.2". Orientation: PORTRAIT.
