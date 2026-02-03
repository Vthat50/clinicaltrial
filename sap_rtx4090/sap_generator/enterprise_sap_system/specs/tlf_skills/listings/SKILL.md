---
name: Listings
ich_section: "16.2"
display_order: 19
version: "2.0.0"
---

# Listings

Individual patient data listings per ICH E3 Section 16.2. All listings use Safety population unless noted otherwise.

## What Comes from the Protocol

- **ADaM datasets**: which datasets are available (ADSL, ADAE, ADLB, ADVS, ADEG, ADCM, ADMH, ADPC, ADPP, ADAB, ADQS, ADRS, ADEX, ADDV)
- **Assessments collected**: determines which conditional listings are included
- **Lab panels**: hematology, chemistry, urinalysis — determines lab listing splits
- **PK sampling**: whether PK concentration and parameter listings are needed
- **Immunogenicity**: whether ADA listing is needed
- **QoL instruments**: whether QoL listings are needed
- **Biosimilar study**: whether salvage treatment, IE criteria, and general comments listings are needed

## Column Structure

All listings use a flat column layout with one column per variable. No treatment arm nesting.

---

## Listing: Subject Disposition

Always included.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADSL |
| Orientation | LANDSCAPE |

### Columns

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

---

## Listing: Screening Failures

Always included.

| Setting | Value |
|---------|-------|
| Population | All Screened |
| Source | ADSL |
| Orientation | LANDSCAPE |
| Filter | RANDFL ≠ 'Y' |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Site | SITEID | |
| Age | AGE | |
| Sex | SEX | |
| Reason for Screen Failure | SCRFREAS | |

---

## Listing: Protocol Deviations

Always included.

| Setting | Value |
|---------|-------|
| Population | All Enrolled |
| Source | ADDV |
| Orientation | LANDSCAPE |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Site | SITEID | |
| Treatment | TRT01A | |
| Deviation Category | DVCAT | |
| Deviation Description | DVTERM | |
| Deviation Date | DVSTDT | |
| Impact on Analysis | DVIMP | Major/minor; PP exclusion flag |

---

## Listing: Demographics and Baseline Characteristics

Always included.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADSL |
| Orientation | LANDSCAPE |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Site | SITEID | |
| Treatment | TRT01A | |
| Age | AGE | |
| Sex | SEX | |
| Race | RACE | |
| Ethnicity | ETHNIC | |
| Weight (kg) | WEIGHTBL | |
| Height (cm) | HEIGHTBL | |
| BMI (kg/m²) | BMIBL | |

---

## Listing: Medical History

Always included.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADMH |
| Orientation | LANDSCAPE |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment | TRT01A | |
| System Organ Class | MHBODSYS | MedDRA SOC |
| Preferred Term | MHDECOD | MedDRA PT |
| Condition/Diagnosis | MHTERM | Verbatim term |
| Ongoing at Baseline | MHENRF | |

---

## Listing: Disease Characteristics

Always included.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADSL |
| Orientation | LANDSCAPE |

### Columns

Columns are protocol-specific. Typical oncology columns:

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment | TRT01A | |
| Disease Stage | DSSTAGE | Protocol-specific |
| Histology | HISTTYPE | Protocol-specific |
| ECOG at Baseline | ECOGBL | |
| Prior Lines of Therapy | NPRIOR | |

---

## Listing: Prior Medications

Always included.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADCM |
| Orientation | LANDSCAPE |
| Filter | CMCAT = 'PRIOR' or CMENRF = 'BEFORE' |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment | TRT01A | |
| ATC Class | CMCLAS | |
| Drug Name | CMDECOD | WHO Drug coded name |
| Indication | CMINDC | |
| Start Date | CMSTDT | |
| End Date | CMENDT | |

---

## Listing: Concomitant Medications

Always included.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADCM |
| Orientation | LANDSCAPE |
| Filter | Concomitant medications (overlapping with treatment period) |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment | TRT01A | |
| ATC Class | CMCLAS | |
| Drug Name | CMDECOD | |
| Indication | CMINDC | |
| Start Date | CMSTDT | |
| End Date | CMENDT | |
| Ongoing | CMENRF | |

---

## Listing: Study Drug Exposure

Always included.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADEX |
| Orientation | LANDSCAPE |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment | TRT01A | |
| First Dose Date | EXSTDT | |
| Last Dose Date | EXENDT | |
| Duration (days) | EXDUR | |
| Number of Doses/Cycles | EXDOSE | |
| Dose Modifications | EXADJ | |
| Relative Dose Intensity (%) | EXRDI | |

---

## Listing: All Adverse Events

Always included.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADAE |
| Orientation | LANDSCAPE |

### Columns

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

---

## Listing: Serious Adverse Events

Always included.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADAE |
| Orientation | LANDSCAPE |
| Filter | AESER = 'Y' |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment | TRT01A | |
| System Organ Class | AEBODSYS | |
| Preferred Term | AEDECOD | |
| Verbatim Term | AETERM | |
| Start Date | AESTDT | |
| Severity/Grade | AETOXGR | |
| Relationship | AEREL | |
| Action Taken | AEACN | |
| Outcome | AEOUT | |
| Seriousness Criteria | AESMIE | Death, hospitalization, etc. |

