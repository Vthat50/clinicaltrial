# Clinical Chemistry Listing

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADLB |
| Orientation | LANDSCAPE |
| Filter | PARCAT1 = 'CHEMISTRY' |

## How to Read the Protocol for This Listing

Read the protocol to determine:

1. **Chemistry parameters**: Identify all clinical chemistry parameters collected in the study. The laboratory assessments section lists them. The listing includes all parameters — not a subset.
2. **CTCAE grading**: Check if the protocol applies CTCAE toxicity grading to laboratory values. If yes, include the CTCAE Grade column and note the version in footnotes. If the protocol does not mention CTCAE grading for labs, the column can be omitted or marked as not applicable.
3. **Clinically significant flag**: Check if the protocol requires investigators to assess clinical significance of abnormal lab values. If yes, include the Clinically Significant column.
4. **Central vs local lab**: Determine whether laboratory samples are processed by a central laboratory, local laboratories, or both. This affects the reference range source and should be noted in footnotes.
5. **Unit system**: Check whether the protocol specifies SI units or conventional units. The listing should match the protocol specification.

## Decision Rules

- Include ALL visits where chemistry labs are collected — not just a subset.
- Include both actual values and change from baseline.
- Reference ranges come from the central laboratory unless the protocol specifies otherwise.
- If CTCAE grading is not used in the protocol, the CTCAE Grade column can be excluded or noted as not applicable.
- Sort by Subject ID first, then Parameter, then Visit Date to enable review of longitudinal trends per subject per parameter.

## Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment Group | TRT01A | |
| Parameter | PARAM | |
| Baseline Value | BASE | |
| Unit | AVALU | SI units |
| Visit | AVISIT | |
| Visit Date | ADT | |
| Result | AVAL | |
| Change from Baseline | CHG | AVAL - BASE |
| CTCAE Grade | ATOXGR | If CTCAE grading applied |
| Reference Range Low | ANRLO | Per central lab |
| Reference Range High | ANRHI | Per central lab |
| Clinically Significant | CSSIG | Y/N |

## Sort Order

Sorted by Subject ID, Parameter, Visit Date.

## Page Break

Page break by Subject ID.

## Footnotes

1. Safety Population defined as {full definition from protocol}.
2. Sorted by Subject ID, Parameter, Visit Date.
3. Baseline is defined as the last non-missing value prior to first dose of study drug.
4. Normal ranges per central laboratory reference ranges.
5. Abbreviations as applicable.

## Programming Notes

Source: ADLB. Filter: SAFFL = 'Y', PARCAT1 = 'CHEMISTRY'. USUBJID for subject, PARAM/PARAMCD for parameter, AVISIT for visit, ADT for date, AVAL for result, BASE for baseline, CHG for change, ANRLO/ANRHI for reference ranges, ABLFL = 'Y' for baseline flag.
