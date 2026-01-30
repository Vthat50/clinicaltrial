---
name: Biosimilar TLF Generation
description: Tables, figures, and listings specific to biosimilar clinical trials
therapeutic_area: biosimilar
design_type: biosimilar
reference_saps: 1
supplemental_source: NCT03676192 actual SAP gap analysis
---

# Biosimilar TLF Generation Instructions

Biosimilar trials have unique regulatory requirements (FDA/EMA biosimilar guidance)
that go beyond standard efficacy/safety tables. These rules supplement the
therapeutic-area-specific rules (e.g., oncology, rheumatology) and the core
generation_rules.yaml.

**Apply these rules when:** `facts.study_design.type == "biosimilar"`

## Mandatory Tables (biosimilar-specific)

Always include these for biosimilar studies, in addition to core and area-specific tables:

- **Tipping Point Analysis — Primary Endpoint** — sensitivity analysis required by regulators to assess robustness of equivalence conclusion under worst-case missing data assumptions
- **Equivalence / Biosimilarity Margins Summary** — tabulate the pre-specified equivalence margins, observed differences, and confidence intervals
- **Salvage Treatment by Category** — post-progression or rescue therapy categorization (surgery, radiation, systemic by drug class)
- **Salvage Treatment — Systemic Therapy by Drug Class** — detailed breakdown of post-study systemic therapies
- **Prior Cancer Therapy — Surgical Procedures** — prior surgical procedures for the indication (oncology biosimilars)
- **Prior Cancer Therapy — Radiotherapy** — prior radiotherapy for the indication (oncology biosimilars)
- **Prior Cancer Therapy — Systemic by Drug Class** — prior systemic anticancer therapy broken down by drug class
- **Study Drug Exposure — Dose Administration by Cycle** — cycle-level dosing detail (common in biologic biosimilars)
- **Study Drug Exposure — Reasons for Non-Administration** — missed dose reasons
- **Study Drug Exposure — Dose Delay and Actions Taken** — dose modifications detail
- **Study Drug Exposure — Dose Summary Statistics** — cumulative dose, dose intensity, relative dose intensity

## Common Tables (biosimilar-specific)

Include when the protocol collects the relevant data:

- **Serum Drug Concentration by Study Period** — PK concentration split by treatment period (Induction/Maintenance) → only if PK samples collected and multiple periods
- **PK Parameter (Ctrough) by Study Period** — trough concentrations split by period → only if PK samples collected and multiple periods
- **TEAEs by ADA Status** — adverse events stratified by anti-drug antibody status → only if immunogenicity assessed
- **Hypersensitivity Monitoring Summary** — separate from AESI table, detailed monitoring of infusion reactions → only if infusion-administered biologic
- **Effusion Drainage** — fluid drainage events → only if relevant to the indication (e.g., bevacizumab in lung cancer)

## Conditional Tables

- **Response by Central AND Local Review** — biosimilar efficacy trials typically require both central and local tumor assessment review; generate separate tables for each review type per population (ITT, PP)
- **Whole Study Period AND Induction Period efficacy** — biosimilar trials often report efficacy for the induction period (primary) and whole study period (secondary) separately

## Follow-up Period Safety

Biosimilar trials with treatment periods (Induction, Maintenance) should also include
**Follow-up Period** safety tables in addition to Whole/Induction/Maintenance:

- Overview of TEAEs — Follow-up Period
- TEAEs by SOC and PT — Follow-up Period
- Serious TEAEs — Follow-up Period
- TEAEs (≥5% in Either Group) — Follow-up Period
- TEAEs (Grade 3 or Higher) — Follow-up Period

## Figures (biosimilar-specific)

- **Tipping Point Analysis Plot** — visualization of tipping point sensitivity analysis results

## Listings (biosimilar-specific)

- **Salvage Treatment Details** — individual patient listing of post-study therapies
- **Effusion Drainage** — individual patient listing of drainage events (if applicable)
- **Inclusion and Exclusion Criteria** — individual patient listing showing which criteria were met
- **General Comments** — free-text investigator comments listing

## Area-Specific Considerations

- Equivalence margins must be pre-specified and justified — include in table footnotes
- Risk difference method: Miettinen-Nurminen for binary endpoints
- Tipping point analysis is a regulatory expectation for missing data sensitivity
- Both Central and Local review required for tumor endpoints in oncology biosimilars
- PK/immunogenicity tables should be split by treatment period when multiple periods exist
- Drug-related TEAEs and drug-related Grade ≥3 TEAEs are standard biosimilar safety subsets
- ADA status stratification of safety data is expected
- Concomitant medications should be reported by study period
- Prior cancer therapy should be broken down by modality (surgical, radiation, systemic) with systemic further split by drug class
- Salvage/subsequent therapy tracking is important for long-term follow-up
