"""
Complete TFL (Table/Figure/Listing) Inventory v2.0
===================================================

Comprehensive inventory of 100+ tables, figures, and listings
for Phase 2/3 oncology SAPs.

Follows ICH/FDA guidelines for SAP reporting and CSR presentation.

Structure:
- Section 14.1: Disposition, Demographics, Baseline (15 tables)
- Section 14.2: Efficacy Tables (25 tables)
- Section 14.3: Safety Tables (30 tables)
- Section 14.4: Figures (15 figures)
- Section 16.2: Listings (25 listings)

Total: 110 TFLs
"""

from typing import Dict, List
import json
from pathlib import Path


# =============================================================================
# SECTION 14.1 - DISPOSITION, DEMOGRAPHICS, BASELINE (15 tables)
# =============================================================================

DISPOSITION_TABLES = {
    "14.1.1": {
        "title": "Subject Disposition",
        "population": "All Screened",
        "columns": ["Category", "Treatment A (N=XXX)", "Treatment B (N=XXX)", "Total (N=XXX)"],
        "rows": [
            "Screened",
            "Screen Failures",
            "  Did not meet eligibility criteria",
            "  Withdrew consent",
            "  Lost to follow-up",
            "  Adverse event",
            "  Other",
            "Randomized",
            "Not Treated",
            "Treated (Safety Population)",
            "Completed Treatment",
            "Discontinued Treatment",
            "  Adverse Event",
            "  Disease Progression",
            "  Physician Decision",
            "  Subject Withdrawal",
            "  Lost to Follow-up",
            "  Protocol Deviation",
            "  Death",
            "  Other",
            "Completed Study",
            "Ongoing"
        ],
        "statistics": "n (%)",
        "footnotes": [
            "Percentages based on number screened for screening rows, number randomized for disposition rows.",
            "A subject may have multiple reasons for screen failure or discontinuation."
        ]
    },

    "14.1.2": {
        "title": "Demographics and Baseline Characteristics (ITT Population)",
        "population": "ITT",
        "parameters": [
            {"name": "Age (years)", "statistics": ["n", "Mean (SD)", "Median", "Min, Max"]},
            {"name": "Age Group", "categories": ["<65 years", "65 to <75 years", ">=75 years"], "statistics": "n (%)"},
            {"name": "Sex", "categories": ["Male", "Female"], "statistics": "n (%)"},
            {"name": "Race", "categories": ["White", "Black or African American", "Asian", "American Indian or Alaska Native", "Native Hawaiian or Other Pacific Islander", "Multiple", "Other", "Not Reported"], "statistics": "n (%)"},
            {"name": "Ethnicity", "categories": ["Hispanic or Latino", "Not Hispanic or Latino", "Not Reported"], "statistics": "n (%)"},
            {"name": "Weight (kg)", "statistics": ["n", "Mean (SD)", "Median", "Min, Max"]},
            {"name": "Height (cm)", "statistics": ["n", "Mean (SD)", "Median", "Min, Max"]},
            {"name": "BMI (kg/m^2)", "statistics": ["n", "Mean (SD)", "Median", "Min, Max"]},
            {"name": "BSA (m^2)", "statistics": ["n", "Mean (SD)", "Median", "Min, Max"]},
            {"name": "ECOG Performance Status", "categories": ["0", "1", "2"], "statistics": "n (%)"},
            {"name": "Geographic Region", "categories": ["North America", "Western Europe", "Eastern Europe", "Asia-Pacific", "Rest of World"], "statistics": "n (%)"}
        ],
        "footnotes": [
            "BMI = Weight (kg) / Height (m)^2",
            "BSA = Body Surface Area calculated using Dubois formula",
            "ECOG = Eastern Cooperative Oncology Group"
        ]
    },

    "14.1.3": {
        "title": "Disease Characteristics at Baseline (ITT Population)",
        "population": "ITT",
        "parameters": [
            {"name": "Time Since Initial Diagnosis (months)", "statistics": ["n", "Mean (SD)", "Median", "Min, Max"]},
            {"name": "Disease Stage at Study Entry", "categories": ["Stage IIIB", "Stage IV"], "statistics": "n (%)"},
            {"name": "Histology", "categories": ["Adenocarcinoma", "Squamous Cell Carcinoma", "Large Cell Carcinoma", "Other"], "statistics": "n (%)"},
            {"name": "Sites of Metastases", "categories": ["Liver", "Lung", "Bone", "Brain", "Lymph Node", "Adrenal", "Soft Tissue", "Other"], "statistics": "n (%)"},
            {"name": "Number of Metastatic Sites", "categories": ["1", "2", ">=3"], "statistics": "n (%)"},
            {"name": "Sum of Target Lesion Diameters (mm)", "statistics": ["n", "Mean (SD)", "Median", "Min, Max"]},
            {"name": "Number of Target Lesions", "categories": ["1", "2", "3", "4", "5"], "statistics": "n (%)"},
            {"name": "Measurable Disease at Baseline", "categories": ["Yes", "No"], "statistics": "n (%)"},
            {"name": "CNS Metastases at Baseline", "categories": ["Yes", "No"], "statistics": "n (%)"}
        ]
    },

    "14.1.4": {
        "title": "Biomarker Status at Baseline (ITT Population)",
        "population": "ITT",
        "parameters": [
            {"name": "PD-L1 Expression (TPS)", "categories": ["<1%", "1-49%", ">=50%", "Unknown/Not Evaluable"], "statistics": "n (%)"},
            {"name": "PD-L1 Expression (CPS)", "categories": ["<1", "1-9", ">=10", "Unknown"], "statistics": "n (%)"},
            {"name": "Mutation Status [specify gene]", "categories": ["Wild-type", "Mutant", "Unknown"], "statistics": "n (%)"},
            {"name": "TMB Status", "categories": ["Low (<10 mut/Mb)", "High (>=10 mut/Mb)", "Unknown"], "statistics": "n (%)"},
            {"name": "MSI Status", "categories": ["MSS/pMMR", "MSI-H/dMMR", "Unknown"], "statistics": "n (%)"}
        ],
        "footnotes": [
            "TPS = Tumor Proportion Score",
            "CPS = Combined Positive Score",
            "TMB = Tumor Mutational Burden",
            "MSI = Microsatellite Instability"
        ]
    },

    "14.1.5": {
        "title": "Prior Anti-Cancer Therapy (ITT Population)",
        "population": "ITT",
        "parameters": [
            {"name": "Any Prior Systemic Therapy", "categories": ["Yes", "No"], "statistics": "n (%)"},
            {"name": "Number of Prior Lines of Therapy", "categories": ["0", "1", "2", ">=3"], "statistics": "n (%)"},
            {"name": "Type of Prior Therapy", "categories": ["Chemotherapy", "Targeted Therapy", "Immunotherapy", "Hormone Therapy"], "statistics": "n (%)"},
            {"name": "Prior Platinum-based Chemotherapy", "categories": ["Yes", "No"], "statistics": "n (%)"},
            {"name": "Prior Radiotherapy", "categories": ["Yes", "No"], "statistics": "n (%)"},
            {"name": "Prior Surgery", "categories": ["Yes", "No"], "statistics": "n (%)"},
            {"name": "Best Response to Last Prior Therapy", "categories": ["CR", "PR", "SD", "PD", "Unknown"], "statistics": "n (%)"}
        ]
    },

    "14.1.6": {
        "title": "Medical History by System Organ Class and Preferred Term (Safety Population)",
        "population": "Safety",
        "columns": ["System Organ Class / Preferred Term", "Treatment A n (%)", "Treatment B n (%)", "Total n (%)"],
        "sorting": "SOC alphabetically, PT by decreasing frequency",
        "coding": "MedDRA version XX.X",
        "threshold": "Display PTs occurring in >=5% of any treatment group"
    },

    "14.1.7": {
        "title": "Prior Medications (Safety Population)",
        "population": "Safety",
        "columns": ["ATC Level 2 / Preferred Name", "Treatment A n (%)", "Treatment B n (%)", "Total n (%)"],
        "definition": "Medications with start date prior to first dose of study drug",
        "sorting": "ATC Level 2 alphabetically, medication name alphabetically",
        "coding": "WHODrug version XXXX"
    },

    "14.1.8": {
        "title": "Concomitant Medications (Safety Population)",
        "population": "Safety",
        "columns": ["ATC Level 2 / Preferred Name", "Treatment A n (%)", "Treatment B n (%)", "Total n (%)"],
        "definition": "Medications with start date on or after first dose and on or before last dose + 28 days",
        "sorting": "ATC Level 2 alphabetically, medication name alphabetically"
    },

    "14.1.9": {
        "title": "Study Drug Exposure (Safety Population)",
        "population": "Safety",
        "parameters": [
            {"name": "Duration of Treatment (days)", "statistics": ["n", "Mean (SD)", "Median", "Min, Max"]},
            {"name": "Duration of Treatment (months)", "statistics": ["n", "Mean (SD)", "Median", "Min, Max"]},
            {"name": "Duration Category", "categories": ["<3 months", "3 to <6 months", "6 to <12 months", ">=12 months"], "statistics": "n (%)"},
            {"name": "Number of Cycles", "statistics": ["n", "Mean (SD)", "Median", "Min, Max"]},
            {"name": "Total Dose Received (mg)", "statistics": ["n", "Mean (SD)", "Median", "Min, Max"]},
            {"name": "Number of Doses Received", "statistics": ["n", "Mean (SD)", "Median", "Min, Max"]},
            {"name": "Relative Dose Intensity (%)", "statistics": ["n", "Mean (SD)", "Median", "Min, Max"]},
            {"name": "Dose Modifications", "categories": ["None", "Dose Reduction", "Dose Interruption", "Both"], "statistics": "n (%)"}
        ],
        "footnotes": [
            "Duration = (Date of last dose - Date of first dose + 1)",
            "Relative Dose Intensity = (Actual dose intensity / Planned dose intensity) x 100"
        ]
    },

    "14.1.10": {
        "title": "Dose Modifications by Reason (Safety Population)",
        "population": "Safety",
        "categories": {
            "dose_reductions": [
                "Any Dose Reduction",
                "  Adverse Event",
                "  Laboratory Abnormality",
                "  Other"
            ],
            "dose_interruptions": [
                "Any Dose Interruption",
                "  Adverse Event",
                "  Laboratory Abnormality",
                "  Scheduling/Administrative",
                "  Other"
            ]
        },
        "columns": ["Category", "Treatment A n (%)", "Treatment B n (%)"]
    },

    "14.1.11": {
        "title": "Protocol Deviations (ITT Population)",
        "population": "ITT",
        "categories": [
            "Any Protocol Deviation",
            "Major Protocol Deviation",
            "  Eligibility criteria not met",
            "  Prohibited concomitant medication",
            "  Wrong treatment administered",
            "  Missed efficacy assessments",
            "  Dosing violation",
            "  GCP non-compliance",
            "Minor Protocol Deviation",
            "  Visit out of window",
            "  Informed consent issue",
            "  Other"
        ],
        "columns": ["Category", "Treatment A n (%)", "Treatment B n (%)", "Total n (%)"]
    },

    "14.1.12": {
        "title": "Analysis Populations",
        "population": "All Randomized",
        "rows": [
            "Randomized",
            "Intent-to-Treat (ITT) Population",
            "  Excluded from ITT",
            "Full Analysis Set (FAS)",
            "  Excluded from FAS",
            "Safety Population",
            "  Excluded from Safety Population",
            "Per-Protocol Population",
            "  Excluded from PP",
            "Efficacy Evaluable Population",
            "Response Evaluable Population"
        ],
        "footnotes": [
            "ITT = All randomized subjects analyzed as randomized",
            "FAS = All randomized subjects with at least one post-baseline efficacy assessment",
            "Safety = All subjects who received at least one dose of study drug, analyzed as treated",
            "PP = FAS without major protocol deviations"
        ]
    },

    "14.1.13": {
        "title": "Stratification Factors as Randomized vs CRF Derived (ITT Population)",
        "population": "ITT",
        "purpose": "Compare IXRS stratification factors with CRF-derived values",
        "columns": ["Stratification Factor", "Category", "IXRS n (%)", "CRF n (%)", "Discrepancy n"],
        "factors": [
            "Geographic Region",
            "ECOG Performance Status",
            "Prior Lines of Therapy",
            "Biomarker Status"
        ]
    },

    "14.1.14": {
        "title": "Baseline Laboratory Values (Safety Population)",
        "population": "Safety",
        "parameters": {
            "hematology": ["Hemoglobin (g/dL)", "WBC (10^9/L)", "ANC (10^9/L)", "Lymphocytes (10^9/L)", "Platelets (10^9/L)"],
            "chemistry": ["ALT (U/L)", "AST (U/L)", "Total Bilirubin (mg/dL)", "ALP (U/L)", "Albumin (g/dL)", "Creatinine (mg/dL)", "BUN (mg/dL)", "LDH (U/L)"],
            "electrolytes": ["Sodium (mEq/L)", "Potassium (mEq/L)", "Calcium (mg/dL)", "Magnesium (mg/dL)", "Phosphorus (mg/dL)"]
        },
        "statistics": ["n", "Mean (SD)", "Median", "Min, Max"]
    },

    "14.1.15": {
        "title": "Baseline Vital Signs and Physical Examination (Safety Population)",
        "population": "Safety",
        "parameters": [
            {"name": "Systolic Blood Pressure (mmHg)", "statistics": ["n", "Mean (SD)", "Median", "Min, Max"]},
            {"name": "Diastolic Blood Pressure (mmHg)", "statistics": ["n", "Mean (SD)", "Median", "Min, Max"]},
            {"name": "Heart Rate (bpm)", "statistics": ["n", "Mean (SD)", "Median", "Min, Max"]},
            {"name": "Body Temperature (C)", "statistics": ["n", "Mean (SD)", "Median", "Min, Max"]},
            {"name": "Respiratory Rate (breaths/min)", "statistics": ["n", "Mean (SD)", "Median", "Min, Max"]},
            {"name": "SpO2 (%)", "statistics": ["n", "Mean (SD)", "Median", "Min, Max"]}
        ]
    }
}


