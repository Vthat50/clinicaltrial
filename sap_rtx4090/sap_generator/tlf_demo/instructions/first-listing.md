# First Listing from the SAP Index

Generates the first listing entry from the SAP TLF index. The listing content varies by protocol.

## How to Read the Protocol for This Listing

Read the protocol, SAP, and the listing title to determine:

1. **Source dataset**: The listing title indicates the clinical domain. Map to the correct ADaM dataset:
   - Tumor response / efficacy assessments → ADRS or ADTTE
   - Subject disposition → ADSL
   - Adverse events → ADAE
   - Laboratory results → ADLB
   - Vital signs → ADVS
   - ECG → ADEG
   - Concomitant medications → ADCM
   - Exposure / dosing → ADEX
   - PK concentrations → ADPC
   - Quality of life / PRO → ADQS
2. **Column variables**: Read the listing title to determine what data is being listed. Then identify the ADaM variables that map to each column. Include all variables a statistical programmer would need to produce the listing.
3. **Population**: Use the population from the SAP index entry. Read the full population definition from the protocol.
4. **Sort order**: Derive from the listing content. Typically sorted by Subject ID first, then by the primary grouping variable, then by date or visit.
5. **Page break**: Determine the primary grouping variable. Usually Subject ID for patient-level listings.
6. **Assessment criteria**: If the listing involves clinical assessments (tumor response, disease activity), find the criteria name and version from the protocol.
7. **Review type**: If the listing involves imaging or central review, note whether it is investigator assessment, central review, or both.

## Decision Rules

- Always include Subject ID and Treatment Group as the first two columns.
- Include date variables (assessment date, visit date) when available — these are critical for programming.
- Include both coded and verbatim terms when the listing involves coded data (adverse events, medications).
- If the protocol specifies both local and central assessments, include a column indicating the reviewer type.
- Include baseline values and change from baseline when the listing shows longitudinal data.

## Settings

| Setting | Value |
|---------|-------|
| Population | From SAP index (ITT or Safety) |
| Source | Determined from listing content |
| Orientation | LANDSCAPE |

## Column Structure

All listings use a flat column layout with one column per variable. No treatment arm nesting. Variables are determined from the listing title and protocol content.

## Required Fields

| Field | Description |
|-------|-------------|
| `title` | Full descriptive title including population name in parentheses |
| `type` | Always "listing" |
| `population` | Analysis population name from the SAP index |
| `section` | ICH E3 section number (16.2.x format) |
| `variables` | Array of column header strings |
| `source` | ADaM dataset name |
| `orientation` | LANDSCAPE |
| `sort_order` | Sort specification derived from the listing content and protocol |
| `page_break_by` | Primary grouping variable for page breaks |
| `footnotes` | Array of footnote strings |
| `programming_notes` | ADaM variable mappings for columns and filtering criteria |

## Footnotes

1. Population definition with the full definition from the protocol/SAP
2. Sort order description
3. Relevant methodology or assessment criteria from the protocol
4. Abbreviation definitions

## Common Listing Types

### Efficacy Data

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment | TRT01A | |
| Visit | AVISIT | |
| Assessment Date | ADT | |
| Endpoint Value | AVAL | |
| Baseline Value | BASE | |
| Change from Baseline | CHG | |
| Response Category | AVALC | For binary/categorical endpoints |

Source: ADRS, ADEFF, or ADTTE depending on endpoint type.

### Subject Disposition

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Site | SITEID | |
| Treatment | TRT01A | Actual treatment received |
| Date of Randomization | RANDDT | |
| Date of First Dose | TRTSDT | |
| Date of Last Dose | TRTEDT | |
| Completion Status | EOSSTT | |
| Reason for Discontinuation | DCSREAS | |
| Date of Discontinuation | DCSDT | |

Source: ADSL.

### Adverse Events

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment | TRT01A | |
| System Organ Class | AEBODSYS | MedDRA SOC |
| Preferred Term | AEDECOD | MedDRA PT |
| Verbatim Term | AETERM | As reported by investigator |
| Start Date | AESTDT | |
| End Date | AEENDT | |
| Duration (days) | AEDUR | |
| Severity/Grade | AETOXGR | CTCAE grade |
| Serious | AESER | Y/N |
| Relationship | AEREL | Investigator assessment |
| Action Taken | AEACN | |
| Outcome | AEOUT | |

Source: ADAE.
