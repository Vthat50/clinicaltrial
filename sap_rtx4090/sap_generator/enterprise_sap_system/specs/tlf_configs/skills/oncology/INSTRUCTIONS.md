---
name: Oncology TLF Generation
description: Tables, figures, and listings for oncology clinical trials
therapeutic_area: Oncology
reference_saps: 10
---

# Oncology TLF Generation Instructions

Based on analysis of **10 reference SAPs** in oncology.

## Study Profile of Reference SAPs

- superiority: 6/10 SAPs
- single_arm: 3/10 SAPs
- non_inferiority: 1/10 SAPs

- Phase 3: 7/10 SAPs
- Phase 2: 2/10 SAPs
- observational: 1/10 SAPs

## Mandatory Tables (appeared in ≥80% of Oncology SAPs)

Always include these for oncology studies:

- *(No table type appeared in ≥80% — use the global mandatory set from generation_rules.yaml)*

## Common Tables (appeared in 40–80% of Oncology SAPs)

Include these when the protocol collects the relevant data:

- **Study Drug Exposure** — 5/10 SAPs (50%)
- **Demographics and Baseline Characteristics** — 5/10 SAPs (50%)
- **Subject Disposition** — 5/10 SAPs (50%)
- **Other / Study-Specific** — 5/10 SAPs (50%)
- **Time-to-Event Efficacy (e.g., OS, PFS, EFS)** — 4/10 SAPs (40%)
- **TEAEs Grade ≥3 by SOC and PT** — 4/10 SAPs (40%)
- **Disease Characteristics** — 4/10 SAPs (40%)
- **Quality of Life / PRO** — 4/10 SAPs (40%) → only if PRO instruments specified in protocol

## Conditional Tables (appeared in <40% of Oncology SAPs)

Include only when the protocol explicitly specifies the assessment:

- **Overview of TEAEs** — 3/10 SAPs (30%)
- **TEAEs by SOC and PT** — 3/10 SAPs (30%)
- **Serious TEAEs by SOC and PT** — 2/10 SAPs (20%)
- **ECOG Performance Status** — 2/10 SAPs (20%) → only if ECOG PS assessed
- **Vital Signs** — 2/10 SAPs (20%) → only if vital signs collected
- **TEAEs Leading to Death** — 2/10 SAPs (20%)
- **Concomitant Medications** — 2/10 SAPs (20%)
- **Subgroup Analyses** — 2/10 SAPs (20%) → only if subgroups pre-specified
- **Laboratory Parameters — Summary Statistics** — 2/10 SAPs (20%) → only if labs collected
- **TEAEs Leading to Discontinuation** — 2/10 SAPs (20%)
- **ECG Parameters** — 2/10 SAPs (20%) → only if ECG assessed
- **Baseline Values** — 2/10 SAPs (20%)
- **Prior Therapies / Anticancer Treatment** — 2/10 SAPs (20%)
- **Binary Efficacy Endpoint (e.g., response rate)** — 2/10 SAPs (20%)
- **Laboratory Parameters — Shift Tables** — 2/10 SAPs (20%) → only if labs collected
- **Medical History** — 2/10 SAPs (20%)
- **Adverse Events of Special Interest** — 1/10 SAPs (10%) → only if AESIs defined in protocol
- **Laboratory Parameters — CTCAE Grade** — 1/10 SAPs (10%) → only if labs collected (oncology: CTCAE grading)
- **TEAEs with Incidence ≥5%** — 1/10 SAPs (10%)
- **Continuous Efficacy Endpoint (e.g., change from baseline)** — 1/10 SAPs (10%)

## Figures

- **Kaplan-Meier Plot** — 5/10 SAPs (50%)
- **Other Figures** — 3/10 SAPs (30%)
- **Forest Plot** — 2/10 SAPs (20%)
- **Laboratory Trend Plot** — 1/10 SAPs (10%)
- **Waterfall Plot** — 1/10 SAPs (10%)
- **QoL Score Over Time** — 1/10 SAPs (10%)
- **Swimmer Plot** — 1/10 SAPs (10%)

## Listings

### Common (40–80%):
- **Other / Study-Specific** — 4/10 (40%)

### Conditional (<40%):
- **Overview of TEAEs** — 3/10 (30%)
- **Study Drug Exposure** — 3/10 (30%)
- **Laboratory Parameters — Summary Statistics** — 2/10 (20%)
- **Subject Disposition** — 2/10 (20%)
- **Time-to-Event Efficacy (e.g., OS, PFS, EFS)** — 2/10 (20%)
- **Demographics and Baseline Characteristics** — 2/10 (20%)
- **Adverse Events of Special Interest** — 1/10 (10%)
- **Serious TEAEs by SOC and PT** — 1/10 (10%)
- **ECOG Performance Status** — 1/10 (10%)
- **TEAEs Leading to Death** — 1/10 (10%)
- **Vital Signs** — 1/10 (10%)
- **TEAEs Leading to Discontinuation** — 1/10 (10%)
- **Medical History** — 1/10 (10%)
- **ECG Parameters** — 1/10 (10%)
- **Concomitant Medications** — 1/10 (10%)
- **Disease Characteristics** — 1/10 (10%)

## Area-Specific Considerations

- RECIST v1.1 is the standard response criteria — specify central and/or local review per protocol
- CTCAE grading is standard for AE severity and laboratory toxicities
- Prior anticancer therapy tables are expected (surgical, radiation, systemic by drug class)
- Disease characteristics table should include histology, stage, and biomarker status
- Period-split safety tables when Induction/Maintenance or Treatment/Follow-up periods exist
- Waterfall plots for tumor response when tumor measurements are collected
- Swimmer plots for duration of response in trials with ORR endpoints
- Subgroup forest plots for primary and key secondary endpoints
- Biosimilar oncology trials: add tipping point analysis table + figure, salvage therapy tables
