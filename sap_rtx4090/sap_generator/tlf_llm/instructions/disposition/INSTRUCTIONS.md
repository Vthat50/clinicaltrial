---
name: Disposition
ich_section: "14.1"
display_order: 1
types: [disposition, screening_failures]
condition: always
---

You are generating the subject disposition table and figure shells for ICH E3 Section 14.1.

## What to Look For in the Protocol

Read the protocol to identify:
- Study periods and transitions (screening → randomization → treatment → follow-up)
- Reasons for discontinuation listed in the protocol
- Whether there is a screening period with screening failure criteria
- Whether there is a run-in or washout period
- Whether the study has multiple treatment periods

## Denominator Conventions

Percentages for screening failures use the number screened as the denominator. Percentages from randomization onward use the number randomized per arm as the denominator. Each discontinued subject must have exactly one primary reason for discontinuation. The sum of all discontinuation reasons must equal the total number of discontinued subjects.

## Hierarchical Structure

Disposition tables follow a hierarchical count flow: Screened → Randomized/Enrolled → Treated → Completed → Discontinued. Each level must be a subset of the level above it.

## Mandatory Tables (every study)

- **Subject Disposition**: Counts of subjects screened, randomized/enrolled, completed, discontinued with reasons. One table that summarizes the full flow.

## Conditional Tables

- **Screening Failures**: Include if the protocol describes a screening period. Summarize reasons for screen failure.
- **Period-Specific Disposition**: If the study has distinct treatment periods, include a SEPARATE disposition table for EACH period.
- **Randomization Stratification Factors**: If the study is stratified, include a table summarizing the distribution of stratification factors by treatment arm.
- **Protocol Deviations Summary**: Major protocol deviations by category and treatment arm.
- **Subject Enrollment by Country**: For multicenter studies, include a table of subject counts by country and treatment arm.
- **Subject Enrollment by Country and Center**: For multicenter studies, include a table of subject counts broken down by country and investigational site/center.

## Figures

- **CONSORT Flow Diagram**: Include for randomized studies. Not needed for single-arm studies.

## Design-Type Guidance

Design type affects column structure:
- Randomized: columns per treatment arm + total
- Single-arm: overall column only
- Crossover: generate separate tables per period; use period-specific baselines for shift tables
- Dose-escalation: group by dose/cohort

## Population

Disposition tables use the **Screened** or **Enrolled** population (whichever is broader).

## Output Format — Full Shell Specification

Each table must include complete columns, rows, footnotes, source, and orientation. See the system prompt for the full JSON schema.

**Domain-specific row guidance for disposition tables:**
- Header row: "Subjects" (bold)
- Data rows: Screened (count), Screen Failures (count_pct), Randomized/Enrolled (count), Treated (count), Completed Study Treatment (count_pct), Discontinued Study Treatment (count_pct)
- Spacer row
- Header row: "Reasons for Discontinuation" (bold)
- Data rows: One per protocol-defined discontinuation reason (count_pct, indent=1)
- Spacer row
- Header row: "Analysis Populations" (bold)
- Data rows: One per protocol-defined analysis population (count, indent=1)

Types: "disposition" for disposition tables, "screening_failures" for screening failure tables.
Source: ADSL. Section: "14.1". Orientation: PORTRAIT.