# =============================================================================
# SECTION 14.2 - EFFICACY TABLES (25 tables)
# =============================================================================

EFFICACY_TABLES = {
    # Primary Endpoint Tables
    "14.2.1.1": {
        "title": "Summary of Progression-Free Survival (ITT Population, IRC Assessment)",
        "endpoint": "Primary",
        "columns": ["Parameter", "Treatment A (N=XXX)", "Treatment B (N=XXX)"],
        "rows": [
            "Number of Events, n (%)",
            "  Disease Progression",
            "  Death",
            "Number Censored, n (%)",
            "",
            "Kaplan-Meier Estimates",
            "  25th Percentile (months) [95% CI]",
            "  Median (months) [95% CI]",
            "  75th Percentile (months) [95% CI]",
            "",
            "Event-free Probability [95% CI]",
            "  At 6 Months",
            "  At 12 Months",
            "  At 18 Months",
            "  At 24 Months",
            "",
            "Stratified Analysis",
            "  Hazard Ratio [95% CI]",
            "  P-value (Stratified Log-rank)",
            "",
            "Unstratified Analysis",
            "  Hazard Ratio [95% CI]",
            "  P-value (Unstratified Log-rank)"
        ],
        "footnotes": [
            "PFS = Time from randomization to first documented progression per RECIST v1.1 or death from any cause.",
            "IRC = Independent Radiology Committee assessment.",
            "Hazard ratio <1 favors Treatment A.",
            "Stratified by [list stratification factors].",
            "95% CI for median calculated using Brookmeyer-Crowley method.",
            "95% CI for KM estimates calculated using Greenwood formula with log-log transformation."
        ]
    },

    "14.2.1.2": {
        "title": "Summary of Progression-Free Survival (ITT Population, Investigator Assessment)",
        "endpoint": "Sensitivity",
        "columns": ["Parameter", "Treatment A (N=XXX)", "Treatment B (N=XXX)"],
        "rows": "Same structure as 14.2.1.1",
        "note": "Sensitivity analysis using investigator assessment"
    },

    "14.2.1.3": {
        "title": "Summary of PFS by Censoring Reason (ITT Population, IRC Assessment)",
        "columns": ["Censoring Reason", "Treatment A n (%)", "Treatment B n (%)", "Total n (%)"],
        "rows": [
            "Event - Documented Progression",
            "Event - Death",
            "Censored - Ongoing",
            "Censored - New Anticancer Therapy",
            "Censored - Missed Assessments",
            "Censored - Lost to Follow-up",
            "Censored - Withdrew Consent",
            "Censored - No Post-Baseline Assessment"
        ]
    },

    "14.2.2.1": {
        "title": "Summary of Overall Survival (ITT Population)",
        "endpoint": "Secondary/Co-Primary",
        "columns": ["Parameter", "Treatment A (N=XXX)", "Treatment B (N=XXX)"],
        "rows": [
            "Number of Deaths, n (%)",
            "Number Censored, n (%)",
            "",
            "Kaplan-Meier Estimates",
            "  25th Percentile (months) [95% CI]",
            "  Median (months) [95% CI]",
            "  75th Percentile (months) [95% CI]",
            "",
            "Survival Probability [95% CI]",
            "  At 12 Months",
            "  At 24 Months",
            "  At 36 Months",
            "  At 48 Months",
            "",
            "Stratified Analysis",
            "  Hazard Ratio [95% CI]",
            "  P-value (Stratified Log-rank)",
            "",
            "Unstratified Analysis",
            "  Hazard Ratio [95% CI]",
            "  P-value (Unstratified Log-rank)"
        ],
        "footnotes": [
            "OS = Time from randomization to death from any cause.",
            "Subjects alive at data cutoff are censored at last known alive date.",
            "Hazard ratio <1 favors Treatment A."
        ]
    },

    "14.2.2.2": {
        "title": "Summary of OS Follow-up (ITT Population)",
        "columns": ["Parameter", "Treatment A (N=XXX)", "Treatment B (N=XXX)", "Total (N=XXX)"],
        "rows": [
            "Follow-up Duration (months)",
            "  n",
            "  Mean (SD)",
            "  Median",
            "  Min, Max",
            "",
            "Survival Status at Data Cutoff",
            "  Alive, n (%)",
            "  Dead, n (%)",
            "  Unknown/Lost to Follow-up, n (%)",
            "",
            "Maturity",
            "  Events/Planned Events",
            "  % Maturity"
        ]
    },

    # Response Tables
    "14.2.3.1": {
        "title": "Best Overall Response (ITT Population, IRC Assessment)",
        "columns": ["Response Category", "Treatment A (N=XXX) n (%)", "Treatment B (N=XXX) n (%)"],
        "rows": [
            "Complete Response (CR)",
            "Partial Response (PR)",
            "Stable Disease (SD)",
            "Progressive Disease (PD)",
            "Not Evaluable (NE)",
            "",
            "Objective Response Rate (CR+PR)",
            "  95% Exact CI",
            "  Difference vs Control [95% CI]",
            "  Odds Ratio [95% CI]",
            "  P-value (CMH Test)",
            "",
            "Disease Control Rate (CR+PR+SD)",
            "  95% Exact CI",
            "",
            "Clinical Benefit Rate (CR+PR+SD>=24 weeks)",
            "  95% Exact CI"
        ],
        "footnotes": [
            "Response assessed per RECIST v1.1.",
            "CR and PR require confirmation >= 4 weeks after initial response.",
            "SD requires minimum duration of 6 weeks from baseline.",
            "95% CI calculated using Clopper-Pearson exact method.",
            "CMH test stratified by [stratification factors]."
        ]
    },

    "14.2.3.2": {
        "title": "Best Overall Response (ITT Population, Investigator Assessment)",
        "columns": "Same as 14.2.3.1",
        "rows": "Same as 14.2.3.1",
        "note": "Sensitivity analysis"
    },

    "14.2.3.3": {
        "title": "Confirmed vs Unconfirmed Response (ITT Population, IRC)",
        "columns": ["Category", "Treatment A n (%)", "Treatment B n (%)", "Total n (%)"],
        "rows": [
            "Confirmed CR",
            "Unconfirmed CR (pending confirmation)",
            "Confirmed PR",
            "Unconfirmed PR (pending confirmation)",
            "Confirmed ORR (CR+PR)",
            "Unconfirmed ORR (including unconfirmed)"
        ]
    },

    "14.2.4.1": {
        "title": "Duration of Response (Responder Population, IRC Assessment)",
        "population": "Responders (confirmed CR or PR)",
        "columns": ["Parameter", "Treatment A (N=XXX)", "Treatment B (N=XXX)"],
        "rows": [
            "Number of Responders (CR+PR)",
            "Number with Subsequent Progression or Death, n (%)",
            "Number Censored, n (%)",
            "",
            "Kaplan-Meier Estimates",
            "  Median DOR (months) [95% CI]",
            "  Range (Min, Max)",
            "",
            "Probability of Maintained Response [95% CI]",
            "  At 6 Months",
            "  At 9 Months",
            "  At 12 Months",
            "  At 18 Months"
        ],
        "footnotes": [
            "DOR = Time from first confirmed response to progression or death.",
            "Subjects without progression are censored at last tumor assessment.",
            "Responder Population = Subjects with confirmed CR or PR."
        ]
    },

    "14.2.4.2": {
        "title": "Time to Response (Responder Population, IRC Assessment)",
        "population": "Responders",
        "columns": ["Parameter", "Treatment A (N=XXX)", "Treatment B (N=XXX)"],
        "rows": [
            "Number of Responders (CR+PR)",
            "",
            "Time to Response (months)",
            "  n",
            "  Mean (SD)",
            "  Median",
            "  Min, Max",
            "  Q1, Q3"
        ]
    },

    # Tumor Assessment Tables
    "14.2.5.1": {
        "title": "Target Lesion Assessment Over Time (ITT Population, IRC)",
        "columns": ["Visit", "n", "Mean % Change (SD)", "Median % Change", "Min, Max"],
        "rows": [
            "Baseline",
            "Week 6",
            "Week 12",
            "Week 18",
            "Week 24",
            "Week 36",
            "Week 48",
            "Best Response"
        ]
    },

    "14.2.5.2": {
        "title": "Non-Target Lesion Assessment Over Time (ITT Population, IRC)",
        "columns": ["Visit", "n", "CR/Complete Disappearance n (%)", "Non-CR/Non-PD n (%)", "PD n (%)", "NE n (%)"],
        "rows": ["Week 6", "Week 12", "Week 18", "Week 24", "Best Response"]
    },

    "14.2.5.3": {
        "title": "New Lesion Assessment Over Time (ITT Population, IRC)",
        "columns": ["Visit", "n", "No New Lesions n (%)", "New Lesions Present n (%)"],
        "rows": ["Week 6", "Week 12", "Week 18", "Week 24", "Week 36", "Week 48"]
    },

    # Sensitivity Analysis Tables
    "14.2.6.1": {
        "title": "Sensitivity Analyses for PFS (ITT Population)",
        "columns": ["Analysis", "Events n (%)", "HR [95% CI]", "P-value"],
        "analyses": [
            "Primary Analysis (IRC, Stratified)",
            "Investigator Assessment",
            "Unstratified Analysis",
            "Per-Protocol Population",
            "Excluding Early Progressors (PFS <= 6 weeks)",
            "Including Post-Local-PD Scans",
            "Deaths After Missed Visits as Events",
            "Adjusted Cox Model (baseline covariates)",
            "RECIST 1.1 Per Protocol (strict criteria)"
        ]
    },

    "14.2.6.2": {
        "title": "Sensitivity Analyses for OS (ITT Population)",
        "columns": ["Analysis", "Events n (%)", "HR [95% CI]", "P-value"],
        "analyses": [
            "Primary Analysis (Stratified)",
            "Unstratified Analysis",
            "Per-Protocol Population",
            "RPSFT-Adjusted (Crossover-Corrected)",
            "IPCW-Adjusted",
            "Excluding Subjects Who Crossed Over"
        ]
    },

    # Subgroup Analysis Tables
    "14.2.7.1": {
        "title": "Subgroup Analysis of PFS (ITT Population, IRC)",
        "format": "Forest Plot Data",
        "subgroups": [
            "Overall",
            "Age (<65 / >=65 years)",
            "Age (<75 / >=75 years)",
            "Sex (Male / Female)",
            "Race (White / Non-White)",
            "Race (Asian / Non-Asian)",
            "ECOG PS (0 / 1)",
            "Geographic Region (North America / Europe / Asia / ROW)",
            "Disease Stage (IIIB / IV)",
            "Prior Lines (0-1 / >=2)",
            "Histology (Squamous / Non-Squamous)",
            "PD-L1 (<1% / 1-49% / >=50%)",
            "Liver Metastases (Yes / No)",
            "Brain Metastases (Yes / No)",
            "Baseline Tumor Burden (<Median / >=Median)",
            "Number of Metastatic Sites (<3 / >=3)",
            "LDH (<=ULN / >ULN)"
        ],
        "columns": ["Subgroup", "Treatment A Events/N", "Treatment B Events/N", "HR [95% CI]", "Interaction P"]
    },

    "14.2.7.2": {
        "title": "Subgroup Analysis of OS (ITT Population)",
        "format": "Forest Plot Data",
        "subgroups": "Same as 14.2.7.1",
        "columns": ["Subgroup", "Treatment A Events/N", "Treatment B Events/N", "HR [95% CI]", "Interaction P"]
    },

    "14.2.7.3": {
        "title": "Subgroup Analysis of ORR (ITT Population, IRC)",
        "subgroups": "Same as 14.2.7.1",
        "columns": ["Subgroup", "Treatment A Resp/N (%)", "Treatment B Resp/N (%)", "Difference [95% CI]"]
    },

    # Additional Efficacy Tables
    "14.2.8.1": {
        "title": "Subsequent Anti-Cancer Therapy (ITT Population)",
        "columns": ["Category", "Treatment A n (%)", "Treatment B n (%)", "Total n (%)"],
        "categories": [
            "Any Subsequent Therapy",
            "Systemic Therapy",
            "  Chemotherapy",
            "  Immunotherapy",
            "  Targeted Therapy",
            "  Hormone Therapy",
            "  Other Systemic",
            "Radiotherapy",
            "Surgery",
            "Best Supportive Care Only",
            "None"
        ]
    },

    "14.2.8.2": {
        "title": "Time to Subsequent Therapy (ITT Population)",
        "columns": ["Parameter", "Treatment A (N=XXX)", "Treatment B (N=XXX)"],
        "rows": [
            "Events (started subsequent therapy), n (%)",
            "Censored, n (%)",
            "",
            "Kaplan-Meier Estimates",
            "  Median (months) [95% CI]",
            "",
            "Hazard Ratio [95% CI]",
            "P-value"
        ]
    },

    "14.2.9.1": {
        "title": "PFS2 - Progression-Free Survival on Next-Line Therapy (ITT Population)",
        "definition": "Time from randomization to progression on next-line therapy or death",
        "columns": ["Parameter", "Treatment A (N=XXX)", "Treatment B (N=XXX)"],
        "rows": [
            "Events, n (%)",
            "Censored, n (%)",
            "Median PFS2 (months) [95% CI]",
            "Hazard Ratio [95% CI]",
            "P-value"
        ]
    },

    "14.2.10.1": {
        "title": "Time to Deterioration in PRO Scores (ITT Population)",
        "instruments": ["EORTC QLQ-C30 Global Health", "EORTC QLQ-C30 Physical Functioning", "Lung Cancer Module Symptoms"],
        "columns": ["PRO Domain", "Treatment A Events/N", "Treatment B Events/N", "Median TTD Months [95% CI]", "HR [95% CI]"],
        "definition": "Time to first >= 10-point decrease from baseline (confirmed at next assessment)"
    },

    "14.2.10.2": {
        "title": "PRO Scores Over Time (ITT Population)",
        "columns": ["Visit", "Treatment A (n, Mean, SD)", "Treatment B (n, Mean, SD)", "LS Mean Difference [95% CI]"],
        "domains": ["Global Health Status", "Physical Functioning", "Role Functioning", "Fatigue", "Pain"],
        "timepoints": ["Baseline", "Week 6", "Week 12", "Week 24", "Week 48", "EOT"]
    },

    "14.2.11.1": {
        "title": "RECIST 1.1 Response by Baseline Characteristics (ITT Population, IRC)",
        "columns": ["Characteristic", "n", "ORR n (%)", "DCR n (%)", "Median PFS [95% CI]"],
        "characteristics": [
            "Overall",
            "PD-L1 <1%",
            "PD-L1 1-49%",
            "PD-L1 >=50%",
            "Liver Metastases - Yes",
            "Liver Metastases - No",
            "Prior IO - Yes",
            "Prior IO - No"
        ]
    }
}


