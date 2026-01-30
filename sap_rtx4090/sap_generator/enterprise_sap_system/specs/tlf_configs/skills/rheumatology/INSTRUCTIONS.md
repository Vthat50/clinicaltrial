---
name: Rheumatology TLF Generation
description: Tables, figures, and listings for rheumatology clinical trials
therapeutic_area: Rheumatology
reference_saps: 5
---

# Rheumatology TLF Generation Instructions

Based on analysis of **5 reference SAPs** in rheumatology.

## Study Profile of Reference SAPs

- superiority: 2/5 SAPs
- single_arm: 2/5 SAPs
- descriptive: 1/5 SAPs

- Phase 3: 2/5 SAPs
- Phase 2: 1/5 SAPs
- N/A: 1/5 SAPs
- Phase 4: 1/5 SAPs

## Mandatory Tables (appeared in ≥80% of Rheumatology SAPs)

Always include these for rheumatology studies:

- *(No table type appeared in ≥80% — use the global mandatory set from generation_rules.yaml)*

## Common Tables (appeared in 40–80% of Rheumatology SAPs)

Include these when the protocol collects the relevant data:

- **Other / Study-Specific** — 2/5 SAPs (40%)

## Conditional Tables (appeared in <40% of Rheumatology SAPs)

Include only when the protocol explicitly specifies the assessment:

- **Adverse Events of Special Interest** — 1/5 SAPs (20%) → only if AESIs defined in protocol
- **Study Drug Exposure** — 1/5 SAPs (20%)
- **Serious TEAEs by SOC and PT** — 1/5 SAPs (20%)
- **Vital Signs** — 1/5 SAPs (20%) → only if vital signs collected
- **Overview of TEAEs** — 1/5 SAPs (20%)
- **Laboratory Parameters — CTCAE Grade** — 1/5 SAPs (20%) → only if labs collected (oncology: CTCAE grading)
- **TEAEs Leading to Death** — 1/5 SAPs (20%)
- **Immunogenicity (ADA / NAb)** — 1/5 SAPs (20%) → only if immunogenicity assessed
- **TEAEs with Incidence ≥5%** — 1/5 SAPs (20%)
- **Disease Characteristics** — 1/5 SAPs (20%)
- **Concomitant Medications** — 1/5 SAPs (20%)
- **Subgroup Analyses** — 1/5 SAPs (20%) → only if subgroups pre-specified
- **Laboratory Parameters — Summary Statistics** — 1/5 SAPs (20%) → only if labs collected
- **Time-to-Event Efficacy (e.g., OS, PFS, EFS)** — 1/5 SAPs (20%)
- **Quality of Life / PRO** — 1/5 SAPs (20%) → only if PRO instruments specified in protocol
- **TEAEs Leading to Discontinuation** — 1/5 SAPs (20%)
- **Demographics and Baseline Characteristics** — 1/5 SAPs (20%)
- **Subject Disposition** — 1/5 SAPs (20%)
- **Prior Therapies / Anticancer Treatment** — 1/5 SAPs (20%)
- **Binary Efficacy Endpoint (e.g., response rate)** — 1/5 SAPs (20%)
- **Continuous Efficacy Endpoint (e.g., change from baseline)** — 1/5 SAPs (20%)
- **Medical History** — 1/5 SAPs (20%)

## Figures

- **Kaplan-Meier Plot** — 1/5 SAPs (20%)
- **CONSORT / Disposition Diagram** — 1/5 SAPs (20%)
- **Other Figures** — 1/5 SAPs (20%)

## Listings

### Conditional (<40%):
- **Adverse Events of Special Interest** — 1/5 (20%)
- **Laboratory Parameters — Summary Statistics** — 1/5 (20%)
- **TEAEs by SOC and PT** — 1/5 (20%)
- **Serious TEAEs by SOC and PT** — 1/5 (20%)
- **Other / Study-Specific** — 1/5 (20%)
- **Demographics and Baseline Characteristics** — 1/5 (20%)
- **TEAEs Leading to Death** — 1/5 (20%)
- **Vital Signs** — 1/5 (20%)
- **Medical History** — 1/5 (20%)
- **Concomitant Medications** — 1/5 (20%)

## Area-Specific Considerations

- ACR20/50/70 response rates are standard efficacy endpoints
- DAS28 score analysis (change from baseline, remission rates)
- Immunogenicity is frequently assessed (biologic therapies)
- CTCAE grading may apply for laboratory toxicities
- Disease activity categories (remission, low, moderate, high) at each visit
- Open-label extension period tables are common
