# Clinical Chemistry Summary Table

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADLB |
| Orientation | LANDSCAPE |
| Filter | SAFFL = 'Y', PARCAT1 = 'CHEMISTRY' |

## How to Read the Protocol for This Table

Read the protocol and SAP to extract:

1. **Chemistry parameters**: Look in the laboratory assessments section of the protocol for the list of clinical chemistry parameters collected. Include all parameters listed — do not omit any.
2. **Visit schedule**: Find the schedule of assessments table or visit schedule. Identify every visit where laboratory samples are collected. Include screening, all treatment period visits, maintenance period visits (if applicable), and end of treatment.
3. **Treatment periods**: Check if the study has multiple treatment periods (induction, maintenance, follow-up). Include visits from ALL periods where labs are collected.
4. **Normal ranges**: Reference ranges come from the central laboratory. The ADLB dataset contains ANRLO and ANRHI variables. Show ranges in the table using the standard notation for each parameter.
5. **Units**: Determine whether the protocol specifies SI units or conventional units. ADLB uses the AVALU variable.
6. **Grading**: Check if the protocol uses CTCAE grading for laboratory abnormalities. If so, note the version.
7. **Baseline definition**: Confirm the baseline definition — typically the last non-missing value prior to first dose of study drug (ABLFL = 'Y' in ADLB).

## Decision Rules

- If the SAP title says "by Visit" or "by Parameter and Visit": include rows for ALL scheduled assessment visits from the protocol visit schedule across ALL treatment periods.
- If the SAP title says "Actual and Change from Baseline" without "by Visit": show only Baseline, End of Treatment, and Change from Baseline.
- Every parameter block must show the SAME full set of visits. Do not truncate subsequent parameters.
- Do NOT include a Total column for lab tables.
- Change from Baseline rows appear only for post-baseline visits.

## Column Structure

| Column | Header | Align | Description |
|--------|--------|-------|-------------|
| 1 | Parameter (unit) / Normal Range | L | Parameter name on first row of block, normal range on second row |
| 2 | Visit | L | Visit name from the protocol schedule |
| 3 | Statistic | L | n, Mean, SD, Median, Min, Max |
| 4+ | One column per treatment arm | C | Using exact arm names with (N=xxx) |

No Total column for lab tables.

## Row Structure

All rows are flat (indent=0). The Parameter, Visit, and Statistic are separate columns — not nested indentation.

For each parameter block:

| Parameter (unit) | Visit | Statistic | Arm 1 | Arm 2 |
|-------------------|-------|-----------|-------|-------|
| Parameter Name (Unit) | | | | |
| xx-xx | Screening | n | xx | xx |
| | | Mean | xx.x | xx.x |
| | | SD | xx.x | xx.x |
| | | Median | xx.x | xx.x |
| | | Min, Max | xx-xx | xx-xx |
| | Visit 2 | n | xx | xx |
| | | Mean | xx.x | xx.x |
| | | SD | xx.x | xx.x |
| | | Median | xx.x | xx.x |
| | | Min, Max | xx-xx | xx-xx |
| | Visit 2 - CFB | n | xx | xx |
| | | Mean | xx.x | xx.x |
| | | SD | xx.x | xx.x |
| | | Median | xx.x | xx.x |
| | | Min, Max | xx-xx | xx-xx |
| (spacer) | | | | |

## Calculation Methods

- Descriptive: PROC MEANS / PROC UNIVARIATE by AVISIT and treatment
- Baseline: Last non-missing value prior to first dose (ABLFL = 'Y')
- Change from baseline: AVAL - BASE (CHG variable in ADLB)
- Units: SI units throughout (unless protocol specifies conventional)
- Visits: Summarized by scheduled analysis visit (AVISIT)
- Visit windows: Apply windowing rules from the SAP if defined; otherwise use AVISIT as-is

## Footnotes

1. Safety Population defined as {full definition from protocol}.
2. Baseline is defined as the last non-missing value prior to first dose of study drug.
3. Table structure repeats for all clinical chemistry parameters: {list all parameters from protocol}.
4. Change from baseline = post-baseline value minus baseline value.
5. SI units used throughout.
6. Visit window definitions per SAP (if defined).
7. Abbreviations as applicable.

## Programming Notes

Source: ADLB. Filter: SAFFL = 'Y', PARCAT1 = 'CHEMISTRY'. PARAMCD for parameter, AVISIT for visit column, ABLFL = 'Y' for baseline, CHG for change from baseline, BASE for baseline value, ANRLO/ANRHI for normal ranges.