# =============================================================================
# SECTION 14.3 - SAFETY TABLES (30 tables)
# =============================================================================

SAFETY_TABLES = {
    "14.3.1.1": {
        "title": "Overview of Treatment-Emergent Adverse Events (Safety Population)",
        "columns": ["Category", "Treatment A (N=XXX) n (%)", "Treatment B (N=XXX) n (%)"],
        "rows": [
            "Subjects with at least one TEAE",
            "Subjects with at least one Grade >=3 TEAE",
            "Subjects with at least one Grade 4 TEAE",
            "Subjects with at least one Grade 5 TEAE (Death)",
            "Subjects with at least one Serious TEAE",
            "Subjects with at least one Treatment-Related TEAE",
            "Subjects with at least one Treatment-Related Grade >=3 TEAE",
            "Subjects with at least one Treatment-Related Serious TEAE",
            "Subjects with TEAE Leading to Treatment Discontinuation",
            "Subjects with TEAE Leading to Dose Reduction",
            "Subjects with TEAE Leading to Dose Interruption",
            "Subjects with TEAE Leading to Death"
        ],
        "footnotes": [
            "TEAE = Treatment-emergent adverse event with onset on or after first dose through 28 days after last dose.",
            "A subject with multiple events is counted once per category.",
            "Grading per NCI-CTCAE version 5.0.",
            "Treatment-related = Possibly, Probably, or Definitely Related as assessed by Investigator."
        ]
    },

    "14.3.1.2": {
        "title": "TEAEs by System Organ Class and Preferred Term (Safety Population) - All Grades",
        "columns": [
            "System Organ Class / Preferred Term",
            "Treatment A (N=XXX) All Grades n (%)",
            "Treatment A Grade >=3 n (%)",
            "Treatment B (N=XXX) All Grades n (%)",
            "Treatment B Grade >=3 n (%)"
        ],
        "sorting": "SOC alphabetically, PT by decreasing frequency in Treatment A",
        "counting": "Subject counted once per PT at worst grade",
        "footnotes": [
            "Adverse events coded using MedDRA version 26.0.",
            "Graded using NCI-CTCAE version 5.0."
        ]
    },

    "14.3.1.3": {
        "title": "TEAEs Occurring in >=10% of Subjects in Any Treatment Group (Safety Population)",
        "columns": [
            "Preferred Term",
            "Treatment A (N=XXX) All Grades n (%)",
            "Treatment A Grade >=3 n (%)",
            "Treatment B (N=XXX) All Grades n (%)",
            "Treatment B Grade >=3 n (%)"
        ],
        "sorting": "By decreasing frequency in Treatment A",
        "threshold": ">=10% in any treatment group"
    },

    "14.3.1.4": {
        "title": "TEAEs Occurring in >=5% of Subjects in Any Treatment Group (Safety Population)",
        "columns": "Same as 14.3.1.3",
        "threshold": ">=5% in any treatment group"
    },

    "14.3.2.1": {
        "title": "Treatment-Related TEAEs by SOC and PT (Safety Population)",
        "columns": "Same as 14.3.1.2",
        "population": "Treatment-related TEAEs only",
        "definition": "Possibly, Probably, or Definitely Related"
    },

    "14.3.2.2": {
        "title": "Treatment-Related TEAEs Occurring in >=5% (Safety Population)",
        "columns": "Same as 14.3.1.3",
        "population": "Treatment-related TEAEs only",
        "threshold": ">=5%"
    },

    "14.3.3.1": {
        "title": "Grade >=3 TEAEs by SOC and PT (Safety Population)",
        "columns": [
            "System Organ Class / Preferred Term",
            "Treatment A (N=XXX) n (%)",
            "Treatment B (N=XXX) n (%)"
        ],
        "population": "Grade 3, 4, or 5 TEAEs only"
    },

    "14.3.3.2": {
        "title": "Grade 4 and 5 TEAEs by SOC and PT (Safety Population)",
        "columns": "Same as 14.3.3.1",
        "population": "Grade 4 or 5 TEAEs only"
    },

    "14.3.4.1": {
        "title": "Serious Adverse Events by SOC and PT (Safety Population)",
        "columns": [
            "System Organ Class / Preferred Term",
            "Treatment A (N=XXX) n (%)",
            "Treatment B (N=XXX) n (%)"
        ],
        "definition": "SAE = Death, Life-threatening, Hospitalization, Disability, Congenital anomaly, Important medical event"
    },

    "14.3.4.2": {
        "title": "Treatment-Related Serious Adverse Events by SOC and PT (Safety Population)",
        "columns": "Same as 14.3.4.1",
        "population": "Treatment-related SAEs only"
    },

    "14.3.5.1": {
        "title": "TEAEs Leading to Treatment Discontinuation by SOC and PT (Safety Population)",
        "columns": [
            "System Organ Class / Preferred Term",
            "Treatment A (N=XXX) n (%)",
            "Treatment B (N=XXX) n (%)"
        ]
    },

    "14.3.5.2": {
        "title": "TEAEs Leading to Dose Modification by SOC and PT (Safety Population)",
        "columns": [
            "System Organ Class / Preferred Term",
            "Treatment A - Reduction n (%)",
            "Treatment A - Interruption n (%)",
            "Treatment B - Reduction n (%)",
            "Treatment B - Interruption n (%)"
        ]
    },

    "14.3.6.1": {
        "title": "Deaths Overview (Safety Population)",
        "columns": ["Category", "Treatment A (N=XXX) n (%)", "Treatment B (N=XXX) n (%)"],
        "rows": [
            "All Deaths",
            "Deaths During Treatment Period (first dose to last dose + 28 days)",
            "  Disease Progression",
            "  Adverse Event (Treatment-Related)",
            "  Adverse Event (Not Treatment-Related)",
            "  Other",
            "Deaths After Treatment Period (>28 days after last dose)",
            "  Disease Progression",
            "  Adverse Event",
            "  Other/Unknown"
        ]
    },

    "14.3.6.2": {
        "title": "On-Treatment Deaths by Cause (Safety Population)",
        "columns": ["Primary Cause of Death", "Treatment A (N=XXX) n (%)", "Treatment B (N=XXX) n (%)"],
        "rows": [
            "Disease Progression",
            "Respiratory Failure",
            "Sepsis",
            "Cardiac Event",
            "Hemorrhage",
            "Multi-organ Failure",
            "Other"
        ]
    },

    "14.3.7.1": {
        "title": "Laboratory Parameters Summary Statistics (Safety Population)",
        "parameters": {
            "hematology": ["Hemoglobin", "WBC", "ANC", "Lymphocytes", "Platelets"],
            "chemistry": ["ALT", "AST", "Total Bilirubin", "ALP", "Albumin", "Creatinine", "LDH"]
        },
        "timepoints": ["Baseline", "Week 6", "Week 12", "Week 24", "EOT", "Worst Post-Baseline"],
        "statistics": ["n", "Mean (SD)", "Median", "Min, Max"],
        "additional": "Change from Baseline"
    },

    "14.3.7.2": {
        "title": "Shift Table: Hematology Parameters (Safety Population)",
        "format": "Baseline CTCAE Grade vs Worst Post-Baseline CTCAE Grade",
        "parameters": ["ANC", "Hemoglobin", "Lymphocytes", "Platelets"],
        "columns": ["Baseline Grade", "Grade 0", "Grade 1", "Grade 2", "Grade 3", "Grade 4", "Total"],
        "rows": ["Grade 0", "Grade 1", "Grade 2", "Grade 3", "Grade 4", "Total"]
    },

    "14.3.7.3": {
        "title": "Shift Table: Chemistry Parameters (Safety Population)",
        "format": "Same as 14.3.7.2",
        "parameters": ["ALT", "AST", "Total Bilirubin", "Creatinine"]
    },

    "14.3.7.4": {
        "title": "Potentially Clinically Significant Laboratory Abnormalities (Safety Population)",
        "columns": ["Parameter / Criterion", "Treatment A (N=XXX) n (%)", "Treatment B (N=XXX) n (%)"],
        "criteria": {
            "liver": [
                "ALT > 3x ULN",
                "ALT > 5x ULN",
                "ALT > 10x ULN",
                "ALT > 20x ULN",
                "AST > 3x ULN",
                "AST > 5x ULN",
                "Total Bilirubin > 1.5x ULN",
                "Total Bilirubin > 2x ULN",
                "ALP > 2.5x ULN"
            ],
            "renal": [
                "Creatinine > 1.5x ULN",
                "Creatinine > 2x ULN",
                "Creatinine > 3x ULN"
            ],
            "hematology": [
                "Hemoglobin < 10 g/dL",
                "Hemoglobin < 8 g/dL",
                "ANC < 1.5 x 10^9/L",
                "ANC < 1.0 x 10^9/L",
                "ANC < 0.5 x 10^9/L",
                "Platelets < 100 x 10^9/L",
                "Platelets < 75 x 10^9/L",
                "Platelets < 50 x 10^9/L",
                "Platelets < 25 x 10^9/L",
                "Lymphocytes < 0.5 x 10^9/L"
            ]
        }
    },

    "14.3.7.5": {
        "title": "Hy's Law Evaluation (Safety Population)",
        "columns": ["Category", "Treatment A (N=XXX) n (%)", "Treatment B (N=XXX) n (%)"],
        "criteria": [
            "ALT or AST > 3x ULN",
            "Total Bilirubin > 2x ULN",
            "ALT or AST > 3x ULN AND Total Bilirubin > 2x ULN",
            "Potential Hy's Law Cases (manual adjudication)"
        ],
        "footnote": "Per FDA Guidance on Drug-Induced Liver Injury"
    },

    "14.3.8.1": {
        "title": "Vital Signs Summary Statistics (Safety Population)",
        "parameters": ["SBP (mmHg)", "DBP (mmHg)", "Heart Rate (bpm)", "Weight (kg)", "Temperature (C)"],
        "timepoints": ["Baseline", "Week 6", "Week 12", "Week 24", "EOT"],
        "statistics": ["n", "Mean (SD)", "Median", "Change from Baseline Mean (SD)"]
    },

    "14.3.8.2": {
        "title": "Potentially Clinically Significant Vital Signs Values (Safety Population)",
        "columns": ["Criterion", "Treatment A (N=XXX) n (%)", "Treatment B (N=XXX) n (%)"],
        "criteria": [
            "SBP >= 180 mmHg and increase >= 20 mmHg",
            "SBP <= 90 mmHg and decrease >= 20 mmHg",
            "DBP >= 105 mmHg and increase >= 15 mmHg",
            "DBP <= 50 mmHg and decrease >= 15 mmHg",
            "HR >= 120 bpm and increase >= 15 bpm",
            "HR <= 50 bpm and decrease >= 15 bpm",
            "Weight loss >= 10%",
            "Weight gain >= 10%"
        ]
    },

    "14.3.9.1": {
        "title": "ECG Parameters Summary Statistics (Safety Population)",
        "parameters": ["HR (bpm)", "PR Interval (ms)", "QRS Duration (ms)", "QT Interval (ms)", "QTcF Interval (ms)"],
        "timepoints": ["Baseline", "Week 6", "Week 12", "Week 24"],
        "statistics": ["n", "Mean (SD)", "Median", "Change from Baseline Mean (SD)"]
    },

    "14.3.9.2": {
        "title": "QTcF Interval Categories (Safety Population)",
        "columns": ["Category", "Treatment A (N=XXX) n (%)", "Treatment B (N=XXX) n (%)"],
        "absolute_categories": ["<=450 ms", ">450 to <=480 ms", ">480 to <=500 ms", ">500 ms"],
        "change_categories": ["<=30 ms change", ">30 to <=60 ms change", ">60 ms change"]
    },

    "14.3.10.1": {
        "title": "Adverse Events of Special Interest Overview (Safety Population)",
        "columns": ["AESI Category", "Treatment A All Grades n (%)", "Treatment A Grade >=3 n (%)", "Treatment B All Grades n (%)", "Treatment B Grade >=3 n (%)"],
        "categories": [
            "Immune-Related AEs",
            "Infusion-Related Reactions",
            "Hepatotoxicity",
            "Pneumonitis/ILD",
            "Colitis",
            "Nephritis",
            "Thyroid Disorders",
            "Skin Reactions",
            "Cardiac Events",
            "Neurological Events"
        ]
    },

    "14.3.10.2": {
        "title": "Immune-Related Adverse Events Detail (Safety Population)",
        "columns": "Same as 14.3.10.1",
        "categories": [
            "Any irAE",
            "Pneumonitis",
            "Colitis/Diarrhea",
            "Hepatitis",
            "Nephritis",
            "Hypothyroidism",
            "Hyperthyroidism",
            "Hypophysitis",
            "Type 1 Diabetes Mellitus",
            "Myocarditis",
            "Myasthenia Gravis",
            "Guillain-Barre Syndrome",
            "Dermatitis/Rash",
            "Vitiligo"
        ],
        "management": ["Time to onset", "Time to resolution", "Corticosteroid use"]
    },

    "14.3.10.3": {
        "title": "Immune-Related AE Management (Safety Population)",
        "columns": ["irAE Category", "N with Event", "Median Time to Onset (days)", "Median Duration (days)", "Corticosteroid Use n (%)", "Resolved n (%)"]
    },

    "14.3.11.1": {
        "title": "TEAEs by Maximum Grade (Safety Population)",
        "columns": ["Preferred Term", "Grade 1 n (%)", "Grade 2 n (%)", "Grade 3 n (%)", "Grade 4 n (%)", "Grade 5 n (%)", "Total n (%)"],
        "note": "Displays TEAEs occurring in >=5% of any treatment group"
    },

    "14.3.12.1": {
        "title": "Exposure-Adjusted Adverse Event Rates (Safety Population)",
        "columns": ["Preferred Term", "Treatment A Events/100 PY", "Treatment B Events/100 PY"],
        "calculation": "(Number of subjects with event / Total patient-years) × 100",
        "threshold": "TEAEs occurring in >=5%"
    },

    "14.3.13.1": {
        "title": "Adverse Events in Subgroups (Safety Population)",
        "subgroups": ["Age (<65 vs >=65)", "Sex (M vs F)", "Region", "Prior IO (Yes vs No)"],
        "columns": ["Subgroup", "Any TEAE n (%)", "Grade >=3 n (%)", "SAE n (%)", "TEAE Leading to D/C n (%)"]
    }
}


