---
name: Demographics & Baseline
ich_section: "14.1"
display_order: 2
types: [demographics, baseline, medical_history, disease_characteristics]
condition: always
---

You are generating the demographics and baseline characteristics table shells for ICH E3 Section 14.1.

## What to Look For in the Protocol

Read the protocol to identify:
- Demographic variables collected (age, sex, race, ethnicity, weight, height, BMI)
- Inclusion/exclusion criteria that define the study population characteristics
- Disease-specific baseline characteristics
- Medical history collection requirements
- Prior/concomitant medication categories relevant at baseline
- Stratification factors (often used as baseline summary variables)
- Any protocol-specified subgroups based on baseline characteristics

## Variable Presentation Rules

Categorical variables are presented as count and percentage. Continuous variables are presented as n, mean, SD, median, min, and max. Demographics tables are descriptive only — do not include p-values or statistical tests unless the protocol explicitly requests them.

## Column Structure

For randomized studies, include one column per treatment arm plus a Total column. The Total column pools all randomized subjects regardless of treatment assignment. For single-arm studies, use a single Overall column with no Total column.

## Completeness Check

Every variable listed in the protocol's stratification factors, inclusion/exclusion criteria, and schedule of assessments baseline visit must appear in the demographics or baseline characteristics table. If the protocol collects a baseline measurement, it must appear in either the demographics table or the baseline characteristics table.

## Mandatory Tables (every study)

- **Demographics and Baseline Characteristics**: Age, sex, race, ethnicity, and other demographic variables. Continuous variables summarized with N, mean, SD, median, min, max. Categorical variables with counts and percentages.

## Conditional Tables

- **Disease Characteristics at Baseline**: Include when the protocol describes disease-specific baseline measures. Use the actual disease-specific variables from the protocol.
- **Medical History**: Include if medical history is collected (almost always yes).
- **Baseline Disease Activity / Severity**: For studies with disease severity scales at baseline.

## Design-Type Guidance

Design type affects column structure:
- Randomized: columns per treatment arm + total
- Single-arm: overall column only
- Crossover: generate separate tables per period; use period-specific baselines for shift tables
- Dose-escalation: group by dose/cohort

## CRITICAL: Multiple Populations

If the protocol defines that demographics should be summarized for more than one analysis population, generate a SEPARATE demographics table for EACH population. Each table title must include the population name.

## Population

Demographics/baseline tables use the **ITT/FAS** or **Enrolled/Randomized** population (the broadest analysis population). If the protocol also specifies demographics for other populations (Safety, Per-Protocol), generate separate tables for those as well.

## Output Format — Full Shell Specification

Each table must include complete columns, rows, footnotes, source, and orientation. See the system prompt for the full JSON schema.

**Domain-specific row guidance for demographics tables:**
- Header row: "Age (years)" (bold) → sub-rows: n (count), Mean (mean), SD (sd), Median (median), Min (min), Max (max)
- Spacer row
- Header row: "Age group, n (%)" (bold) → sub-rows: one per protocol-defined age stratum (count_pct, indent=1)
- Spacer row
- Header row: "Sex, n (%)" (bold) → sub-rows: Male, Female (count_pct, indent=1)
- Spacer row
- Header row: "Race, n (%)" (bold) → sub-rows per protocol races (count_pct, indent=1)
- Spacer row
- Header row: "Ethnicity, n (%)" (bold) → sub-rows: per protocol-defined ethnicity categories (count_pct, indent=1)
- Spacer row
- Header row: "Weight (kg)" (bold) → sub-rows with descriptive stats (mean, sd, median, min, max)
- Add disease-specific baseline characteristics from the protocol as additional sections

For **disease_characteristics** tables, use the actual disease-specific variables from the protocol.

Types: "demographics", "baseline", "medical_history", "disease_characteristics".
Source: ADSL. Section: "14.1". Orientation: PORTRAIT.
