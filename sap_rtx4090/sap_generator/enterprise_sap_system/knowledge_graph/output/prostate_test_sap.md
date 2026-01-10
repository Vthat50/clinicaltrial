# Statistical Analysis Plan (SAP)

**Study Title:** A Randomized Double-Blind Parallel Group Study Comparing Casodex (or Generic Equivalent) 50mg Plus Placebo to Casodex (or Generic Equivalent) 50mg Plus Dutasteride 3.5mg Administered for 18 Months to Men With Prostate Cancer Who Have Failed First-Line Androgen Deprivation Therapy (Assessed by Rising PSA) Followed by a Two-Year Extension Phase

**NCT ID:** NCT00470834  
**Sponsor:** GlaxoSmithKline  
**Phase:** Phase 4

---

## 1. STUDY DESIGN

This is a randomized, double-blind, placebo-controlled, parallel group study in men with prostate cancer who have failed first-line androgen deprivation therapy. A total of 127 participants were randomized to one of two treatment arms:

- **Arm 1 (Experimental):** 50 mg bicalutamide + 3.5 mg dutasteride
- **Arm 2 (Placebo Comparator):** 50 mg bicalutamide + placebo

Treatment duration is 18 months followed by a two-year extension phase.

---

## 2. STUDY OBJECTIVES AND ENDPOINTS

### 2.1 Primary Objective
To compare the time to disease progression between the two treatment arms.

### 2.2 Primary Endpoint
**Time to Disease Progression:** Interval of time between the date of start of treatment and the date of disease progression (up to Study Month 42).

Disease progression is defined as:
- PSA progression from Baseline: PSA value ≥25% and ≥2 ng/mL above Baseline, confirmed by a second PSA value
- PSA progression from nadir, without a 50% decrease from Baseline: PSA value ≥25% and ≥2 ng/mL above nadir, confirmed by a second PSA value  
- PSA progression from nadir, with a 50% or more decrease from Baseline: PSA value ≥50% and ≥2 ng/mL above nadir, confirmed by a second PSA value
- Metastatic disease (radiographic evidence)
- Death due to prostate cancer
- Receipt of post-Baseline rescue medication

PSA confirmation was not required if no subsequent PSA values were available.

### 2.3 Secondary Endpoints
1. **Time to Treatment Failure:** Interval of time between the date of start of treatment and the date of treatment failure (up to Study Month 42)
2. **Number of Participants With PSA Response:** Time from Baseline PSA measurement until the first PSA measurement with a 50% or greater reduction in PSA values (up to Study Month 42)
3. **Change From Baseline in Total PSA:** At Months 6, 12, 18, 21, and 42
4. **Number of Participants With Metastatic Disease:** Interval of time between the date of start of treatment and the date of radiographic evidence of metastatic disease (up to Study Month 42)

---

## 3. ANALYSIS POPULATIONS

### 3.1 Intent-to-Treat (ITT) Population
All randomized participants, analyzed according to their randomized treatment assignment.

### 3.2 Per-Protocol (PP) Population
Participants who completed the study without major protocol violations.

### 3.3 Safety Population
All participants who received at least one dose of study medication.

---

## 4. STATISTICAL METHODS

### 4.1 General Considerations
- All statistical tests will be two-sided with a significance level of α = 0.05
- No adjustment for multiplicity will be applied unless specified
- Missing data patterns will be described and appropriate methods applied

### 4.2 Primary Analysis

**Time to Disease Progression**
- **Method:** Cox proportional hazards regression model
- **Primary Comparison:** Hazard ratio (HR) and 95% confidence interval comparing experimental arm vs. placebo arm
- **Censoring:** Participants without progression will be censored at the date of latest follow-up information
- **Graphical Display:** Kaplan-Meier curves by treatment arm
- **Population:** ITT population (primary); PP population (sensitivity analysis)

### 4.3 Secondary Analyses

**Time to Treatment Failure**
- **Method:** Cox proportional hazards regression model
- **Analysis:** Hazard ratio and 95% CI; Kaplan-Meier curves by treatment arm

**PSA Response**
- **Method:** Logistic regression model
- **Analysis:** Odds ratio and 95% CI for response rate comparison between arms
- **Summary:** Number and percentage of participants with PSA response by treatment arm

**Change From Baseline in Total PSA**
- **Method:** Mixed-effects model for repeated measures (MMRM)
- **Model:** Includes treatment, visit, treatment-by-visit interaction, and baseline PSA as covariates
- **Analysis:** Least squares mean difference and 95% CI at each time point
- **Summary:** Descriptive statistics (n, mean, SD, median, Q1, Q3) by treatment arm and visit

**Metastatic Disease**
- **Method:** Time-to-event analysis using Cox proportional hazards regression
- **Analysis:** Hazard ratio and 95% CI; Kaplan-Meier curves by treatment arm
- **Summary:** Number and percentage of participants developing metastatic disease

---

## 5. BASELINE CHARACTERISTICS

Baseline demographics and disease characteristics will be summarized by treatment arm:
- Age (years)
- ECOG Performance Status (0, 1, 2)
- Baseline PSA (ng/mL)
- Serum Testosterone level
- Time since first-line androgen deprivation therapy failure

Continuous variables: n, mean, SD, median, Q1, Q3, min, max
Categorical variables: n, percentage

---

## 6. SAFETY ANALYSES

Safety analyses will be performed on the Safety Population and summarized by treatment arm:
- Adverse events by system organ class and preferred term
- Serious adverse events
- Adverse events leading to discontinuation
- Deaths

---

## 7. MISSING DATA HANDLING

- Missing data patterns will be characterized and reported
- For time-to-event endpoints: Censoring as described above
- For continuous endpoints: MMRM approach assumes missing at random (MAR)
- Sensitivity analyses may be conducted under alternative missing data assumptions

---

## 8. SENSITIVITY ANALYSES

- Primary endpoint analysis in PP population
- Alternative definitions of disease progression if applicable
- Sensitivity to missing data assumptions

---

## 9. SOFTWARE

Statistical analyses will be performed using appropriate statistical software (e.g., SAS version 9.4 or later).