# =============================================================================
# SECTION 14.4 - FIGURES (15 figures)
# =============================================================================

FIGURES = {
    "14.4.1.1": {
        "title": "Kaplan-Meier Plot of Progression-Free Survival (ITT Population, IRC)",
        "type": "Kaplan-Meier",
        "elements": [
            "Survival curves by treatment arm (distinct colors/line styles)",
            "Number at risk table below x-axis",
            "Censoring tick marks on curves",
            "Horizontal dashed line at median (0.5)",
            "Hazard ratio with 95% CI displayed",
            "P-value displayed",
            "Legend"
        ],
        "x_axis": {"label": "Time from Randomization (Months)", "range": [0, 36], "ticks": "Every 3 months"},
        "y_axis": {"label": "Probability of Progression-Free Survival", "range": [0, 1.0]},
        "annotations": "HR = X.XX (95% CI: X.XX-X.XX), P = X.XXXX"
    },

    "14.4.1.2": {
        "title": "Kaplan-Meier Plot of PFS (ITT Population, Investigator Assessment)",
        "type": "Kaplan-Meier",
        "note": "Sensitivity analysis - same format as 14.4.1.1"
    },

    "14.4.2.1": {
        "title": "Kaplan-Meier Plot of Overall Survival (ITT Population)",
        "type": "Kaplan-Meier",
        "elements": "Same as 14.4.1.1",
        "x_axis": {"label": "Time from Randomization (Months)", "range": [0, 48]},
        "y_axis": {"label": "Probability of Overall Survival", "range": [0, 1.0]}
    },

    "14.4.3.1": {
        "title": "Kaplan-Meier Plot of Duration of Response (Responder Population, IRC)",
        "type": "Kaplan-Meier",
        "population": "Subjects with confirmed CR or PR only",
        "y_axis": {"label": "Probability of Maintained Response"}
    },

    "14.4.4.1": {
        "title": "Forest Plot of Subgroup Analyses for PFS (ITT Population, IRC)",
        "type": "Forest Plot",
        "elements": [
            "Subgroup labels (left column)",
            "N per treatment arm (middle columns)",
            "Number of events per arm",
            "Hazard ratio point estimate (square)",
            "95% CI horizontal lines",
            "Vertical reference line at HR=1.0",
            "Favors labels at bottom",
            "Overall HR at top or bottom"
        ],
        "x_axis": {"label": "Hazard Ratio (95% CI)", "scale": "Log scale"},
        "subgroups": "See Table 14.2.7.1"
    },

    "14.4.4.2": {
        "title": "Forest Plot of Subgroup Analyses for OS (ITT Population)",
        "type": "Forest Plot",
        "elements": "Same as 14.4.4.1"
    },

    "14.4.5.1": {
        "title": "Waterfall Plot of Best Percentage Change in Target Lesion Sum (ITT Population, IRC)",
        "type": "Waterfall",
        "elements": [
            "Vertical bars for each subject ordered by % change",
            "Color coding by best overall response (CR=green, PR=blue, SD=yellow, PD=red)",
            "Horizontal reference line at -30% (PR threshold)",
            "Horizontal reference line at +20% (PD threshold)",
            "Y-axis truncated at +100% for readability"
        ],
        "x_axis": {"label": "Subject"},
        "y_axis": {"label": "Best Percentage Change from Baseline (%)"}
    },

    "14.4.5.2": {
        "title": "Waterfall Plot by Treatment Arm (ITT Population, IRC)",
        "type": "Waterfall",
        "format": "Side-by-side panels for each treatment arm"
    },

    "14.4.6.1": {
        "title": "Swimmer Plot of Treatment Duration and Response (ITT Population)",
        "type": "Swimmer Plot",
        "elements": [
            "Horizontal bar for each subject representing treatment duration",
            "Symbols for response events (triangle=PR, circle=CR, X=PD)",
            "Color coding by best overall response",
            "Arrow for ongoing subjects",
            "Subjects sorted by treatment duration"
        ],
        "x_axis": {"label": "Time from First Dose (Months)"},
        "y_axis": {"label": "Subject"}
    },

    "14.4.7.1": {
        "title": "Spider Plot of Individual Subject Tumor Burden Over Time (ITT Population, IRC)",
        "type": "Spider/Spaghetti Plot",
        "elements": [
            "Line for each subject showing % change from baseline over time",
            "Horizontal reference lines at -30% and +20%",
            "Color coding by best overall response or treatment arm"
        ],
        "x_axis": {"label": "Time from Baseline (Weeks)"},
        "y_axis": {"label": "Percentage Change from Baseline in Sum of Target Lesions"}
    },

    "14.4.8.1": {
        "title": "ORR by Subgroup (ITT Population, IRC)",
        "type": "Bar Chart / Forest",
        "elements": [
            "Response rate by subgroup with 95% CI",
            "Reference line at overall ORR"
        ]
    },

    "14.4.9.1": {
        "title": "PRO Scores Over Time - Global Health Status (ITT Population)",
        "type": "Line Plot",
        "elements": [
            "Mean score by treatment arm at each visit",
            "Error bars (95% CI or SE)",
            "Reference line at baseline"
        ],
        "x_axis": {"label": "Study Visit"},
        "y_axis": {"label": "EORTC QLQ-C30 Global Health Status Score"}
    },

    "14.4.10.1": {
        "title": "Time to Deterioration in PRO - Kaplan-Meier (ITT Population)",
        "type": "Kaplan-Meier",
        "y_axis": {"label": "Probability of No Deterioration"},
        "definition": ">=10 point decrease from baseline"
    },

    "14.4.11.1": {
        "title": "Exposure-Response Relationship",
        "type": "Scatter Plot",
        "elements": ["Response status vs drug exposure", "Logistic regression curve"],
        "x_axis": {"label": "Drug Exposure (AUC or Cmax)"},
        "y_axis": {"label": "Probability of Response"}
    },

    "14.4.12.1": {
        "title": "eDISH Plot for Hepatotoxicity Assessment (Safety Population)",
        "type": "Scatter Plot",
        "elements": [
            "X-axis: Peak ALT/ULN",
            "Y-axis: Peak TBL/ULN",
            "Quadrant lines at 3x ULN (ALT) and 2x ULN (TBL)",
            "Points colored by treatment arm",
            "Hy's Law quadrant labeled"
        ]
    }
}


