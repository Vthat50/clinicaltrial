---
name: Immunogenicity
ich_section: "14.3"
display_order: 9
types: [immunogenicity]
condition: has_immunogenicity
---

You are generating the immunogenicity table shells for ICH E3 Section 14.3.

This domain only runs when the protocol includes immunogenicity assessment (anti-drug antibody testing).

## What to Look For in the Protocol

Read the protocol to identify:
- Whether anti-drug antibody (ADA) testing is performed
- Whether neutralizing antibody (NAb) testing is performed
- ADA sampling schedule and timepoints
- Whether ADA impact analysis is planned (efficacy by ADA status, AEs by ADA status, PK by ADA status)
- ADA-evaluable population definition
- Tiered testing approach described (screening → confirmatory → titer → NAb)

## Tables

- **Anti-Drug Antibody Incidence**: ADA status (positive/negative) by treatment arm at each timepoint. Include treatment-emergent ADA (TE-ADA) and treatment-boosted ADA categories.
- **ADA Titer Summary**: If titers are reported — summary of ADA titers among ADA-positive subjects.

### Conditional Tables — Generate ALL That Apply

- **Neutralizing Antibody (NAb) Incidence**: Include if NAb testing is performed. NAb positive/negative among ADA-positive subjects by timepoint.
- **NAb Impact on Efficacy**: If NAb impact analysis is planned. Primary endpoint results by NAb status.
- **NAb Impact on PK**: If NAb-PK relationship is analyzed.
- **TEAEs by ADA Status**: Include if ADA impact analysis on safety is planned. TEAE incidence in ADA-positive vs ADA-negative subjects.
- **Efficacy by ADA Status**: Include if ADA impact analysis on efficacy is planned. Primary endpoint results by ADA status.
- **PK by ADA Status**: Include if PK-ADA relationship analysis is planned. PK parameters in ADA-positive vs ADA-negative subjects.

For biologic/biosimilar studies, assume ALL of these conditional tables apply unless the protocol explicitly excludes them.

## Design-Type Guidance

Design type affects column structure:
- Randomized: columns per treatment arm + total
- Single-arm: overall column only
- Crossover: generate separate tables per period; use period-specific baselines for shift tables
- Dose-escalation: group by dose/cohort

## Population

Immunogenicity tables use the **ADA Evaluable** population (subjects with at least one baseline and one post-baseline ADA sample).

## Output Format — Full Shell Specification

Each table must include complete columns, rows, footnotes, source, and orientation. See the system prompt for the full JSON schema.

**Row guidance for ADA incidence tables:**
- Data: ADA Evaluable, N (count)
- Data: Baseline ADA positive, n (%) (count_pct)
- Data: Treatment-emergent ADA positive, n (%) (count_pct)
- Data: Treatment-boosted ADA positive, n (%) (count_pct)
- Spacer
- Header: "ADA Status by Visit" → sub-rows per protocol ADA sampling timepoint (count_pct, indent=1)

**Row guidance for NAb tables:**
- Among ADA-positive: NAb positive, n (%) (count_pct); NAb negative, n (%) (count_pct)

Type: "immunogenicity".
Source: ADAB (or custom immunogenicity dataset). Section: "14.3". Orientation: PORTRAIT.
