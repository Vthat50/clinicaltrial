---
name: Data Listings
ich_section: "16.2"
display_order: 11
types: []
condition: always
---

You are generating the ICH E3 Section 16.2 individual patient data listing shells.

Listings provide patient-level data for regulatory review. Every data domain collected in the study should have a corresponding listing.

## What to Look For in the Protocol

Read the protocol to identify ALL data domains collected:
- Demographics, medical history, prior/concomitant medications
- Study drug exposure and compliance
- All efficacy assessment data (one listing per endpoint or assessment type)
- Adverse events (all AEs, SAEs, AEs leading to discontinuation, deaths, AESIs)
- Lab panels collected (one listing per panel)
- Vital signs, ECG, physical examination
- PK concentrations and derived parameters (if PK assessed)
- Immunogenicity/ADA results (if assessed)
- QoL/PRO instrument data (if collected)
- Protocol deviations
- Screening failures, subject disposition

## Mandatory Listings (every study)

These listings are required by ICH E3 regardless of study design:

- **Listing of Deaths**: All deaths with narratives/details
- **Listing of Serious Adverse Events**: All SAEs with details
- **Listing of TEAEs Leading to Discontinuation**: All AEs causing study drug discontinuation
- **Listing of TEAEs Leading to Death**: AEs with fatal outcome
- **Listing of Protocol Deviations**: All major protocol deviations
- **Listing of Screening Failures**: Reasons for screen failure
- **Listing of Subject Disposition**: Enrollment, treatment, completion, discontinuation per subject
- **Listing of Demographics**: Individual demographic data
- **Listing of Medical History**: Individual medical history data
- **Listing of Prior Medications**: Medications at baseline
- **Listing of Concomitant Medications**: Medications during treatment
- **Listing of Study Drug Exposure**: Individual dosing data
- **Listing of All Adverse Events**: Complete AE listing

## Assessment-Conditional Listings

Generate these based on what the protocol collects. Generate a SEPARATE listing for EACH item:

- **Listing of [Lab Panel] Results**: ONE PER lab panel collected — do NOT combine into one listing
- **Listing of Vital Signs**: If vital signs collected
- **Listing of ECG Results**: If ECGs collected
- **Listing of Physical Examination Findings**: If physical exam data collected
- **Listing of PK Concentrations**: If PK sampling performed
- **Listing of PK Parameters**: If PK parameters derived
- **Listing of Subjects Excluded from PK Analysis**: If PK analysis has exclusion criteria
- **Listing of Immunogenicity/ADA Results**: If ADA testing performed
- **Listing of Neutralizing Antibody Results**: If NAb testing performed
- **Listing of [QoL Instrument] Responses**: ONE PER QoL/PRO instrument (including disease-specific modules)
- **Listing of Adverse Events of Special Interest**: If AESIs defined

## Endpoint Data Listings

- **Listing of [Endpoint Name] Data**: One listing per efficacy endpoint (primary and secondary). Include individual patient assessment data.

## Design-Specific Listings

- **Listing of Rescue Medication Use**: If rescue therapy is defined
- **Listing of Dose Modifications**: If dose modifications are allowed
- **Listing of Backbone Therapy**: If add-on study design
- **Listing of Subjects with Notable Lab Abnormalities**: If protocol defines criteria
- **Listing of Subjects with Notable Vital Sign Abnormalities**: If protocol defines criteria
- **Listing of Subjects Excluded from Efficacy Analysis**: If the protocol defines efficacy analysis exclusion criteria
- **Listing of Subjects Excluded from Safety Analysis**: If the protocol defines safety analysis exclusion criteria

## CRITICAL: Completeness

Every data domain collected in the study MUST have at least one listing. A typical Phase 3 study should produce 30-50 listings. If you have fewer than 25, you are likely missing some. Count the mandatory listings (13) + lab panels + vital signs + ECG + efficacy endpoints + PK + immunogenicity + QoL instruments + design-specific listings.

## Sort Order

Every listing must specify its sort order. The default is by subject identifier, then by visit or date within subject.

## Population

- Safety-related listings: **Safety** population
- Efficacy data listings: **ITT/FAS** or **Enrolled** population
- PK listings: **PK** or **PK Evaluable** population
- Immunogenicity listings: **ADA Evaluable** population
- Disposition/screening listings: **Screened** or **Enrolled** population

## Output Format — Full Shell Specification

Each listing must include: title, type, population, section, variables (column headers), source, orientation.

**Listings use the `variables` field instead of columns/rows.** The `variables` field is an array of column header strings that a programmer would use as the listing columns.

Example variables by listing type:
- Deaths: ["Subject ID", "Treatment Group", "Age", "Sex", "Date of Death", "Cause of Death", "Days from Last Dose", "Relationship to Study Drug"]
- SAEs: ["Subject ID", "Treatment Group", "SOC", "Preferred Term", "Start Date", "End Date", "Severity", "Outcome", "Causality"]
- AEs: ["Subject ID", "Treatment Group", "SOC", "Preferred Term", "Start Date", "End Date", "Severity/Grade", "Serious", "Action Taken", "Outcome", "Causality"]
- Demographics: ["Subject ID", "Treatment Group", "Age", "Sex", "Race", "Ethnicity", "Weight (kg)", "Height (cm)", "BMI"]
- Labs: ["Subject ID", "Treatment Group", "Lab Parameter", "Visit", "Date", "Result", "Unit", "Reference Range", "Flag"]

Type: "listing".
Source: appropriate ADaM dataset.
Section: "16.2". Orientation: LANDSCAPE for all listings.