# =============================================================================
# SECTION 16.2 - LISTINGS (25 listings)
# =============================================================================

LISTINGS = {
    "16.2.1.1": {
        "title": "Assignment to Analysis Populations",
        "columns": ["Subject ID", "Site", "Country", "Treatment Randomized", "Treatment Received", "ITT", "Safety", "FAS", "PP", "Efficacy Evaluable", "Reason for Exclusion"]
    },

    "16.2.1.2": {
        "title": "Study Completion and Discontinuation",
        "columns": ["Subject ID", "Site", "Treatment", "First Dose Date", "Last Dose Date", "Treatment Duration (days)", "Treatment Status", "Discontinuation Reason", "Discontinuation Date", "Study Completion Status", "Study End Date"]
    },

    "16.2.1.3": {
        "title": "Screen Failures",
        "columns": ["Subject ID", "Site", "Screen Date", "Screen Failure Reason", "Specific Eligibility Criterion Failed"]
    },

    "16.2.2.1": {
        "title": "Protocol Deviations",
        "columns": ["Subject ID", "Site", "Treatment", "Deviation Category", "Deviation Description", "Deviation Date", "Major/Minor", "Impact on Analysis Set"]
    },

    "16.2.3.1": {
        "title": "Demographics",
        "columns": ["Subject ID", "Site", "Treatment", "Age", "Sex", "Race", "Ethnicity", "Height (cm)", "Weight (kg)", "BMI", "BSA"]
    },

    "16.2.3.2": {
        "title": "Baseline Disease Characteristics",
        "columns": ["Subject ID", "Treatment", "Diagnosis Date", "Disease Stage", "Histology", "Number of Met Sites", "Sites of Metastases", "Baseline Tumor Sum (mm)", "Number of Target Lesions", "Measurable Disease"]
    },

    "16.2.3.3": {
        "title": "Medical History",
        "columns": ["Subject ID", "Treatment", "System Organ Class", "Preferred Term", "Start Date", "Ongoing at Baseline (Y/N)"]
    },

    "16.2.3.4": {
        "title": "Prior Medications",
        "columns": ["Subject ID", "Treatment", "Medication Name", "ATC Code", "Indication", "Route", "Start Date", "End Date", "Ongoing"]
    },

    "16.2.4.1": {
        "title": "Tumor Assessment Data - All Visits",
        "columns": ["Subject ID", "Treatment", "Assessment Date", "Visit", "Target Lesion Sum (mm)", "% Change from Baseline", "% Change from Nadir", "Non-Target Status", "New Lesions (Y/N)", "Overall Response per Visit", "Assessment Source (IRC/INV)"]
    },

    "16.2.4.2": {
        "title": "Best Overall Response",
        "columns": ["Subject ID", "Treatment", "Baseline Sum (mm)", "Nadir Sum (mm)", "Best % Change", "Best Overall Response", "Response Date", "Confirmation Date", "ORR (Y/N)", "DCR (Y/N)"]
    },

    "16.2.4.3": {
        "title": "PFS Event/Censoring Data",
        "columns": ["Subject ID", "Treatment", "Randomization Date", "Event/Censor Date", "Event Type", "Censoring Reason", "PFS (months)", "Event/Censored", "Last Adequate Assessment Date"]
    },

    "16.2.4.4": {
        "title": "OS Event/Censoring Data",
        "columns": ["Subject ID", "Treatment", "Randomization Date", "Death Date", "Last Known Alive Date", "OS (months)", "Event/Censored", "Survival Status"]
    },

    "16.2.4.5": {
        "title": "Duration of Response Data",
        "columns": ["Subject ID", "Treatment", "First Response Date", "Response Type (CR/PR)", "Progression/Death Date", "DOR (months)", "Event/Censored"]
    },

    "16.2.5.1": {
        "title": "Adverse Events - All",
        "columns": ["Subject ID", "Treatment", "AE Verbatim", "Preferred Term", "System Organ Class", "Start Date", "End Date", "Duration", "Grade", "Serious (Y/N)", "Related (Y/N)", "Outcome", "Action Taken"]
    },

    "16.2.5.2": {
        "title": "Serious Adverse Events",
        "columns": ["Subject ID", "Treatment", "SAE Term", "PT", "SOC", "Start Date", "End Date", "Grade", "Seriousness Criteria", "Causality", "Outcome", "Hospitalization Dates"]
    },

    "16.2.5.3": {
        "title": "Deaths",
        "columns": ["Subject ID", "Treatment", "Death Date", "Days from Last Dose", "Primary Cause of Death", "Relationship to Study Drug", "Autopsy Performed (Y/N)"]
    },

    "16.2.5.4": {
        "title": "Adverse Events Leading to Discontinuation",
        "columns": ["Subject ID", "Treatment", "AE Term", "PT", "Start Date", "Grade", "Related", "Discontinuation Date"]
    },

    "16.2.5.5": {
        "title": "Adverse Events Leading to Dose Modification",
        "columns": ["Subject ID", "Treatment", "AE Term", "PT", "Start Date", "Grade", "Modification Type", "Modification Date", "Dose Before", "Dose After"]
    },

    "16.2.6.1": {
        "title": "Laboratory Results - Hematology",
        "columns": ["Subject ID", "Treatment", "Parameter", "Visit", "Collection Date", "Result", "Unit", "Reference Range", "CTCAE Grade", "Baseline Value", "Change from Baseline"]
    },

    "16.2.6.2": {
        "title": "Laboratory Results - Chemistry",
        "columns": "Same as 16.2.6.1"
    },

    "16.2.6.3": {
        "title": "Potentially Clinically Significant Laboratory Values",
        "columns": ["Subject ID", "Treatment", "Parameter", "Visit", "Date", "Result", "PCS Criterion Met", "Clinical Significance Assessment"]
    },

    "16.2.7.1": {
        "title": "Vital Signs",
        "columns": ["Subject ID", "Treatment", "Parameter", "Visit", "Date", "Result", "Unit", "Baseline Value", "Change from Baseline", "PCS (Y/N)"]
    },

    "16.2.7.2": {
        "title": "ECG Results",
        "columns": ["Subject ID", "Treatment", "Visit", "Date", "HR", "PR", "QRS", "QT", "QTcF", "Interpretation", "Clinically Significant (Y/N)"]
    },

    "16.2.8.1": {
        "title": "Study Drug Exposure",
        "columns": ["Subject ID", "Treatment", "Cycle", "Dose Date", "Planned Dose", "Actual Dose", "Route", "Dose Modification", "Modification Reason"]
    },

    "16.2.8.2": {
        "title": "Concomitant Medications",
        "columns": ["Subject ID", "Treatment", "Medication Name", "ATC Code", "Indication", "Route", "Dose", "Start Date", "End Date", "Ongoing"]
    },

    "16.2.9.1": {
        "title": "Subsequent Anti-Cancer Therapy",
        "columns": ["Subject ID", "Treatment", "Subsequent Therapy Type", "Therapy Name", "Start Date", "End Date", "Ongoing", "Best Response"]
    }
}


