# TLF Extraction Layer — Master Instructions

This is the **extraction layer** for TLF shell generation. It reads the clinical trial protocol and identifies everything the generation layer needs to build study-specific table shells.

## Why This Exists

A fixed JSON schema cannot anticipate study-specific requirements. When tested, it missed disease-specific baseline variables, study-specific AE categories, special monitoring tables, and protocol-defined assessment details. The extraction layer replaces the fixed schema with reasoning-based instructions that guide the LLM to discover what THIS protocol actually requires.

## Architecture

```
Protocol PDF
    ↓
Extraction Layer (these instruction files)
    → Protocol-specific facts (natural language)
    ↓
Generation Layer (SKILL.md rendering specs)
    → TLF shell documents
```

## How to Use

Read the protocol, then work through each extraction file in order. Each file tells you where to look in the protocol and what to think about. Extract what you find — do not assume, do not default, do not guess.

The extraction files are in `extraction/`. Process them in this order:

1. **`study-context.md`** — Extract first. Produces the shared study shape (arms, populations, periods, indication) that every other section needs.
2. **`disposition.md`** — Discontinuation reasons, follow-up structure, deviation categories.
3. **`demographics.md`** — Disease-specific baselines, stratification-driven variables, SOA baseline assessments.
4. **`efficacy.md`** — Every endpoint with its type, population, method, sensitivity analyses, subgroups.
5. **`adverse-events.md`** — Grading, relatedness, AESIs, grouped terms, dose modification triggers, drug class safety concerns.
6. **`labs.md`** — Panels collected, special monitoring parameters, toxicity grading, abnormality criteria.
7. **`vitals-ecg.md`** — Parameters measured, special procedures, QT assessment, categorical thresholds.
8. **`exposure-meds.md`** — Dosing regimen, dose modification rules, backbone therapy, rescue medications.
9. **`pk-immunogenicity.md`** — Sampling schedule, analytes, ADA assessment, PD biomarkers.
10. **`figures.md`** — Derived from above: which figures the endpoints and assessments require.
11. **`listings.md`** — Derived from above: every data domain collected needs a listing.

## Principles

- **Extract what the protocol says.** Do not assume standard values. If the protocol doesn't mention something, it's not there.
- **Use the protocol's exact names.** Population names, arm names, endpoint names, assessment names — copy them verbatim.
- **No specific examples in the output.** The extraction captures what THIS protocol defines, not what a typical protocol might define.
- **Study-specific comes from the protocol, not from templates.** The whole point of this layer is to find things a fixed template would miss.