---

## Listing: TEAEs Leading to Discontinuation

Always included.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADAE |
| Orientation | LANDSCAPE |
| Filter | AEACN = 'DRUG WITHDRAWN' |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment | TRT01A | |
| System Organ Class | AEBODSYS | |
| Preferred Term | AEDECOD | |
| Start Date | AESTDT | |
| Severity/Grade | AETOXGR | |
| Relationship | AEREL | |
| Outcome | AEOUT | |

---

## Listing: TEAEs Leading to Death

Always included.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADAE |
| Orientation | LANDSCAPE |
| Filter | AEOUT = 'FATAL' |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment | TRT01A | |
| System Organ Class | AEBODSYS | |
| Preferred Term | AEDECOD | |
| Start Date | AESTDT | |
| Severity/Grade | AETOXGR | |
| Relationship | AEREL | |
| Primary Cause of Death | AECOD | |

---

## Listing: Deaths

Always included.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADSL |
| Orientation | PORTRAIT |
| Filter | DTHFL = 'Y' |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment | TRT01A | |
| Date of Death | DTHDT | |
| Primary Cause of Death | DTHCAUS | |
| Days from Last Dose to Death | DTHADY | |
| On Treatment | DTHONTR | Y/N |

---

## Listing: Adverse Events of Special Interest

Condition: When AESIs are defined in protocol.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADAE |
| Orientation | LANDSCAPE |
| Filter | AESI-specific criteria per protocol |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment | TRT01A | |
| AESI Category | AESICAT | Which AESI definition matched |
| System Organ Class | AEBODSYS | |
| Preferred Term | AEDECOD | |
| Start Date | AESTDT | |
| Severity/Grade | AETOXGR | |
| Serious | AESER | |
| Relationship | AEREL | |
| Outcome | AEOUT | |

---

## Listing: Efficacy Data

Always included.

| Setting | Value |
|---------|-------|
| Population | ITT |
| Source | ADRS, ADEFF, or ADTTE |
| Orientation | LANDSCAPE |

### Columns

Columns are endpoint-specific. Typical columns:

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment | TRT01A | |
| Endpoint Value | AVAL | |
| Baseline Value | BASE | |
| Change from Baseline | CHG | |
| Response Category | AVALC | For binary/categorical endpoints |
| Assessment Date | ADT | |
| Visit | AVISIT | |

---

## Listing: Hematology

Condition: When laboratory data is collected.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADLB |
| Orientation | LANDSCAPE |
| Filter | PARCAT1 = 'HEMATOLOGY' |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment | TRT01A | |
| Parameter | PARAM | |
| Visit | AVISIT | |
| Result | AVAL | |
| Unit | AVALU | SI units |
| Baseline Flag | ABLFL | Y if baseline record |
| Normal Range Low | ANRLO | Per central lab |
| Normal Range High | ANRHI | Per central lab |
| Abnormality Flag | ANRIND | Normal/Low/High |

---

## Listing: Clinical Chemistry

Condition: When laboratory data is collected.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADLB |
| Orientation | LANDSCAPE |
| Filter | PARCAT1 = 'CHEMISTRY' |

### Columns

Same as Hematology listing.

---

## Listing: Urinalysis

Condition: When urinalysis is collected.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADLB |
| Orientation | LANDSCAPE |
| Filter | PARCAT1 = 'URINALYSIS' |

### Columns

Same as Hematology listing.

---

## Listing: Subjects with Markedly Abnormal Laboratory Values

Condition: When laboratory data is collected.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADLB |
| Orientation | LANDSCAPE |
| Filter | Markedly abnormal per protocol-defined criteria |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment | TRT01A | |
| Parameter | PARAM | |
| Visit | AVISIT | |
| Result | AVAL | |
| Unit | AVALU | |
| Normal Range | ANRLO - ANRHI | |
| Baseline Value | BASE | |
| CTCAE Grade | ATOXGR | If CTCAE grading applied |

---

## Listing: Liver Function Tests

Condition: When liver function is monitored.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADLB |
| Orientation | LANDSCAPE |
| Filter | PARAMCD in ('ALT', 'AST', 'BILI', 'ALP') |

### Columns

Same as Hematology listing, plus:

| Column | Source Variable | Notes |
|--------|----------------|-------|
| x ULN | AVAL / ANRHI | Multiples of upper limit of normal |

---

## Listing: Potential Hy's Law Cases

Condition: When liver function is monitored.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADLB |
| Orientation | PORTRAIT |
| Filter | ALT or AST ≥3x ULN AND Total Bilirubin ≥2x ULN |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment | TRT01A | |
| ALT Peak (x ULN) | AVAL / ANRHI | Maximum post-baseline |
| AST Peak (x ULN) | AVAL / ANRHI | Maximum post-baseline |
| Total Bilirubin Peak (x ULN) | AVAL / ANRHI | Maximum post-baseline |
| ALP Peak (x ULN) | AVAL / ANRHI | To rule out cholestatic cause |
| Date of Peak ALT/AST | ADT | |
| Date of Peak Bilirubin | ADT | |
| Narrative | Free text | Clinical narrative |

