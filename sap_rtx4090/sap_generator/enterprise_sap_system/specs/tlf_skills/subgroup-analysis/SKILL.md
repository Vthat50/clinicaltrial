---
name: Subgroup Analysis
ich_section: "14.2"
display_order: 13
version: "2.0.0"
---

# Subgroup Analysis

Only included when the protocol pre-specifies subgroup analyses. All tables use ITT population.

For each primary or key secondary endpoint, generate one table showing the treatment effect across pre-specified subgroups.

## What Comes from the Protocol

- **Pre-specified subgroups**: demographic and baseline variables for subgroup analysis (e.g., age, sex, race, region, ECOG, disease stage)
- **Subgroup categories**: cut-points for each variable (e.g., <65 / ≥65 years)
- **Endpoints**: which primary and key secondary endpoints have subgroup analyses
- **Analysis method**: unstratified Cox within each subgroup (TTE), or difference in rates (binary)
- **Interaction test**: whether treatment-by-subgroup interaction p-value is required
- **Multiplicity note**: subgroup analyses are exploratory — not adjusted for multiplicity

## Column Structure

Each row shows: n per arm | Treatment effect estimate (HR or difference) | 95% CI | Interaction p-value

---

## Table: Subgroup Analysis — {Endpoint Name}

Repeat per primary and key secondary endpoint.

| Setting | Value |
|---------|-------|
| Population | ITT |
| Source | ADTTE, ADRS, or ADEFF (per endpoint type) |
| Orientation | LANDSCAPE |

### Rows

Standard subgroups (include all that are pre-specified in protocol):

| Row Label | Type | Format | Indent | Notes |
|-----------|------|--------|--------|-------|
| Overall | data | hr_ci or diff_ci | 0 | Reference: same as primary analysis |
| | spacer | | 0 | |
| Age | header | | 0 | |
| <65 years | data | hr_ci or diff_ci | 1 | |
| ≥65 years | data | hr_ci or diff_ci | 1 | |
| | spacer | | 0 | |
| Sex | header | | 0 | |
| Male | data | hr_ci or diff_ci | 1 | |
| Female | data | hr_ci or diff_ci | 1 | |
| | spacer | | 0 | |
| Race | header | | 0 | |
| White | data | hr_ci or diff_ci | 1 | |
| Black or African American | data | hr_ci or diff_ci | 1 | |
| Asian | data | hr_ci or diff_ci | 1 | |
| Other | data | hr_ci or diff_ci | 1 | |
| | spacer | | 0 | |
| Region | header | | 0 | |
| North America | data | hr_ci or diff_ci | 1 | |
| Europe | data | hr_ci or diff_ci | 1 | |
| Asia-Pacific | data | hr_ci or diff_ci | 1 | |
| Rest of World | data | hr_ci or diff_ci | 1 | |
| | spacer | | 0 | |
| ECOG Performance Status | header | | 0 | |
| 0 | data | hr_ci or diff_ci | 1 | |
| 1 | data | hr_ci or diff_ci | 1 | |
| ≥2 | data | hr_ci or diff_ci | 1 | |

### Cell Content Examples

| Format | Placeholder | Example |
|--------|-------------|---------|
| hr_ci | x.xx (x.xx, x.xx) | 0.72 (0.54, 0.96) |
| diff_ci | xx.x (xx.x, xx.x) | 12.3 (3.1, 21.5) |

### Calculation Methods

- **Time-to-event endpoints**: Hazard ratio and 95% CI from unstratified Cox proportional hazards model within each subgroup
- **Binary endpoints**: Difference in response rates and 95% CI within each subgroup (Newcombe method)
- **Continuous endpoints**: LS mean difference and 95% CI from ANCOVA within each subgroup
- **Interaction p-value**: From treatment-by-subgroup interaction term in the overall model (one p-value per subgroup variable, not per category)
- **Sample size**: n per arm shown for each subgroup category
- **Overall row**: Reproduces the primary analysis result for reference
- **SAS**: PROC PHREG with treatment*subgroup interaction; PROC FREQ for binary; PROC GLM for continuous

### Footnotes

1. ITT Population.
2. Subgroups pre-specified in the protocol/SAP.
3. For time-to-event endpoints: hazard ratio and 95% CI from unstratified Cox model within each subgroup.
4. For binary endpoints: difference in response rates and 95% CI within each subgroup.
5. Interaction p-value from treatment-by-subgroup interaction term in the model.
6. Subgroup analyses are exploratory; not adjusted for multiplicity.

### Figures

- **Forest Plot**: One per primary/key secondary endpoint. Shows treatment effect estimate and 95% CI for each subgroup as horizontal bars with point estimates. Vertical reference line at HR=1.0 (TTE) or difference=0 (binary/continuous). See figures/SKILL.md.