# =============================================================================
# SINGLE-ARM STUDY TEMPLATES (No Randomization, Single Treatment Column)
# =============================================================================

SINGLE_ARM_DISPOSITION_TABLES = {
    "14.1.1_SA": {
        "title": "Subject Disposition (Single-Arm)",
        "population": "All Enrolled",
        "columns": ["Category", "N", "n (%)", "Notes"],
        "rows": [
            "Enrolled",
            "  Received Study Treatment",
            "  Did Not Receive Treatment",
            "    Manufacturing Failure",
            "    Adverse Event Before Treatment",
            "    Disease Progression Before Treatment",
            "    Subject Withdrawal",
            "    Other",
            "Treated (Safety Population)",
            "Completed Treatment Phase",
            "Discontinued Treatment",
            "  Adverse Event",
            "  Disease Progression",
            "  Physician Decision",
            "  Subject Withdrawal",
            "  Death",
            "  Lost to Follow-up",
            "  Other"
        ],
        "notes": "Single-arm study - no randomization or comparator arm",
        "statistics": ["n (%)"]
    },
    "14.1.2_SA": {
        "title": "Demographics (Single-Arm)",
        "population": "Safety Analysis Set",
        "columns": ["Parameter", "Statistic", "Treated Subjects (N=XXX)"],
        "rows": [
            "Age (years)|n|xxx",
            "|Mean (SD)|xxx (xxx)",
            "|Median|xxx",
            "|Min, Max|xxx, xxx",
            "Age Group, n (%)|<65 years|xxx (xx.x)",
            "|≥65 years|xxx (xx.x)",
            "Sex, n (%)|Male|xxx (xx.x)",
            "|Female|xxx (xx.x)",
            "Race, n (%)|White|xxx (xx.x)",
            "|Black|xxx (xx.x)",
            "|Asian|xxx (xx.x)",
            "|Other|xxx (xx.x)",
            "ECOG PS, n (%)|0|xxx (xx.x)",
            "|1|xxx (xx.x)"
        ],
        "statistics": ["n (%)", "Mean (SD)", "Median", "Min, Max"]
    },
    "14.2.1_SA": {
        "title": "Best Overall Response (Single-Arm)",
        "population": "Inferential Analysis Set",
        "columns": ["Response Category", "n", "% (95% CI)"],
        "rows": [
            "Objective Response Rate (CR+PR)|xxx|xx.x (xx.x, xx.x)",
            "  Complete Response (CR)|xxx|xx.x (xx.x, xx.x)",
            "  Partial Response (PR)|xxx|xx.x (xx.x, xx.x)",
            "Stable Disease (SD)|xxx|xx.x",
            "Progressive Disease (PD)|xxx|xx.x",
            "Not Evaluable (NE)|xxx|xx.x"
        ],
        "notes": "95% CI calculated using Clopper-Pearson exact method",
        "statistics": ["n", "% with 95% CI"]
    }
}

