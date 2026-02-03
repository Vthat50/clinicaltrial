---
name: Disposition
ich_section: "14.1"
display_order: 1
version: "2.0.0"
---

# Disposition

Always included, every study.

## What Comes from the Protocol

- **Study design**: randomized vs single-arm, open-label vs blinded
- **Treatment arms**: arm names and planned N per arm
- **Treatment periods**: single period or multi-period (induction/maintenance)
- **Discontinuation reasons**: protocol-defined categories (e.g., disease progression only in oncology)
- **Follow-up requirements**: length of safety follow-up after treatment end
- **Analysis populations**: ITT, mITT, PP, Safety — definitions from protocol

## Column Structure

- **Two-arm with total**: {Arm 1} | {Arm 2} | Total
- **Three-arm with total**: {Arm 1} | {Arm 2} | {Arm 3} | Total
- Arm names from `facts.arm_names[]`.
- Screened row uses a single "Total" column; all others use per-arm columns.

---

## Table: Subject Disposition

| Setting | Value |
|---------|-------|
| Population | All Screened |
| Source | ADSL |
| Orientation | PORTRAIT |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Screened | data | count | 0 | Total screened across all sites |
| Screen Failures, n (%) | data | count_pct | 0 | % of N screened |
| | spacer | | 0 | |
| Randomized | data | count | 0 | **Bold**; % not shown or % of screened |
| Treated | data | count_pct | 0 | % of N randomized |
| | spacer | | 0 | |
| Study Treatment Status | header | | 0 | |
| Completed study treatment | data | count_pct | 1 | Per-protocol treatment completion |
| Discontinued study treatment | data | count_pct | 1 | |
| | spacer | | 0 | |
| Reason for Discontinuation | header | | 0 | |
| Adverse event | data | count_pct | 1 | DCSREAS = 'ADVERSE EVENT' |
| Disease progression | data | count_pct | 1 | Optional: oncology studies only |
| Withdrawal by subject | data | count_pct | 1 | |
| Physician decision | data | count_pct | 1 | |
| Protocol deviation | data | count_pct | 1 | |
| Lost to follow-up | data | count_pct | 1 | |
| Death | data | count_pct | 1 | |
| Other | data | count_pct | 1 | |
| | spacer | | 0 | |
| Study Status | header | | 0 | |
| Completed study | data | count_pct | 1 | Completed all follow-up |
| Ongoing | data | count_pct | 1 | Still in follow-up |
| Discontinued from study | data | count_pct | 1 | |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|-------------|---------|
| count | xxx | 245 |
| count_pct | xxx (xx.x) | 12 (4.9) |

### Calculation Methods

- **Screened**: Count of all subjects who signed informed consent (ADSL where SUBJID is not null)
- **Screen Failures**: Screened minus randomized; percentage denominator = N screened
- **Randomized**: RANDFL = 'Y'; percentage denominator switches to N randomized for all subsequent rows
- **Treated**: At least one dose of study treatment (SAFFL = 'Y')
- **Discontinuation reasons**: From DCSREAS in ADSL; mutually exclusive categories
- **Study status**: From EOSSTT in ADSL
- **SAS**: PROC FREQ for counts and percentages

### Footnotes

1. All Screened Population.
2. Percentages for screening based on N screened; all others based on N randomized.

### Figures

- **CONSORT Flow Diagram**: Enrollment → Screening → Randomization → Treatment Arms → Completed/Discontinued → Analysis Populations.

---

## Table: Protocol Deviations

| Setting | Value |
|---------|-------|
| Population | ITT |
| Source | ADSL |
| Orientation | PORTRAIT |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Subjects with at least one important protocol deviation, n (%) | data | count_pct | 0 | **Bold** |
| | spacer | | 0 | |
| Category of Deviation | header | | 0 | |
| Inclusion/exclusion criteria not met | data | count_pct | 1 | |
| Prohibited concomitant medication | data | count_pct | 1 | |
| Incorrect study drug administration | data | count_pct | 1 | |
| Missed visit/assessment outside window | data | count_pct | 1 | |
| Informed consent issue | data | count_pct | 1 | |
| Other | data | count_pct | 1 | |
| | spacer | | 0 | |
| Impact on Analysis Population | header | | 0 | |
| Excluded from Per-Protocol Population, n (%) | data | count_pct | 1 | PPROTFL ≠ 'Y' |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|-------------|---------|
| count_pct | xxx (xx.x) | 18 (7.3) |

### Calculation Methods

- **Important protocol deviations**: Determined by sponsor prior to database lock (blinded review)
- **Categories**: From protocol deviation classification (DVCAT in ADDV or flags in ADSL)
- **Subject counted once**: Per deviation category, regardless of number of deviations
- **PP exclusion**: Linked to PPROTFL flag in ADSL
- **SAS**: PROC FREQ; source may be ADDV dataset or deviation flags in ADSL

### Footnotes

1. ITT Population: All randomized subjects.
2. Important protocol deviations as determined by the sponsor prior to database lock.
3. A subject may have more than one protocol deviation.
