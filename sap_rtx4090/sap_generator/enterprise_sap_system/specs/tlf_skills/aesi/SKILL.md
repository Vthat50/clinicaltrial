---
name: Adverse Events of Special Interest
ich_section: "14.3"
display_order: 14
version: "2.0.0"
---

# Adverse Events of Special Interest

Only included when the protocol defines one or more AESIs. All tables use Safety population.

## What Comes from the Protocol

- **AESI names**: each AESI category defined in the protocol (e.g., Hepatotoxicity, Infusion-Related Reactions, Infections)
- **AESI definitions**: which MedDRA terms define each AESI — either SMQ (Standardised MedDRA Query) or custom preferred term list
- **SMQ scope**: narrow or broad search for each SMQ
- **Severity/seriousness focus**: whether grade ≥3 or serious AESI sub-tables are needed
- **Time windows**: whether AESI analysis is restricted to certain treatment periods

## Column Structure

- **Two-arm with total**: {Arm 1} | {Arm 2} | Total
- Arm names from `facts.arm_names[]`.

---

## Table: AESI — {AESI Name} by SOC and PT

Repeat this table once per AESI defined in the protocol.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADAE |
| Orientation | LANDSCAPE |
| Filter | TRTEMFL = 'Y' AND AESI-specific SMQ or custom preferred term list |

### Rows

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Subjects with at least one {AESI Name} event, n (%) | data | count_pct | 0 | **Bold**; overall count for this AESI |
| | spacer | | 0 | |
| System Organ Class | header | | 0 | Dynamic: SOCs from data within this AESI |
| Preferred Term | data | count_pct | 1 | Dynamic: PTs within SOC |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|-------------|---------|
| count_pct | xxx (xx.x) | 15 (6.1) |

### Calculation Methods

- **AESI identification**: Events matching the AESI definition (SMQ query or custom PT list)
- **SMQ**: MedDRA Standardised MedDRA Query — narrow scope preferred unless protocol specifies broad
- **Custom PT list**: Protocol-specific list of preferred terms defining the AESI
- **Subject counted once**: Per SOC and per PT within the AESI, regardless of number of events
- **Sorting**: SOC by decreasing frequency; PT by decreasing frequency within SOC
- **SAS**: PROC FREQ; merge ADAE with SMQ lookup or custom PT list flag

### Footnotes

1. Safety Population.
2. {AESI Name} defined as: {SMQ name or custom PT list from protocol}.
3. Adverse events coded using MedDRA version XX.X.
4. A subject is counted once in each applicable category.

---

## Table: AESI Summary — Overview of All AESIs

Condition: Only when 2 or more AESIs are defined.

| Setting | Value |
|---------|-------|
| Population | Safety |
| Source | ADAE |
| Orientation | PORTRAIT |
| Filter | TRTEMFL = 'Y' |

### Rows

Repeat per AESI:

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| {AESI Name 1}, n (%) | data | count_pct | 0 | One row per AESI category |
| {AESI Name 2}, n (%) | data | count_pct | 0 | |
| {AESI Name 3}, n (%) | data | count_pct | 0 | |

### Calculation Methods

- **One row per AESI**: Summary count of subjects with at least one event in each AESI category
- **Cross-AESI**: A subject may be counted in multiple AESI categories
- **Denominator**: N = Safety population per arm

### Footnotes

1. Safety Population.
2. Each AESI defined per protocol-specified criteria (SMQ or custom preferred term list).
3. A subject is counted once per AESI category.