# =============================================================================
# LYMPHOMA-SPECIFIC TEMPLATES (Ann Arbor Staging, Lugano Criteria)
# =============================================================================

LYMPHOMA_BASELINE_TABLES = {
    "14.1.3_LYM": {
        "title": "Baseline Disease Characteristics - Lymphoma",
        "population": "Safety Analysis Set",
        "columns": ["Parameter", "Statistic", "Treated Subjects (N=XXX)"],
        "rows": [
            "Ann Arbor Stage, n (%)|Stage I|xxx (xx.x)",
            "|Stage II|xxx (xx.x)",
            "|Stage III|xxx (xx.x)",
            "|Stage IV|xxx (xx.x)",
            "B Symptoms Present, n (%)|Yes|xxx (xx.x)",
            "|No|xxx (xx.x)",
            "Bulky Disease (≥7 cm), n (%)|Yes|xxx (xx.x)",
            "|No|xxx (xx.x)",
            "Extranodal Sites, n (%)|0|xxx (xx.x)",
            "|1|xxx (xx.x)",
            "|≥2|xxx (xx.x)",
            "Bone Marrow Involvement, n (%)|Yes|xxx (xx.x)",
            "|No|xxx (xx.x)",
            "LDH > ULN, n (%)|Yes|xxx (xx.x)",
            "|No|xxx (xx.x)"
        ],
        "notes": "Ann Arbor staging per Lugano Classification {Cheson 2014}",
        "not_applicable": ["M1a/M1b/M1c staging", "BRAF mutation", "TNM staging"]
    },
    "14.1.4_LYM": {
        "title": "Prognostic Index Scores - Lymphoma",
        "population": "Safety Analysis Set",
        "columns": ["Parameter", "Statistic", "Treated Subjects (N=XXX)"],
        "rows": [
            "FLIPI Score, n (%)|Low Risk (0-1)|xxx (xx.x)",
            "|Intermediate Risk (2)|xxx (xx.x)",
            "|High Risk (≥3)|xxx (xx.x)",
            "FLIPI-2 Score, n (%)|Low Risk (0)|xxx (xx.x)",
            "|Intermediate Risk (1-2)|xxx (xx.x)",
            "|High Risk (≥3)|xxx (xx.x)",
            "IPI Score (if applicable), n (%)|Low (0-1)|xxx (xx.x)",
            "|Low-Intermediate (2)|xxx (xx.x)",
            "|High-Intermediate (3)|xxx (xx.x)",
            "|High (4-5)|xxx (xx.x)"
        ],
        "notes": "FLIPI = Follicular Lymphoma International Prognostic Index"
    }
}

LYMPHOMA_EFFICACY_TABLES = {
    "14.2.1_LYM": {
        "title": "Best Overall Response per Lugano Classification",
        "population": "Inferential Analysis Set",
        "columns": ["Response Category", "n", "% (95% CI)"],
        "rows": [
            "Objective Response Rate (CR+PR)|xxx|xx.x (xx.x, xx.x)",
            "  Complete Response (CR)|xxx|xx.x (xx.x, xx.x)",
            "    Complete Metabolic Response|xxx|xx.x",
            "  Partial Response (PR)|xxx|xx.x (xx.x, xx.x)",
            "    Partial Metabolic Response|xxx|xx.x",
            "Stable Disease (SD)|xxx|xx.x",
            "  No Metabolic Response|xxx|xx.x",
            "Progressive Disease (PD)|xxx|xx.x",
            "  Progressive Metabolic Disease|xxx|xx.x",
            "Not Evaluable (NE)|xxx|xx.x"
        ],
        "response_criteria": "Lugano Classification {Cheson 2014}",
        "notes": "95% CI using Clopper-Pearson exact method. Response based on PET-CT.",
        "not_applicable": ["RECIST 1.1", "Target lesion sum", "CR/PR/SD/PD per RECIST"]
    },
    "14.2.2_LYM": {
        "title": "Response by Deauville Score (PET Assessment)",
        "population": "Inferential Analysis Set",
        "columns": ["Deauville Score", "n", "%"],
        "rows": [
            "Score 1 (No uptake)|xxx|xx.x",
            "Score 2 (Uptake ≤ mediastinum)|xxx|xx.x",
            "Score 3 (Uptake > mediastinum, ≤ liver)|xxx|xx.x",
            "Score 4 (Uptake moderately > liver)|xxx|xx.x",
            "Score 5 (Uptake markedly > liver and/or new lesions)|xxx|xx.x",
            "Complete Metabolic Response (Score 1-3)|xxx|xx.x (xx.x, xx.x)"
        ],
        "notes": "Deauville 5-point scale per Lugano Classification"
    }
}

# =============================================================================
# CAR-T SPECIFIC SAFETY TABLES
# =============================================================================