---

## Listing: Vital Signs

Condition: When vital signs are collected.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADVS |
| Orientation | LANDSCAPE |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment | TRT01A | |
| Parameter | PARAM | |
| Visit | AVISIT | |
| Result | AVAL | |
| Unit | AVALU | |
| Baseline Value | BASE | |
| Change from Baseline | CHG | |

---

## Listing: ECG Parameters

Condition: When ECG is assessed.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADEG |
| Orientation | LANDSCAPE |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment | TRT01A | |
| Parameter | PARAM | |
| Visit | AVISIT | |
| Result | AVAL | |
| Unit | AVALU | |
| Baseline Value | BASE | |
| Change from Baseline | CHG | |
| Overall Interpretation | EGINTPR | Normal/Abnormal NCS/Abnormal CS |

---

## Listing: PK Concentrations

Condition: When PK samples are collected.

| Setting | Value |
|---------|-------|
| Population | PK |
| Source | ADPC |
| Orientation | LANDSCAPE |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment | TRT01A | |
| Analyte | PARAM | |
| Visit/Period | AVISIT | |
| Nominal Time (h) | NFRLT | Protocol-specified timepoint |
| Actual Time (h) | AFRLT | Actual collection time |
| Concentration | AVAL | |
| Unit | AVALU | |
| BLQ Flag | ABLFL | Below lower limit of quantification |

---

## Listing: PK Parameters

Condition: When PK samples are collected.

| Setting | Value |
|---------|-------|
| Population | PK |
| Source | ADPP |
| Orientation | LANDSCAPE |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment | TRT01A | |
| Analyte | PARAM | |
| Cmax | AVAL (PARAMCD='CMAX') | Maximum concentration |
| AUC0-t | AVAL (PARAMCD='AUCLST') | AUC to last measurable |
| AUC0-inf | AVAL (PARAMCD='AUCALL') | AUC extrapolated to infinity |
| Tmax | AVAL (PARAMCD='TMAX') | Time to Cmax |
| t1/2 | AVAL (PARAMCD='LAMZHL') | Terminal half-life |

---

## Listing: Anti-Drug Antibody Results

Condition: When immunogenicity is assessed.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADAB |
| Orientation | LANDSCAPE |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment | TRT01A | |
| Visit | AVISIT | |
| ADA Status | AVALC | Positive/Negative |
| Titer | AVAL | Reciprocal of last positive dilution |
| NAb Status | NABLFL | Positive/Negative (if tested) |
| ADA Category | ADABLFL | Treatment-emergent / boosted / persistent / transient |

---

## Listing: QoL Responses by Visit — {Instrument}

Condition: One per QoL/PRO instrument.

| Setting | Value |
|---------|-------|
| Population | ITT |
| Source | ADQS |
| Orientation | LANDSCAPE |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment | TRT01A | |
| Visit | AVISIT | |
| Domain/Subscale | PARAM | |
| Score | AVAL | |
| Baseline Score | BASE | |
| Change from Baseline | CHG | |

---

## Listing: Physical Examination

Condition: When physical exam is collected.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADPE |
| Orientation | LANDSCAPE |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment | TRT01A | |
| Visit | AVISIT | |
| Body System | PECAT | |
| Finding | PEORRES | |
| Clinical Significance | PECLSIG | NCS or CS |

---

## Listing: Pregnancy Test

Condition: When pregnancy test is collected.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADLB |
| Orientation | PORTRAIT |
| Filter | PARAMCD = 'PREG' |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment | TRT01A | |
| Visit | AVISIT | |
| Result | AVALC | Positive/Negative |
| Date | ADT | |

---

## Listing: Salvage Treatment Details

Condition: Biosimilar/equivalence studies.

| Setting | Value |
|---------|-------|
| Population | ITT |
| Source | ADCM |
| Orientation | LANDSCAPE |
| Filter | Salvage/rescue therapy |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Treatment | TRT01A | |
| Salvage Drug | CMDECOD | |
| Start Date | CMSTDT | |
| Reason | CMINDC | |

---

## Listing: Inclusion and Exclusion Criteria

Condition: Biosimilar/equivalence studies.

| Setting | Value |
|---------|-------|
| Population | All Screened |
| Source | ADSL, ADDV |
| Orientation | PORTRAIT |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Site | SITEID | |
| IE Criterion Violated (if any) | IETEST | |
| Description | IETESTCD | |

---

## Listing: General Comments

Condition: Biosimilar/equivalence studies.

| Setting | Value |
|---------|-------|
| Population | All Enrolled |
| Source | ADSL |
| Orientation | PORTRAIT |

### Columns

| Column | Source Variable | Notes |
|--------|----------------|-------|
| Subject ID | USUBJID | |
| Site | SITEID | |
| Treatment | TRT01A | |
| Comment | COMMENT | |
