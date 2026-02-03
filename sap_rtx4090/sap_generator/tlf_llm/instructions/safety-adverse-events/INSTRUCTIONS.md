---
name: Safety - Adverse Events
ich_section: "14.3"
display_order: 5
types: [ae_overview, ae_by_soc_pt, ae_serious, ae_death, ae_discontinuation, ae_grade3plus, aesi]
condition: always
---

You are generating the adverse event table and figure shells for ICH E3 Section 14.3.

## What to Look For in the Protocol

Read the protocol to identify:
- Whether a CTCAE or other grading scale is used for AE severity
- Adverse Events of Special Interest (AESIs) — any defined list of specific AE categories requiring separate tabulation
- Grouped AE terms defined by the sponsor
- Drug-class safety concerns mentioned in the protocol
- Whether dose modifications are triggered by specific AEs
- Treatment-emergent AE (TEAE) definition if specified
- Whether AEs are collected by treatment period (if multi-period study)

## Counting Conventions

Each subject is counted once per system organ class and once per preferred term within that system organ class, regardless of how many times the event occurred. For tables by severity, each subject is counted at their worst severity. For tables by causality, each subject is counted at the closest causal relationship to the study drug. These counting rules must appear in the table footnotes.

## Treatment-Emergent Definition

A treatment-emergent adverse event is one that starts on or after the first dose of study drug, or that worsens in severity after the first dose. This definition must appear in the footnotes of every TEAE table. If the protocol defines a different observation period, use that definition instead.

## Coding Dictionary

Every table that displays adverse events by system organ class and preferred term must state the coding dictionary version in the footnotes.

## Mandatory Tables (every study)

- **TEAE Overview**: Summary incidence of TEAEs, SAEs, AEs leading to discontinuation, AEs leading to death — one row per category, counts and percentages by treatment arm.
- **TEAEs by System Organ Class and Preferred Term**: Full incidence table. By SOC (alphabetical or decreasing frequency) and PT within SOC.
- **TEAEs by Maximum Severity**: Severity is always collected (mild/moderate/severe or a protocol-defined grading scale). Generate this table for every study.
- **TEAEs by Causal Relationship**: Summarize TEAEs by investigator-assessed causality (related/not related). Generate this table for every study.
- **Study Drug-Related TEAEs by SOC and PT**: TEAEs assessed as related to study drug. This is a SEPARATE table from all-causality TEAEs. Generate for every study.
- **Serious Adverse Events by SOC and PT**: Same structure as above but limited to SAEs.
- **TEAEs Leading to Study Drug Discontinuation**: By SOC and PT.
- **TEAEs Leading to Death**: By SOC and PT (or narratives if few events).
- **Deaths**: All-cause mortality summary by treatment arm.

## Conditional Tables

- **Grade ≥3 TEAEs by SOC and PT**: Include if the protocol uses a grading scale with numbered grades.
- **Treatment-Related SAEs**: Separate table for SAEs assessed as related to study drug.
- **Special Search Categories / SMQ-Based TEAEs**: If the protocol defines special search categories, standardised queries, or grouped safety topics for focused analysis, generate ONE SEPARATE TABLE per search category. Use the exact names from the protocol.
- **Deaths Summary Table**: Summary of all deaths by cause category and treatment arm. This is a TABLE (not just a listing). Include even if the number of deaths is small.
- **Adverse Events of Special Interest**: Generate ONE SEPARATE TABLE per AESI category defined in the protocol. Use the exact AESI names from the protocol. The number of AESI tables must equal the number of AESIs defined. Do NOT combine multiple AESIs into one table.
- **Grouped AE Terms**: If the protocol defines grouped terms, generate a table for each group.
- **TEAEs by Treatment Period**: Include if the study has multiple distinct treatment periods. Generate a SEPARATE full set of AE tables (overview + SOC/PT) for EACH treatment period.
- **AEs by ADA Status**: Include ONLY if immunogenicity is assessed (this will be generated in the immunogenicity domain — flag here only if not covered there).
- **Dose Modification Due to AEs**: Include if protocol allows dose modifications for AEs.

## CRITICAL: Generate ALL AESIs

Read the protocol carefully for the COMPLETE list of AESIs. They may be in a dedicated AESI section, in the safety monitoring plan, in the statistical analysis section, in dose modification criteria, in the drug-class safety section, or scattered across the protocol. Search ALL of these locations. Generate one table for EACH AESI found.

Before finalizing, count: list every AESI you found in extracted_facts, then verify you have a matching AESI table for each one. If any AESI is missing a table, add it. Missing an AESI table is a significant gap.

## Design-Type Guidance

Design type affects column structure:
- Randomized: columns per treatment arm + total
- Single-arm: overall column only
- Crossover: generate separate tables per period; use period-specific baselines for shift tables
- Dose-escalation: group by dose/cohort

## Population

All AE tables use the **Safety** population.

## Output Format — Full Shell Specification

Each table must include complete columns, rows, footnotes, source, and orientation. See the system prompt for the full JSON schema.

**Row guidance for AE tables:**

*ae_overview:*
- Data: Subjects with at least one TEAE (count_pct)
- Data: Subjects with at least one SAE (count_pct)
- Data: Subjects with TEAEs leading to discontinuation (count_pct)
- Data: Subjects with TEAEs leading to death (count_pct)
- Data: Subjects with Grade ≥3 TEAEs (count_pct) — if grading used
- Spacer
- Header: "Adverse Events of Special Interest" (bold) — if AESIs defined
- Data: One row per AESI (count_pct, indent=1)

*ae_by_soc_pt:*
- Data: Subjects with at least one TEAE (count_pct)
- Header: "[System Organ Class]" (bold, indent=0) — placeholder for SOC categories
- Data: "[Preferred Term]" (count_pct, indent=1) — placeholder for PTs within SOC

*ae_serious, ae_death, ae_discontinuation, ae_grade3plus:* Same SOC/PT structure as ae_by_soc_pt.

*aesi:* One table per AESI category. Rows: Subjects with event (count_pct), then by PT (count_pct, indent=1).

**Footnotes must include:** Safety population definition, MedDRA coding version, TEAE definition, subject counting rule.

Types: "ae_overview", "ae_by_soc_pt", "ae_serious", "ae_death", "ae_discontinuation", "ae_grade3plus", "aesi".
Source: ADAE. Section: "14.3". Orientation: LANDSCAPE for SOC/PT tables, PORTRAIT for overview.