CAR_T_SAFETY_TABLES = {
    "14.3.1_CART": {
        "title": "Summary of Cytokine Release Syndrome (CRS)",
        "population": "Safety Analysis Set",
        "columns": ["CRS Parameter", "n", "%"],
        "rows": [
            "Any CRS|xxx|xx.x",
            "CRS by Maximum Grade:",
            "  Grade 1|xxx|xx.x",
            "  Grade 2|xxx|xx.x",
            "  Grade 3|xxx|xx.x",
            "  Grade 4|xxx|xx.x",
            "Grade ≥3 CRS|xxx|xx.x",
            "Time to CRS Onset (days):",
            "  Median (range)|x (x-x)|",
            "CRS Duration (days):",
            "  Median (range)|x (x-x)|",
            "CRS Management:",
            "  Tocilizumab|xxx|xx.x",
            "  Corticosteroids|xxx|xx.x",
            "  Vasopressors|xxx|xx.x",
            "  ICU Admission|xxx|xx.x"
        ],
        "grading": "ASTCT 2019 Consensus Grading {Lee 2019}",
        "notes": "CRS collected via specific CRF"
    },
    "14.3.2_CART": {
        "title": "Summary of ICANS (Neurotoxicity)",
        "population": "Safety Analysis Set",
        "columns": ["ICANS Parameter", "n", "%"],
        "rows": [
            "Any ICANS|xxx|xx.x",
            "ICANS by Maximum Grade:",
            "  Grade 1 (ICE 7-9)|xxx|xx.x",
            "  Grade 2 (ICE 3-6)|xxx|xx.x",
            "  Grade 3 (ICE 0-2)|xxx|xx.x",
            "  Grade 4 (ICE 0 + cerebral edema)|xxx|xx.x",
            "Grade ≥3 ICANS|xxx|xx.x",
            "Time to ICANS Onset (days):",
            "  Median (range)|x (x-x)|",
            "ICANS Duration (days):",
            "  Median (range)|x (x-x)|",
            "ICANS Management:",
            "  Corticosteroids|xxx|xx.x",
            "  Anti-seizure medication|xxx|xx.x",
            "  ICU Admission|xxx|xx.x"
        ],
        "grading": "ICE Score (ASTCT 2019)",
        "notes": "ICANS = Immune Effector Cell-Associated Neurotoxicity Syndrome"
    },
    "14.3.3_CART": {
        "title": "CAR-T Cell Kinetics Summary",
        "population": "Safety Analysis Set",
        "columns": ["Parameter", "n", "Mean (SD)", "Median", "Min, Max"],
        "rows": [
            "Cmax (cells/μL)|xxx|xxx (xxx)|xxx|xxx, xxx",
            "Tmax (days)|xxx|xxx (xxx)|xxx|xxx, xxx",
            "AUC Day 0-28 (cells*day/μL)|xxx|xxx (xxx)|xxx|xxx, xxx",
            "Time to Undetectable (months)|xxx|xxx (xxx)|xxx|xxx, xxx"
        ],
        "timepoints": ["Day 7", "Week 2", "Week 4", "Month 3", "Month 6", "Month 12", "Month 24"],
        "notes": "CAR-T cells measured by qPCR"
    },
    "14.3.4_CART": {
        "title": "Prolonged Cytopenias",
        "population": "Safety Analysis Set",
        "columns": ["Cytopenia", "Day 30, n (%)", "Day 60, n (%)", "Day 90, n (%)"],
        "rows": [
            "Neutropenia (ANC <1000/μL)|xxx (xx.x)|xxx (xx.x)|xxx (xx.x)",
            "Thrombocytopenia (<50,000/μL)|xxx (xx.x)|xxx (xx.x)|xxx (xx.x)",
            "Anemia (Hgb <8 g/dL)|xxx (xx.x)|xxx (xx.x)|xxx (xx.x)"
        ],
        "notes": "Cytopenias persisting beyond Day 28 after CAR-T infusion"
    },
    "14.3.5_CART": {
        "title": "Infections Summary",
        "population": "Safety Analysis Set",
        "columns": ["Infection Type", "Any Grade, n (%)", "Grade ≥3, n (%)"],
        "rows": [
            "Any Infection|xxx (xx.x)|xxx (xx.x)",
            "Bacterial|xxx (xx.x)|xxx (xx.x)",
            "Viral|xxx (xx.x)|xxx (xx.x)",
            "Fungal|xxx (xx.x)|xxx (xx.x)",
            "Opportunistic|xxx (xx.x)|xxx (xx.x)"
        ],
        "notes": "Infections identified using MedDRA HLGTs"
    },
    "14.3.6_CART": {
        "title": "Hypogammaglobulinemia and B-Cell Aplasia",
        "population": "Safety Analysis Set",
        "columns": ["Parameter", "n", "%"],
        "rows": [
            "B-Cell Aplasia (CD19+ <1%)|xxx|xx.x",
            "B-Cell Aplasia Duration (months):",
            "  Median (range)|x (x-x)|",
            "Hypogammaglobulinemia (IgG <400 mg/dL)|xxx|xx.x",
            "  Requiring IVIG replacement|xxx|xx.x"
        ],
        "notes": "B-cell aplasia expected with CD19-targeted CAR-T"
    }
}

# =============================================================================
# RETREATMENT TABLES (CAR-T)
# =============================================================================

CAR_T_RETREATMENT_TABLES = {
    "14.2.10_CART_RT": {
        "title": "Response to Retreatment",
        "population": "Safety Re-treatment Analysis Set",
        "columns": ["Response Category", "n", "% (95% CI)"],
        "rows": [
            "Subjects Receiving Retreatment|xxx|",
            "ORR to Retreatment (CR+PR)|xxx|xx.x (xx.x, xx.x)",
            "  Complete Response (CR)|xxx|xx.x",
            "  Partial Response (PR)|xxx|xx.x",
            "Stable Disease (SD)|xxx|xx.x",
            "Progressive Disease (PD)|xxx|xx.x",
            "Not Evaluable (NE)|xxx|xx.x"
        ],
        "notes": "Response in subjects who received retreatment after initial progression"
    },
    "14.2.11_CART_RT": {
        "title": "Duration of Response to Retreatment (DORR)",
        "population": "Safety Re-treatment Analysis Set (Responders)",
        "columns": ["DORR Parameter", "Statistic", "Value"],
        "rows": [
            "Responders to Retreatment|n|xxx",
            "DORR (months)|Median (95% CI)|xxx (xxx, xxx)",
            "|Range|xxx - xxx",
            "Events|n (%)|xxx (xx.x)",
            "Censored|n (%)|xxx (xx.x)"
        ],
        "notes": "DORR = Duration of Response to Retreatment. Kaplan-Meier method."
    }
}


# =============================================================================
# EXPORT FUNCTION
# =============================================================================

def export_tfl_inventory(output_path: Path) -> Dict:
    """Export complete TFL inventory as JSON."""
    inventory = {
        "metadata": {
            "version": "2.0",
            "description": "Complete TFL Inventory for Phase 2/3 Oncology SAPs",
            "total_tables": len(DISPOSITION_TABLES) + len(EFFICACY_TABLES) + len(SAFETY_TABLES),
            "total_figures": len(FIGURES),
            "total_listings": len(LISTINGS),
            "grand_total": len(DISPOSITION_TABLES) + len(EFFICACY_TABLES) + len(SAFETY_TABLES) + len(FIGURES) + len(LISTINGS)
        },
        "section_14_1_disposition": DISPOSITION_TABLES,
        "section_14_2_efficacy": EFFICACY_TABLES,
        "section_14_3_safety": SAFETY_TABLES,
        "section_14_4_figures": FIGURES,
        "section_16_2_listings": LISTINGS
    }

    with open(output_path, 'w') as f:
        json.dump(inventory, f, indent=2, default=str)

    print(f"TFL inventory exported to {output_path}")
    return inventory


def get_table_shell(table_id: str) -> Dict:
    """Get table shell by ID."""
    all_tables = {**DISPOSITION_TABLES, **EFFICACY_TABLES, **SAFETY_TABLES}
    return all_tables.get(table_id, {})


def get_figure_spec(figure_id: str) -> Dict:
    """Get figure specification by ID."""
    return FIGURES.get(figure_id, {})


def get_listing_spec(listing_id: str) -> Dict:
    """Get listing specification by ID."""
    return LISTINGS.get(listing_id, {})


def list_all_tfls() -> Dict[str, List[str]]:
    """List all TFL IDs and titles by section."""
    return {
        "disposition_tables": [f"{tid}: {spec.get('title', '')}" for tid, spec in DISPOSITION_TABLES.items()],
        "efficacy_tables": [f"{tid}: {spec.get('title', '')}" for tid, spec in EFFICACY_TABLES.items()],
        "safety_tables": [f"{tid}: {spec.get('title', '')}" for tid, spec in SAFETY_TABLES.items()],
        "figures": [f"{fid}: {spec.get('title', '')}" for fid, spec in FIGURES.items()],
        "listings": [f"{lid}: {spec.get('title', '')}" for lid, spec in LISTINGS.items()]
    }


if __name__ == "__main__":
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    inventory = export_tfl_inventory(output_dir / "complete_tfl_inventory.json")

    print("\n" + "=" * 80)
    print("COMPLETE TFL INVENTORY v2.0")
    print("=" * 80)

    print(f"\nSection 14.1 - Disposition/Demographics/Baseline: {len(DISPOSITION_TABLES)} tables")
    print(f"Section 14.2 - Efficacy: {len(EFFICACY_TABLES)} tables")
    print(f"Section 14.3 - Safety: {len(SAFETY_TABLES)} tables")
    print(f"Section 14.4 - Figures: {len(FIGURES)} figures")
    print(f"Section 16.2 - Listings: {len(LISTINGS)} listings")

    total = len(DISPOSITION_TABLES) + len(EFFICACY_TABLES) + len(SAFETY_TABLES) + len(FIGURES) + len(LISTINGS)
    print(f"\n{'=' * 80}")
    print(f"GRAND TOTAL: {total} TFLs")
    print("=" * 80)
