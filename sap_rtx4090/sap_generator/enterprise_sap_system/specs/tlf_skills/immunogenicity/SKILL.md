---
name: Immunogenicity
ich_section: "14.4"
display_order: 10
version: "2.0.0"
---

# Immunogenicity

Only included when immunogenicity is assessed. This is ONE combined table — ADA status, NAb status, and ADA titer are all in the same table.

## What Comes from the Protocol

- **Drug name**: the biologic being assessed for immunogenicity
- **ADA assay**: screening, confirmatory, and titer assay details
- **NAb assay**: whether neutralizing antibody testing is performed
- **Sampling schedule**: baseline and post-baseline ADA timepoints
- **ADA-positive definition**: assay-specific cut-point
- **Treatment-emergent definition**: ADA negative at baseline, positive post-baseline
- **Treatment-boosted definition**: ADA positive at baseline with ≥4-fold increase in titer

## Column Structure

- **Two-arm with total**: {Arm 1} | {Arm 2} | Total
- Arm names from `facts.arm_names[]`.

---

## Table: Immunogenicity - Anti-Drug Antibody Summary

| Setting | Value |
|---------|-------|
| Population | ADA Evaluable |
| Source | ADAB |
| Orientation | PORTRAIT |
| Filter | ADAFL = 'Y' |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| ADA Evaluable, N | data | count | 0 | Subjects with baseline + ≥1 post-baseline sample |
| | spacer | | 0 | |
| ADA Status | header | | 0 | |
| ADA Positive, n (%) | data | count_pct | 1 | Any post-baseline positive |
| Treatment-emergent, n (%) | data | count_pct | 2 | Negative at baseline → positive post-baseline |
| Treatment-boosted, n (%) | data | count_pct | 2 | Positive at baseline → ≥4-fold increase |
| ADA Negative, n (%) | data | count_pct | 1 | Negative at all post-baseline timepoints |
| | spacer | | 0 | |
| Neutralizing Antibody (NAb) | header | | 0 | Only if NAb testing performed |
| NAb Evaluable, N | data | count | 1 | |
| NAb Positive, n (%) | data | count_pct | 1 | Among ADA-positive samples tested |
| NAb Negative, n (%) | data | count_pct | 1 | |
| | spacer | | 0 | |
| ADA Titer | header | | 0 | |
| Median titer (range) | data | median_range | 1 | Among ADA-positive subjects |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|------------|---------|
| count | xxx | 195 |
| count_pct | xxx (xx.x) | 23 (11.8) |
| median_range | xxx (xxx-xxx) | 64 (8-2048) |

### Calculation Methods

- **ADA Evaluable**: All subjects with baseline and at least one post-baseline ADA sample
- **ADA Positive**: Subject with at least one ADA-positive post-baseline result (per assay cut-point)
- **Treatment-emergent**: ADA negative or missing at baseline AND positive at one or more post-baseline timepoints
- **Treatment-boosted**: ADA positive at baseline with ≥4-fold increase in titer at any post-baseline timepoint
- **NAb testing**: Performed on ADA-positive samples using cell-based assay (or as specified in protocol)
- **Titer**: Reciprocal of the last dilution with a positive result; median and range among ADA-positive subjects

### Footnotes

1. ADA Evaluable Population: All subjects with baseline and at least one post-baseline ADA sample.
2. Treatment-emergent: negative/missing at baseline, positive post-baseline.
3. Treatment-boosted: positive at baseline with ≥4-fold increase post-baseline.

---

## Table: TEAEs by ADA Status

Condition: Included when immunogenicity is assessed and there are sufficient ADA-positive subjects for meaningful comparison.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADAE, ADAB |
| Orientation | LANDSCAPE |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| ADA-Positive Subjects | header | | 0 | |
| Subjects with at least one TEAE, n (%) | data | count_pct | 1 | |
| Subjects with at least one serious TEAE, n (%) | data | count_pct | 1 | |
| Subjects with at least one treatment-related TEAE, n (%) | data | count_pct | 1 | |
| | spacer | | 0 | |
| ADA-Negative Subjects | header | | 0 | |
| Subjects with at least one TEAE, n (%) | data | count_pct | 1 | |
| Subjects with at least one serious TEAE, n (%) | data | count_pct | 1 | |
| Subjects with at least one treatment-related TEAE, n (%) | data | count_pct | 1 | |

### Calculation Methods

- **ADA status**: Overall post-baseline ADA result (positive if ever positive)
- **TEAE definition**: Same as adverse-events skill (TRTEMFL = 'Y')
- **Denominators**: N = number of ADA-positive or ADA-negative subjects per arm

### Footnotes

1. Safety Population.
2. ADA status determined by overall post-baseline ADA result.
3. Treatment-emergent: onset on or after first dose through safety follow-up.
