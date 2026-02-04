# TLF Shell Generation Rules -- Biostatistician Review

**Document Version:** 1.0
**Generated:** January 2026
**Purpose:** Authoritative reference for all rules governing the automated generation of Tables, Listings, and Figures (TLF) shells from clinical trial protocols.

---

## How It Works

The system reads a clinical trial protocol PDF and extracts structured facts (study design, endpoints, assessments, populations, etc.) into a standardized schema. A library of YAML-based generation rules then evaluates those facts to determine which TLFs are required -- each rule has a condition (e.g., "when the protocol collects ECG assessments") that decides whether a given table, figure, or listing is included. Finally, analysis templates define the exact row structure, column layout, footnotes, and programming notes for every table type, producing complete shells ready for SAS/R programming.

---

## Section 0: LLM Extraction Instructions (What the AI Is Told)

This section documents, verbatim, every instruction the AI receives when it reads a clinical trial protocol. The goal is full transparency: a biostatistician reviewing the generated TLF shells can see exactly what the system was told to look for, exactly how the prompt is structured, and exactly what JSON output schema the AI must conform to.

### 0.1 The Prompt Structure

The system sends a single prompt to Claude (claude-sonnet-4) containing four parts in sequence:

1. **A role instruction** -- "You are a biostatistician reading a clinical trial protocol..." -- that establishes context and defines the task.
2. **Step 1: Detailed reasoning instructions** from 11 domain-specific instruction files. These tell the AI where to look in the protocol, what to think about, and what to extract for each clinical domain.
3. **Step 2: A JSON schema** defining the exact structure and field descriptions for the output.
4. **The protocol text** -- up to 80,000 characters of the uploaded protocol PDF (truncated if longer).

The AI is instructed to reason through each domain first, then output a single JSON object conforming to the schema. No markdown, no explanation -- only valid JSON.

### 0.2 The Prompt Wrapper

The following is the exact text that wraps around the extraction instructions. The `{extraction_instructions}` placeholder is replaced by the concatenation of all 11 instruction files (shown in Section 0.3). The `{schema}` placeholder is replaced by the JSON schema (shown in Section 0.4). The `{protocol_excerpt}` placeholder is replaced by the protocol text.

```
You are a biostatistician reading a clinical trial protocol. Your task is to extract all study-specific facts needed to generate TLF (Tables, Listings, and Figures) shells.

STEP 1: REASON THROUGH THE PROTOCOL

Read the protocol carefully, working through each of the following extraction sections. For each section, look where it tells you to look and think about what it asks you to think about. Extract what the protocol actually says — do not assume, do not default, do not guess.

{extraction_instructions}

STEP 2: STRUCTURE YOUR FINDINGS

Based on your reasoning above, output your findings as a single JSON object. Use the protocol's exact names for populations, arms, endpoints, and assessments. If the protocol does not mention something, use null for strings, false for booleans, or empty arrays [] for lists.

CRITICAL RULES:
- Use the protocol's EXACT population names (e.g. if the protocol says "Full Analysis Set" or "FAS", use that — do NOT default to "ITT")
- Include ALL endpoints (primary, secondary, exploratory)
- Include ALL adverse events of special interest
- Include ALL lab panels individually (do not combine into one generic "labs" entry)
- Include ALL data domains that need listings
- Include ALL figures implied by the study design and endpoints
- For boolean fields in assessments_collected, use true ONLY if the protocol explicitly mentions collecting that assessment

Return ONLY valid JSON (no markdown fences, no explanation) with this schema:

{schema}

PROTOCOL TEXT:
{protocol_excerpt}
```

### 0.3 The Full Extraction Instructions

The 11 instruction files below are concatenated in order, separated by `---` dividers. Each file tells the AI how to reason about one clinical domain. The content below is reproduced in full -- every word is exactly what the AI receives.

---

#### Domain 1: Study Context

# Extraction: Study Context

Every TLF shell needs to know the basic shape of the study. Extract this first — everything else builds on it.

## Where to Look

Start with the title page and protocol synopsis. Then read the study design section for details. The randomization section describes arms and stratification. The statistical methods section defines analysis populations.

## What to Think About

**What disease is being studied?** Capture the specific indication as the protocol states it. The therapeutic area determines which assessments, endpoints, and safety monitoring are relevant for downstream sections.

**What are the treatment arms?** Find the arm names exactly as the protocol states them. These become column headers in every table. Note the drug, dose, route, and frequency for each arm.

**Does the study have more than one treatment period?** If the protocol defines distinct phases with different start/end dates or different treatments, capture each period and its timeframe. This drives whether safety tables need to be repeated per period.

**What are the analysis populations?** Find every population the protocol defines and copy the names exactly. These go into every table title and footnote. Use the protocol's names, not generic defaults.

**What are the stratification factors and their categories?** These appear in efficacy models, subgroup analyses, and demographics tables. Capture each factor and the specific categories the protocol defines for it.

**Is this a multi-regional study?** If the protocol mentions multiple countries or regions, note them. This affects demographics tables and may affect efficacy analysis.

**What is the route of administration?** This determines whether injection site, infusion reaction, or local tolerability assessments are collected, which need their own tables.

**How long is the safety follow-up?** Find the TEAE window definition — how many days after the last dose are adverse events still considered treatment-emergent.

---

#### Domain 2: Disposition (ICH 14.1)

# Extraction: Disposition (ICH 14.1)

The disposition table shows the flow of subjects through the study. Its rows come directly from what the protocol defines.

## Where to Look

Look for a "Discontinuation" or "Withdrawal from Study" section. Sometimes it's under "Study Procedures" or "Completion and Early Termination." Screen failure reasons are implied by the screening process and inclusion/exclusion criteria. Protocol deviation categories may be in a "Data Quality" or "Protocol Compliance" section.

## What to Think About

**What reasons does the protocol list for discontinuing treatment?** Read the discontinuation section and capture every reason the protocol enumerates. Protocols always include standard reasons, but many also add reasons specific to the disease or study design. If you miss a protocol-defined discontinuation reason, the disposition table will have the wrong rows. Extract them all exactly as stated.

**Does the protocol distinguish treatment discontinuation from study discontinuation?** Some protocols allow subjects to stop treatment but remain in the study for follow-up. If this distinction exists, the disposition table needs separate sections for treatment status and study status.

**What happens after treatment ends?** Look for follow-up phases defined after the treatment period. The protocol may define a safety follow-up visit, a survival follow-up period, or a long-term extension. Each distinct follow-up phase affects the disposition table structure.

**Does the protocol pre-define protocol deviation categories?** Some protocols enumerate what counts as a major deviation. If categories are listed, capture them. If not, the generation layer will use a standard set.

**How does the protocol define screen failures?** Look at the screening process. Some protocols track specific failure reasons, others just count failures. Capture whatever the protocol defines.

---

#### Domain 3: Demographics & Baseline Characteristics (ICH 14.1)

# Extraction: Demographics & Baseline Characteristics (ICH 14.1)

Standard demographics (age, sex, race, weight, height, BMI) are always included. The challenge is identifying the disease-specific baseline variables that make this table specific to this study.

## Where to Look

The inclusion/exclusion criteria are the richest source — every criterion that describes the patient's disease state at entry is a candidate baseline variable. Also check the stratification factors, the Schedule of Assessments for baseline-only assessments, and any disease background section that describes the patient population.

## What to Think About

**What characterizes this patient population beyond standard demographics?** Read the inclusion criteria line by line. Each criterion that specifies a disease characteristic is telling you about a baseline variable that needs to appear in the demographics table. If a criterion requires a specific lab value, disease score, performance status, staging, histology, prior treatment history, or any disease measurement, that variable belongs in the baseline table.

**What are the stratification factors?** Stratification factors always appear in the demographics table because they define how randomization was balanced. Whatever variables the protocol uses for stratification need to be captured as baseline characteristics with their specific categories.

**Are there baseline-only assessments in the Schedule of Assessments?** Walk the SOA and look for assessments performed at screening or baseline that measure the patient's disease state. These may include performance status scales, disease severity scores, imaging findings, genetic or biomarker status, or disease-specific instruments. Each produces a row in the baseline table or a separate table.

**Does the study enroll across multiple countries or regions?** If so, the demographics section needs a patient distribution table. Look for how the protocol defines geographic groupings.

**What regulatory requirements affect the demographics table?** If the protocol mentions specific regulatory targets, note them. Different regulatory authorities have different requirements for demographic data collection and presentation.

**Does the protocol define age subgroups?** Look for any mention of age-based subgroups in the statistical methods or subgroup analysis section. Capture whatever cutpoints the protocol defines — do not assume standard cutpoints.

---

#### Domain 4: Efficacy Endpoints (ICH 14.2)

# Extraction: Efficacy Endpoints (ICH 14.2)

Each efficacy endpoint produces at least one analysis table. The number and type of tables depends on the endpoint type, the populations it's analyzed in, and any sensitivity or subgroup analyses the protocol defines.

## Where to Look

The objectives and endpoints section defines every endpoint. The statistical methods section describes how each endpoint is analyzed, including the analysis method, populations, sensitivity analyses, and multiplicity adjustments. The estimands section (if present) defines intercurrent event handling. The sample size section often reveals the primary analysis method.

## What to Think About

**What are all the endpoints?** Read the objectives section and extract every endpoint the protocol defines — primary, key secondary, secondary, and exploratory. For each endpoint, capture:
- The exact name as the protocol states it
- Whether it is primary, key secondary, secondary, or exploratory
- The type of measurement: is it a time-to-event outcome, a binary response, a continuous measure, a count/rate, or an ordinal score? The endpoint type determines which table template the generation layer uses.
- Which population it is analyzed in. The protocol specifies this — it may differ between primary and secondary endpoints.

**Does any endpoint have multiple analysis populations?** The primary endpoint is often analyzed in both the primary population and a sensitivity population. If the protocol says "the primary endpoint will also be analyzed in the per-protocol population," that's a second table for the same endpoint.

**Does any endpoint have multiple review types?** Some studies have both central review and local investigator review for the same endpoint. Each review type produces a separate table.

**What sensitivity analyses are defined?** Look for language like "sensitivity analysis," "supportive analysis," or "robustness analysis." Each distinct sensitivity analysis of the primary endpoint produces its own table. Sensitivity analyses may use a different population, a different statistical method, or a different handling of missing data.

**What subgroup analyses are pre-specified?** Look for a subgroup analysis section. Capture which endpoints have subgroup analyses and what subgroup variables are defined. Each endpoint with subgroups needs a subgroup analysis table and potentially a forest plot figure.

**What statistical methods does the protocol specify?** For each endpoint, does the protocol name a specific analysis method? If stated, capture it. If not, the generation layer will apply a default based on endpoint type.

**Are there multiplicity adjustments?** Does the protocol describe a testing hierarchy, gatekeeping procedure, or alpha-spending function? If so, note which endpoints are in the hierarchy and the testing order. This affects footnotes and whether p-values are labeled as "nominal."

**Are there responder analyses?** Does the protocol define response categories or responder thresholds for any endpoint? If so, these produce separate responder analysis tables.

**Are there any QoL or patient-reported outcome endpoints?** If the protocol specifies QoL instruments, capture each instrument name. Each instrument produces its own set of tables (summary by visit, change from baseline, and possibly a responder analysis).

---

#### Domain 5: Adverse Events (ICH 14.3)

# Extraction: Adverse Events (ICH 14.3)

The AE section always produces a core set of tables (overview, by SOC/PT, serious, leading to discontinuation, leading to death). But the protocol may define additional AE categories, special groupings, or study-specific safety concerns that need their own tables.

## Where to Look

The safety assessment section describes AE collection, coding, and grading. The AE reporting section may define special categories. Look also for "Adverse Events of Special Interest," "Events of Clinical Interest," or "Targeted Safety Events" — these are sometimes in a separate subsection or appendix. The dose modification section describes which AEs trigger dose changes.

## What to Think About

**How does the protocol grade AE severity?** Does it use a standard grading system, or a study-specific grading scale? The grading system determines row labels in the overview table and whether grade-specific tables are needed.

**How does the protocol assess causality/relatedness?** Is it a binary assessment (related/not related) or a multi-category scale? This determines whether "treatment-related" tables are included and how relatedness is defined in footnotes.

**Does the protocol define a frequency threshold for the "common TEAEs" table?** Some protocols specify that only TEAEs occurring above a certain percentage threshold should be shown in a summary table. Look for this in the statistical methods section. If stated, capture the threshold. If not stated, the generation layer will use a standard threshold.

**Does the protocol define Adverse Events of Special Interest (AESIs)?** This is critical. AESIs are protocol-defined categories of AEs that require separate analysis. Each AESI produces its own table. Look for:
- A dedicated AESI section that names specific categories
- References to Standardised MedDRA Queries (SMQs) or custom preferred term lists
- Any AE category the protocol singles out for special monitoring or reporting

Capture every AESI the protocol defines, by name, exactly as stated.

**Does the protocol define grouped AE terms?** Beyond AESIs, protocols sometimes define custom groupings of AE preferred terms that should be analyzed together. These are specific to the drug's safety profile. Capture each group name.

**Does the route of administration create special AE categories?** Injectable drugs may have injection site reaction assessments. IV drugs may have infusion-related reaction monitoring. If the protocol describes a specific assessment for administration-related reactions, this needs its own table.

**Are there dose modification rules triggered by specific AEs?** If the protocol defines rules for dose reduction, interruption, or discontinuation based on specific AE types or grades, this implies a "TEAEs leading to dose modification" table and potentially tables showing which specific AEs triggered modifications.

**Are there protocol-defined stopping rules or safety signals?** If the protocol describes specific safety thresholds that would trigger study-level actions (DSMB review, enrollment hold), note them. These may imply threshold-based summary tables.

**Does the drug class have known safety concerns?** The protocol's safety section often references the drug class's known risks. These known risks typically generate focused analysis tables. The protocol may not call them "AESIs" explicitly, but if it dedicates paragraphs to a specific safety topic, that topic likely needs its own table.

---

#### Domain 6: Laboratory Parameters (ICH 14.3)

# Extraction: Laboratory Parameters (ICH 14.3)

Lab tables are only included when the protocol collects laboratory assessments. The specific tables depend on which panels are collected, whether toxicity grading is applied, and whether there are special monitoring requirements.

## Where to Look

The Schedule of Assessments shows which lab panels are collected and at which visits. The laboratory assessment section (or an appendix) lists the specific parameters within each panel. The inclusion/exclusion criteria may reference lab thresholds that imply which parameters are clinically important. The safety monitoring section may describe enhanced monitoring for specific lab parameters.

## What to Think About

**What lab panels does the protocol collect?** Walk the Schedule of Assessments and find every laboratory assessment row. Each distinct panel (hematology, clinical chemistry, urinalysis, coagulation, thyroid, lipid, etc.) produces its own summary table and listing. Do not assume standard panels — capture exactly what the protocol specifies.

**Are there specific parameters the protocol calls out for special monitoring?** Some protocols highlight individual lab parameters that are of particular concern for the drug being studied. If the protocol singles out specific parameters for enhanced monitoring, special thresholds, or separate analysis, note them. These may need their own summary tables or threshold-based tables.

**Does the protocol apply a toxicity grading system to lab values?** If the protocol references a grading system for lab toxicity, note it. This determines whether grade-based summary tables and grade shift tables are needed.

**Does the protocol define markedly abnormal criteria?** Some protocols define specific thresholds for what constitutes a "markedly abnormal" or "clinically significant" lab value. If defined, capture them. These determine the rows in the markedly abnormal values table.

**Is liver function monitoring specified?** If the protocol describes enhanced liver monitoring, liver function test thresholds, or evaluation criteria for drug-induced liver injury, note this. It implies dedicated liver function tables beyond the standard chemistry summary.

**Is the lab performed by a central lab or local labs?** This affects the source of reference ranges and is noted in table footnotes. Look for mention of central laboratory services.

**What is the assessment schedule?** Which visits include lab assessments? This matters for the "by visit" table structure. The SOA shows the timing.

**Are there any lab-based stopping rules?** If the protocol defines lab value thresholds that trigger dose modification or treatment discontinuation, note them. These imply threshold-based summary tables.

---

#### Domain 7: Vital Signs & ECG (ICH 14.3)

# Extraction: Vital Signs & ECG (ICH 14.3)

Vital signs and ECG tables are only included when these assessments are collected. The specific tables depend on what parameters are measured, whether special thresholds are defined, and whether the drug has known cardiac safety concerns.

## Where to Look

The Schedule of Assessments shows whether vital signs and ECGs are collected and at which visits. The safety assessment section may describe specific measurement procedures. For ECG, look for references to cardiac safety guidance or QT assessment requirements. The inclusion/exclusion criteria may reference vital sign or ECG thresholds.

## What to Think About

### Vital Signs

**What vital sign parameters does the protocol collect?** Check the SOA for which parameters are measured. Do not assume a standard set — capture what the protocol specifies.

**Does the protocol define markedly abnormal vital sign criteria?** Some protocols define specific thresholds for what constitutes a clinically significant vital sign value. If defined, capture them. If not, the generation layer will apply standard criteria.

**Are there special measurement procedures?** Does the protocol require orthostatic vital signs (supine and standing measurements)? If so, this produces additional rows showing orthostatic changes. Does the protocol require specific measurement conditions (resting, post-exercise, timed intervals)?

### ECG

**Does the protocol collect ECGs?** If ECG is not in the SOA, no ECG tables are generated.

**What type of ECG assessment is specified?** Is it single or triplicate? Standard 12-lead? Is there central reading? These affect calculation methods and footnotes.

**What QT correction method does the protocol specify?** The protocol may name a specific correction formula. Capture it as stated.

**Does the protocol define categorical thresholds for QT analysis?** If the protocol or its referenced guidance defines absolute and change-from-baseline thresholds for QT interval, note that categorical analysis tables are needed. Capture the thresholds as stated in the protocol.

**Is this a thorough QT study or standard cardiac monitoring?** The level of ECG analysis differs significantly. A thorough QT study has detailed time-matched ECG-PK analysis. Standard monitoring just has by-visit summaries and categorical analysis.

**Does the drug have known cardiac safety concerns?** If the protocol discusses QT prolongation risk, arrhythmia risk, or references cardiac safety guidance, this implies enhanced ECG analysis beyond standard summaries.

---

#### Domain 8: Exposure & Medications (ICH 14.3)

# Extraction: Exposure & Medications (ICH 14.3)

Exposure and concomitant medication tables are always included. But the specific tables depend on the dosing regimen, whether dose modifications are allowed, whether there is a backbone/background therapy, and whether rescue medications are defined.

## Where to Look

The study treatment section describes the dosing regimen, dose modification rules, and any background therapy. The prohibited/permitted medications section defines medication restrictions. The rescue therapy section (if present) describes what rescue is allowed and when. The SOA may show drug administration and compliance assessments.

## What to Think About

### Study Drug Exposure

**What is the dosing regimen?** Is it fixed-dose, weight-based, titrated, or cycle-based? This determines how exposure is summarized (duration in weeks vs. number of cycles vs. cumulative dose).

**Are dose modifications allowed?** If the protocol defines rules for dose reduction, dose interruption, dose delay, or dose escalation, then dose modification tables are needed. Capture that dose modifications exist and what types are allowed — the generation layer will build the appropriate tables.

**Is there a planned dose for calculating relative dose intensity?** If the protocol specifies a planned dose or planned number of cycles, relative dose intensity can be calculated.

### Backbone / Background Therapy

**Does the protocol require a background therapy that all subjects receive alongside the study drug?** This is different from concomitant medications — it's a required protocol-mandated therapy. If the protocol specifies a required background therapy, capture the drug name and that it exists. If there is no required background therapy, do NOT create backbone therapy tables.

**If there is a backbone, are dose modifications allowed for it?** If the protocol defines dose modification rules specifically for the backbone therapy, note it.

### Concomitant Medications

**Does the protocol distinguish prior from concomitant medications?** If the protocol defines these differently, both may need separate tables.

**Does the protocol define rescue or salvage therapy?** If the protocol specifies specific rescue medications, conditions that trigger rescue use, or escape criteria, note that rescue medication tables are needed.

**Are there prohibited medications?** If the protocol lists specific prohibited medications, this may warrant a "prohibited medication use" table to track protocol deviations.

### Special Considerations

**Is there a run-in or washout period?** If the protocol requires subjects to wash out from prior therapies before randomization, note it — this may affect the prior medication table structure.

**Are there multiple study drugs administered?** Some studies have combination therapy where subjects receive two or more study drugs. Each drug may need its own exposure table.

---

#### Domain 9: Pharmacokinetics & Immunogenicity (ICH 14.4)

# Extraction: Pharmacokinetics & Immunogenicity (ICH 14.4)

PK and immunogenicity tables are only included when the protocol collects these assessments. Biologics almost always have immunogenicity assessment. PK sampling may be sparse (trough levels only) or intensive (full concentration-time profiles).

## Where to Look

Look for a pharmacokinetics section, PK objectives, or PK sampling schedule. This is sometimes in an appendix or a separate PK sub-study section. For immunogenicity, look for an anti-drug antibody (ADA) or immunogenicity assessment section. The bioanalytical methods section may describe assay details.

## What to Think About

### Pharmacokinetics

**Does the protocol collect PK samples?** If there is no PK sampling in the SOA, no PK tables are generated.

**What is the sampling schedule?** Is it sparse sampling (trough levels at a few visits) or intensive sampling (multiple timepoints within a dosing interval)? Intensive sampling produces concentration-time profile figures. Sparse sampling produces by-visit concentration summaries.

**What PK parameters will be derived?** The protocol or PK analysis plan may specify which parameters are of interest. Capture them as stated.

**What analyte(s) are measured?** Is it the parent drug only, or also metabolites? Each analyte may need its own tables.

**Is there a PK population defined?** The protocol may define inclusion criteria for PK-evaluable subjects. Capture the population name.

**Is this a comparative PK study?** For bioequivalence or biosimilar studies, PK comparison tables with confidence intervals and equivalence conclusions are needed.

### Immunogenicity

**Does the protocol assess anti-drug antibodies (ADA)?** If ADA testing is not mentioned, no immunogenicity tables are generated.

**Does the protocol test for neutralizing antibodies (NAb)?** If NAb testing is performed on ADA-positive samples, additional rows are needed in the immunogenicity table.

**How does the protocol define treatment-emergent ADA?** The definition of treatment-emergent vs. treatment-boosted ADA varies across protocols. Capture the definitions as stated.

**Does the protocol analyze the impact of ADA on safety or efficacy?** If the protocol specifies analyzing AEs by ADA status or efficacy by ADA status, additional cross-tabulation tables are needed.

### Pharmacodynamics

**Does the protocol collect PD assessments?** If the protocol defines pharmacodynamic endpoints or biomarker assessments linked to drug mechanism, these may need their own summary tables and figures. PD assessments are sometimes listed separately from efficacy endpoints. Look in the SOA for biomarker or PD sampling rows.

---

#### Domain 10: Figures

# Extraction: Figures

Figures are not extracted independently — they are derived from what you already found in the other extraction sections. This section tells you how to reason about which figures are needed based on the endpoints, assessments, and study design you already identified.

## Where to Look

You already have the information from the efficacy, safety, and PK extraction sections. The figures section just applies logic to determine which visual outputs are needed.

## What to Think About

**Which endpoints are time-to-event?** Every time-to-event endpoint you identified in the efficacy extraction needs a Kaplan-Meier curve figure. The protocol defines these endpoints — you already captured them.

**Which endpoints have pre-specified subgroup analyses?** Every endpoint with subgroup analyses needs a forest plot figure. You already captured subgroup specifications in the efficacy extraction.

**Does the study collect tumor response data?** If the efficacy extraction identified tumor response endpoints with criteria like RECIST, the study may need waterfall plots (best change from baseline in tumor size) and swimmer plots (duration of response). Only include these if the protocol actually describes tumor assessment criteria.

**Are there continuous primary endpoints?** Each primary continuous endpoint may need a mean-change-over-time line plot showing treatment arm trajectories across visits.

**Did you find PK sampling?** If the PK extraction identified intensive PK sampling, concentration-time profile figures are needed (both linear and semi-log scale), plus individual concentration curves.

**Is the study randomized?** Randomized studies need a CONSORT flow diagram showing the flow of subjects from screening through completion.

**Did you find lab assessments?** If the labs extraction identified laboratory panels, trend plots for selected parameters of clinical interest may be needed.

**Did you find QoL instruments?** Each QoL/PRO instrument identified in the efficacy extraction needs a score-over-time figure.

**Are there any other assessments that would benefit from visual presentation?** Think about whether any assessment you identified would be better understood as a figure than a table. This is a judgment call based on what the protocol emphasizes.

---

#### Domain 11: Listings (ICH 16.2)

# Extraction: Listings (ICH 16.2)

Listings present individual patient data for every data domain collected. Like figures, listings are derived from what you already found — every assessment you identified needs a corresponding listing.

## Where to Look

You already have all the information from the other extraction sections. The listings extraction is about confirming completeness: every data domain collected in the study needs a patient-level listing.

## What to Think About

**What data domains are collected in this study?** Walk through everything you identified in the other extraction sections. Each domain that collects patient-level data needs its own listing. The core domains are always present (disposition, demographics, medical history, medications, exposure, adverse events, efficacy). But the study-specific domains you identified are equally important — if the protocol collects it, it needs a listing.

**Which lab panels did you identify?** Each lab panel identified in the labs extraction needs its own listing. Do not combine them into one generic "lab listing" — separate them by panel as the protocol defines them.

**Did you identify PK or immunogenicity assessments?** If so, each needs its own listing (PK concentrations, PK parameters, ADA results).

**Did you identify QoL instruments?** Each instrument needs its own listing showing individual patient responses by visit.

**Did you identify any study-specific assessments?** Any assessment from the SOA that you captured in the other sections — disease-specific scores, imaging results, biomarker data, tolerability assessments, device readings — needs a listing. If you created a table for it, it needs a listing too.

**Are there AESIs?** If you identified AESIs in the adverse events extraction, they need a dedicated AESI listing showing individual event details.

**Are there special listing requirements for the study design?** Biosimilar/equivalence studies may need additional listings (salvage treatment details, inclusion/exclusion criteria verification). Studies with complex dosing may need detailed dose administration listings.

**Does the protocol define any specific listing requirements?** Some protocols or statistical analysis plan templates specify particular listings. If the protocol references required listings, capture them.

---

### 0.4 The JSON Schema

The AI must return a single JSON object conforming to this schema. Each field description tells the AI what to put in that field. The schema below is reproduced exactly as it appears in the prompt:

```json
{
  "study_design": {
    "phase": "Phase of the trial as stated in the protocol",
    "type": "One of: superiority, equivalence, non_inferiority, biosimilar, single_arm",
    "blinding": "Blinding description as stated in the protocol",
    "randomization": "Randomization ratio as stated in the protocol",
    "equivalence_margin": "Equivalence/non-inferiority margin if applicable, null if not",
    "indication": "Disease/condition being studied",
    "route_of_administration": "Route of study drug administration"
  },
  "arms": [
    {"name": "Full arm name as stated in the protocol", "dose": "Dose as stated", "route": "Route as stated"}
  ],
  "populations": [
    {"name": "Population name exactly as the protocol defines it", "definition": "Definition as stated in the protocol", "primary_for": "What this population is primary for (efficacy/safety/pk/etc.) or null"}
  ],
  "endpoints": [
    {
      "name": "Endpoint name exactly as stated in the protocol",
      "type": "One of: binary, time_to_event, continuous, count, ordinal",
      "primary": true,
      "analysis_method": "Statistical method as described in the protocol, or null if not stated",
      "covariates": ["Covariates/stratification factors for this endpoint's model as stated"],
      "populations": ["Population names this endpoint is analyzed in, using the protocol's names"],
      "reviews": ["Review types if applicable, empty list if N/A"],
      "response_criteria": "Response criteria name if applicable, null if N/A",
      "landmark_timepoints": ["Timepoints as stated in the protocol"],
      "censoring_rules": "Censoring description as stated, null if not described",
      "extra_rows": ["Additional row items like response categories"],
      "sensitivity_analyses": ["Sensitivity analyses described for this endpoint"],
      "multiplicity_adjustment": "Multiplicity adjustment method if stated, null if not"
    }
  ],
  "study_periods": ["All study periods in order as the protocol names them"],
  "treatment_periods": ["Only the treatment periods as the protocol names them"],
  "assessments_collected": {
    "labs": true,
    "vitals": true,
    "ecg": true,
    "pk": true,
    "immunogenicity": true,
    "qol": ["QoL/PRO instrument names as stated in the protocol, empty list if none"],
    "imaging": "Imaging description or null",
    "physical_exam": true,
    "pregnancy_test": true,
    "ecog_ps": true,
    "viral_serology": true,
    "gene_screening": true
  },
  "lab_panels": [
    {"name": "Panel name as stated in the protocol", "parameters": ["Parameters in this panel if listed"]}
  ],
  "special_monitoring_params": ["Parameters requiring special monitoring as identified in the protocol"],
  "ecg_assessment": {
    "collected": true,
    "qt_correction_method": "QT correction formula if stated, null if not",
    "centralized_reading": true,
    "categorical_thresholds_defined": true
  },
  "vitals_details": {
    "parameters": ["Vital sign parameters collected"],
    "orthostatic_assessment": true
  },
  "aesis": [
    {"name": "AESI category name as stated", "definition": "Definition as stated in the protocol"}
  ],
  "ae_grouped_terms": [
    {"name": "Grouped term name", "definition": "How the protocol defines this grouping"}
  ],
  "safety_concerns": ["Drug-class or study-specific safety signals mentioned in the protocol"],
  "dose_modifications": {
    "allowed": true,
    "types": ["Types of dose modifications allowed: reduction, interruption, delay, escalation"],
    "triggers": ["Conditions that trigger dose modifications as described"]
  },
  "rescue_medications": [
    {"name": "Rescue/salvage therapy name", "trigger": "Condition that allows rescue use"}
  ],
  "backbone_therapies": [
    {"name": "Backbone therapy name as stated", "dose": "Dose as stated", "dose_modifications_allowed": true}
  ],
  "discontinuation_reasons": ["Protocol-defined reasons for discontinuation"],
  "deviation_categories": ["Protocol-defined deviation categories if any"],
  "pk_sampling": {
    "type": "One of: sparse, intensive, none",
    "analytes": ["Analyte names measured"],
    "parameters_derived": ["PK parameters to be derived as stated"],
    "pk_population": "PK-evaluable population name if defined, null if not"
  },
  "ada_assessment": {
    "performed": true,
    "nab_testing": true,
    "impact_analysis": true
  },
  "stratification_factors": ["Randomization stratification factors as stated"],
  "subgroups": ["Pre-specified subgroup analyses as stated in the protocol"],
  "disease_specific_baseline": [
    "Disease-specific baseline characteristics identified from inclusion criteria, SOA, and disease description"
  ],
  "figure_requirements": [
    {"type": "Figure type (e.g. kaplan_meier, forest_plot, waterfall, consort, concentration_time, score_over_time)", "for_endpoint": "Endpoint name or null", "description": "Brief description"}
  ],
  "listing_domains": [
    "Every data domain that needs a patient-level listing (e.g. disposition, demographics, medical_history, each lab panel, each efficacy assessment, AEs, AESIs, exposure, conmeds, PK, ADA, each QoL instrument, etc.)"
  ],
  "multicenter_design": {
    "is_multicenter": true,
    "countries": ["Country names if listed in the protocol"],
    "regions": ["Region groupings if the protocol defines them"]
  },
  "age_strata": ["Protocol-defined age subgroup cutpoints as stated, e.g. '6-11 years', '12-17 years', '18-64 years'. Empty list if no age subgroups defined."],
  "coding_dictionaries": {
    "ae": "MedDRA version if stated, null if not",
    "medications": "WHO Drug Dictionary version if stated, null if not"
  },
  "therapeutic_area": "Therapeutic area as identified from the protocol"
}
```

---

## Section 1: Extraction Schema

The following facts are extracted from each protocol. These facts drive every downstream decision about which TLFs to generate.

### 1.1 Study Design

| Fact | Description | Example Values |
|------|-------------|----------------|
| Phase | Phase of the trial as stated in the protocol | Phase 1, Phase 2, Phase 3 |
| Type | Study design type | superiority, equivalence, non_inferiority, biosimilar, single_arm |
| Blinding | Blinding description as stated | Double-blind, Open-label |
| Randomization | Randomization ratio | 1:1, 2:1, 1:1:1 |
| Equivalence margin | Equivalence or non-inferiority margin, if applicable | -15%, HR 1.3 |
| Indication | Disease or condition being studied | Non-small cell lung cancer |
| Route of administration | Route of study drug | IV, Subcutaneous, Oral |

### 1.2 Treatment Arms

| Fact | Description | Example Values |
|------|-------------|----------------|
| Arm name | Full arm name as stated in the protocol | Pembrolizumab 200 mg Q3W |
| Dose | Dose as stated | 200 mg, 10 mg/kg |
| Route | Route as stated | IV infusion, SC injection |

### 1.3 Analysis Populations

| Fact | Description | Example Values |
|------|-------------|----------------|
| Population name | Population name exactly as the protocol defines it | Full Analysis Set, Safety Population |
| Definition | Definition as stated | All randomized subjects who received at least one dose |
| Primary for | What this population is primary for | efficacy, safety, pk |

### 1.4 Endpoints

| Fact | Description | Example Values |
|------|-------------|----------------|
| Name | Endpoint name exactly as stated | Progression-Free Survival, Overall Response Rate |
| Type | Endpoint data type | binary, time_to_event, continuous, count, ordinal |
| Primary | Whether this is a primary endpoint | true, false |
| Analysis method | Statistical method as described | Cox proportional hazards, Logistic regression |
| Covariates | Stratification factors / covariates for the model | Region, PD-L1 status |
| Populations | Populations this endpoint is analyzed in | ITT, Per-Protocol |
| Reviews | Review types if applicable (e.g., blinded independent central review) | BICR, Investigator |
| Response criteria | Response criteria name if applicable | RECIST v1.1, IMWG |
| Landmark timepoints | Protocol-specified timepoints | 6 months, 12 months, 24 months |
| Censoring rules | Censoring description as stated | Subjects without event censored at last assessment |
| Extra rows | Additional row items like response categories | CR, PR, SD, PD |
| Sensitivity analyses | Sensitivity analyses described for this endpoint | Unstratified analysis, Per-protocol population |
| Multiplicity adjustment | Multiplicity method if stated | Hochberg, Gatekeeping |

### 1.5 Study Periods and Treatment Periods

| Fact | Description | Example Values |
|------|-------------|----------------|
| Study periods | All study periods in order | Screening, Treatment, Follow-up |
| Treatment periods | Only the treatment periods | Induction, Maintenance |

### 1.6 Assessments Collected

| Fact | Description | Example Values |
|------|-------------|----------------|
| Labs | Whether laboratory assessments are collected | true / false |
| Vitals | Whether vital signs are collected | true / false |
| ECG | Whether ECG is collected | true / false |
| PK | Whether pharmacokinetic sampling is performed | true / false |
| Immunogenicity | Whether immunogenicity (ADA) is assessed | true / false |
| QoL / PRO | Quality of life / patient-reported outcome instruments | EQ-5D-5L, EORTC QLQ-C30 |
| Imaging | Imaging description | CT/MRI per RECIST |
| Physical exam | Whether physical exams are collected | true / false |
| Pregnancy test | Whether pregnancy tests are collected | true / false |
| ECOG PS | Whether ECOG performance status is assessed | true / false |
| Viral serology | Whether viral serology is collected | true / false |
| Gene screening | Whether biomarker/genomic screening is performed | true / false |

### 1.7 Lab Panels

| Fact | Description | Example Values |
|------|-------------|----------------|
| Panel name | Panel name as stated in the protocol | Hematology, Clinical Chemistry, Coagulation |
| Parameters | Parameters in this panel | Hemoglobin, WBC, Platelets |

### 1.8 ECG Assessment Details

| Fact | Description | Example Values |
|------|-------------|----------------|
| Collected | Whether ECG is collected | true / false |
| QT correction method | QT correction formula if stated | Fridericia (QTcF) |
| Centralized reading | Whether centralized ECG reading is used | true / false |
| Categorical thresholds defined | Whether ICH E14 thresholds are explicitly defined | true / false |

### 1.9 Vital Signs Details

| Fact | Description | Example Values |
|------|-------------|----------------|
| Parameters | Vital sign parameters collected | SBP, DBP, Pulse, Temperature |
| Orthostatic assessment | Whether orthostatic measurements are required | true / false |

### 1.10 Safety Monitoring

| Fact | Description | Example Values |
|------|-------------|----------------|
| AESIs | Adverse events of special interest -- name and definition | Infusion-related reactions, Hepatotoxicity |
| Grouped AE terms | Grouped AE term names and definitions | Infections, Cardiac events |
| Safety concerns | Drug-class or study-specific safety signals | Cardiotoxicity, Immune-mediated events |
| Special monitoring parameters | Parameters requiring special monitoring | Troponin, Thyroid function |

### 1.11 Dose Modifications

| Fact | Description | Example Values |
|------|-------------|----------------|
| Allowed | Whether dose modifications are permitted | true / false |
| Types | Types of dose modifications allowed | reduction, interruption, delay, escalation |
| Triggers | Conditions that trigger dose modifications | Grade 3 neutropenia, Hepatotoxicity |

### 1.12 Rescue and Background Medications

| Fact | Description | Example Values |
|------|-------------|----------------|
| Rescue medications | Rescue/salvage therapy name and trigger condition | Leucovorin rescue after methotrexate toxicity |
| Backbone therapies | Background therapy name, dose, and whether dose modifications allowed | Methotrexate 15 mg weekly |

### 1.13 PK Sampling

| Fact | Description | Example Values |
|------|-------------|----------------|
| Type | Sampling type | sparse, intensive, none |
| Analytes | Analyte names measured | Drug X, Metabolite Y |
| Parameters derived | PK parameters to be derived | Cmax, AUC0-inf, Tmax, T1/2 |
| PK population | PK-evaluable population name | PK Evaluable Population |

### 1.14 ADA Assessment

| Fact | Description | Example Values |
|------|-------------|----------------|
| Performed | Whether ADA testing is performed | true / false |
| NAb testing | Whether neutralizing antibody testing is performed | true / false |
| Impact analysis | Whether ADA impact on safety/efficacy is analyzed | true / false |

### 1.15 Study Structure

| Fact | Description | Example Values |
|------|-------------|----------------|
| Stratification factors | Randomization stratification factors | Region, Prior therapy, PD-L1 status |
| Subgroups | Pre-specified subgroup analyses | Age (<65 / >=65), Sex, Region, ECOG (0 vs 1) |
| Disease-specific baseline | Disease-specific baseline characteristics | Tumor type, Stage, Number of prior lines |
| Multicenter design | Whether multicenter, and countries/regions | true; US, EU, Asia-Pacific |
| Age strata | Protocol-defined age subgroup cutpoints | 6-11 years, 12-17 years, 18-64 years |
| Coding dictionaries | MedDRA and WHO Drug Dictionary versions | MedDRA 26.0, WHO-DD March 2024 |
| Therapeutic area | Therapeutic area | oncology, immunology, neurology |
| Discontinuation reasons | Protocol-defined reasons for discontinuation | AE, Disease progression, Withdrawal |
| Deviation categories | Protocol-defined protocol deviation categories | I/E criteria, Prohibited medication |

### 1.16 Figures and Listings

| Fact | Description | Example Values |
|------|-------------|----------------|
| Figure requirements | Explicitly identified figures with type, endpoint, and description | kaplan_meier for PFS, forest_plot for ORR |
| Listing domains | Every data domain that needs a patient-level listing | disposition, demographics, each lab panel, AEs, etc. |

---

## Section 2: Generation Rules by Domain

Each subsection below describes one domain of TLF generation. For each table, the condition column indicates when the table is included. Tables with no condition are always generated.

---

### 2.1 Disposition (ICH Section 10.1)

Display order: 1

| Output | Population | Condition |
|--------|------------|-----------|
| Subject Disposition | Screened | Always included |
| Protocol Deviations | Enrolled | Always included |

---

### 2.2 Demographics and Baseline Characteristics (ICH Section 11.2)

Display order: 2

| Output | Population | Condition |
|--------|------------|-----------|
| Demographics and Baseline Characteristics | Safety | Always included |
| Demographics and Baseline Characteristics (Full Analysis Set) | FAS | When the study defines more than one analysis population |
| Patient Distribution by Country | Enrolled | When the study is a multicenter design |
| Physical Examination - Shift Table | Safety | When the protocol collects physical exam assessments |
| ECOG Performance Status by Visit | Safety | When the protocol assesses ECOG Performance Status |
| ECOG Performance Status - Shift Table | Safety | When the protocol assesses ECOG Performance Status |
| Pregnancy Test Summary | Safety | When the protocol includes pregnancy testing |

---

### 2.3 Medical History (ICH Section 11.2)

Display order: 3

| Output | Population | Condition |
|--------|------------|-----------|
| Medical History | Safety | Always included |
| Prior and Concomitant Therapies | Safety | Always included |
| Viral Serology | Safety | When the protocol collects viral serology |
| Biomarker and Genomic Screening | Safety | When the protocol includes gene/biomarker screening |

---

### 2.4 Concomitant Medications (ICH Section 9.4.7)

Display order: 4

| Output | Population | Condition |
|--------|------------|-----------|
| Concomitant Medications | Safety | Always included |

---

### 2.5 Adverse Events (ICH Section 12.2)

Display order: 5

**Core AE tables (always included):**

| Output | Population |
|--------|------------|
| Overview of Treatment-Emergent Adverse Events | Safety |
| TEAEs by SOC and PT | Safety |
| Treatment-Related TEAEs by SOC and PT | Safety |
| TEAEs Grade >=3 by SOC and PT | Safety |
| Serious TEAEs by SOC and PT | Safety |
| TEAEs Leading to Discontinuation of Study Treatment | Safety |
| TEAEs Leading to Death | Safety |
| TEAEs with Incidence >=5% in Any Treatment Group | Safety |
| TEAEs by SOC, PT, and Maximum Severity | Safety |

**Dose modification tables:**

| Output | Population | Condition |
|--------|------------|-----------|
| TEAEs Leading to Dose Modification | Safety | When the protocol allows dose modifications |
| Dose Reductions | Safety | When the protocol allows dose modifications |
| Dose Interruptions | Safety | When the protocol allows dose modifications |

**Grouped AE term tables:**

| Output | Population | Condition |
|--------|------------|-----------|
| TEAEs - (one per grouped term) | Safety | When the extraction identified grouped AE terms (e.g., Infections, Cardiac events) |

**Safety concern tables:**

| Output | Population | Condition |
|--------|------------|-----------|
| TEAEs Related to (concern) - one per safety concern | Safety | When drug-class or study-specific safety concerns are identified |

**Biosimilar / equivalence design tables:**

| Output | Population | Condition |
|--------|------------|-----------|
| TEAEs Related to Study Drug | Safety | When the study design is biosimilar or equivalence |
| TEAEs Related to Study Drug Grade >=3 | Safety | When the study design is biosimilar or equivalence |
| Tipping Point Analysis | Safety | When the study design is biosimilar or equivalence |
| Equivalence / Biosimilarity Margins Summary | Safety | When the study design is biosimilar or equivalence |

**Oncology + biosimilar prior therapy tables:**

| Output | Population | Condition |
|--------|------------|-----------|
| Prior Cancer Therapy -- Surgical Procedures | Safety | When the study is both oncology and biosimilar/equivalence |
| Prior Cancer Therapy -- Radiotherapy | Safety | When the study is both oncology and biosimilar/equivalence |
| Prior Cancer Therapy -- Systemic by Drug Class | Safety | When the study is both oncology and biosimilar/equivalence |

---

### 2.6 Adverse Events of Special Interest (ICH Section 12.2)

Display order: 14

| Output | Population | Condition |
|--------|------------|-----------|
| AESI - (name) -- one table per AESI defined in the protocol | Safety | One table is generated for each AESI identified in the protocol. The AESI definition determines which extra rows appear in the table. |

---

### 2.7 Exposure (ICH Section 12.1)

Display order: 3

| Output | Population | Condition |
|--------|------------|-----------|
| Study Drug Exposure | Safety | Always included |
| Study Drug Dose Modifications | Safety | When the protocol allows dose modifications |
| Rescue Medication Use | Safety | When rescue medications are identified in the protocol |

---

### 2.8 Laboratory Parameters (ICH Section 12.4)

Display order: 6

**Per-panel tables (primary path, when extraction identifies individual lab panels):**

| Output | Population | Condition |
|--------|------------|-----------|
| (Panel Name) - Summary Statistics -- one per lab panel | Safety | When the protocol defines specific lab panels |
| (Panel Name) - Shift Table -- one per lab panel | Safety | When the protocol defines specific lab panels |

**Cross-panel safety tables:**

| Output | Population | Condition |
|--------|------------|-----------|
| Laboratory Parameters - CTCAE Grade Summary | Safety | When the protocol collects lab assessments |
| Laboratory Parameters - CTCAE Grade Shift | Safety | When the protocol collects lab assessments |
| Subjects with Markedly Abnormal Laboratory Values | Safety | When the protocol collects lab assessments |

**Liver function tables:**

| Output | Population | Condition |
|--------|------------|-----------|
| Liver Function Tests - Summary Statistics | Safety | When the protocol collects lab assessments |
| Potential Hy's Law Cases | Safety | When the protocol collects lab assessments |

**Fallback tables (when labs are collected but no specific panels were extracted):**

| Output | Population | Condition |
|--------|------------|-----------|
| Hematology Parameters - Summary Statistics | Safety | When labs are collected but no specific lab panels were identified |
| Clinical Chemistry Parameters - Summary Statistics | Safety | When labs are collected but no specific lab panels were identified |
| Urinalysis Parameters - Summary Statistics | Safety | When labs are collected but no specific lab panels were identified |
| Hematology Parameters - Shift Table | Safety | When labs are collected but no specific lab panels were identified |
| Clinical Chemistry Parameters - Shift Table | Safety | When labs are collected but no specific lab panels were identified |

---

### 2.9 Vital Signs (ICH Section 12.5)

Display order: 7

| Output | Population | Condition |
|--------|------------|-----------|
| Vital Signs - Summary Statistics by Visit | Safety | When the protocol collects vital signs |
| Vital Signs - Change from Baseline by Visit | Safety | When the protocol collects vital signs |
| Subjects with Markedly Abnormal Vital Sign Values | Safety | When the protocol collects vital signs |
| Orthostatic Blood Pressure and Heart Rate Assessment | Safety | When the protocol requires orthostatic measurements |

---

### 2.10 ECG (ICH Section 12.6)

Display order: 8

| Output | Population | Condition |
|--------|------------|-----------|
| Electrocardiogram Parameters - Summary by Visit | Safety | When the protocol collects ECG assessments |
| Electrocardiogram - Qualitative Results | Safety | When the protocol collects ECG assessments |
| QTcF Change from Baseline - Categorical Analysis | Safety | When the protocol collects ECG assessments (ICH E14 thresholds) |

---

### 2.11 Pharmacokinetics (ICH Section 12.1)

Display order: 9

| Output | Population | Condition |
|--------|------------|-----------|
| Plasma Drug Concentration by Visit -- Summary Statistics | PK | When the protocol collects PK samples |
| PK Parameters - Summary Statistics | PK | When the protocol collects PK samples |

---

### 2.12 Immunogenicity (ICH Section 12.1)

Display order: 10

| Output | Population | Condition |
|--------|------------|-----------|
| Immunogenicity - Anti-Drug Antibody Incidence | Safety | When the protocol assesses immunogenicity |
| Immunogenicity - Neutralizing Antibody Status | Safety | When NAb testing is performed |
| TEAEs by ADA Status | Safety | When ADA impact analysis is specified |

---

### 2.13 Primary Efficacy (ICH Section 11)

Display order: 11

One table is generated for each primary endpoint, for each applicable population, and for each review type (if reviews such as BICR/Investigator are specified). The table type is selected based on the endpoint data type:

| Endpoint Type | Table Template Used |
|---------------|---------------------|
| Time-to-event | Time-to-event analysis |
| Binary | Binary response analysis |
| Continuous | Continuous endpoint analysis |
| Count | Continuous endpoint analysis |
| Ordinal | Continuous endpoint analysis |
| Rate | Continuous endpoint analysis |

**Title pattern:** "(Endpoint Name) ((Review) Review) ((Population) Population)"

Footnotes are auto-generated based on the analysis method.

---

### 2.14 Secondary Efficacy (ICH Section 11)

Display order: 12

Same structure as primary efficacy, but applies to all non-primary endpoints (secondary and exploratory). One table per endpoint, per population, per review type.

| Endpoint Type | Table Template Used |
|---------------|---------------------|
| Time-to-event | Time-to-event analysis |
| Binary | Binary response analysis |
| Continuous | Continuous endpoint analysis |
| Count | Continuous endpoint analysis |
| Ordinal | Continuous endpoint analysis |
| Rate | Continuous endpoint analysis |

---

### 2.15 Subgroup Analysis (ICH Section 11.4)

Display order: 13

| Output | Population | Condition |
|--------|------------|-----------|
| Subgroup Analysis of (Endpoint Name) -- one per primary or key secondary endpoint | ITT | When the protocol defines pre-specified subgroup analyses. Generated for each endpoint that is either primary or key secondary. |

---

### 2.16 Quality of Life / PRO (ICH Section 11.3)

Display order: 15

| Output | Population | Condition |
|--------|------------|-----------|
| (Instrument) - Summary by Visit -- one per QoL/PRO instrument | ITT | When the protocol collects QoL/PRO instruments |
| (Instrument) - Change from Baseline -- one per instrument | ITT | When the protocol collects QoL/PRO instruments |

---

### 2.17 Backbone Therapy (ICH Section 12.1)

Display order: 15

| Output | Population | Condition |
|--------|------------|-----------|
| (Drug Name) Exposure -- one table per backbone therapy | Safety | When the protocol defines backbone/background therapies |
| Individual (Drug Name) Exposure listing -- one per backbone therapy | Safety | When the protocol defines backbone/background therapies |

---

### 2.18 Period-Split Safety (ICH Section 12)

Display order: 16

These tables are generated when the study has multiple treatment periods (e.g., Induction and Maintenance), providing period-specific safety summaries.

| Output | Population | Condition |
|--------|------------|-----------|
| Overview of TEAEs - (Period) Period -- one per treatment period | Safety | When the study has more than one treatment period |
| TEAEs by SOC and PT - (Period) Period -- one per treatment period | Safety | When the study has more than one treatment period |
| Serious TEAEs - (Period) Period -- one per treatment period | Safety | When the study has more than one treatment period |

---

### 2.19 Figures

Display order: 17

**Extraction-based figures:** Any figures explicitly identified by the protocol extraction are generated first. These include figure type, associated endpoint, and description.

**Deterministic figures (rule-based):**

| Figure | Condition |
|--------|-----------|
| Kaplan-Meier Plot of (Endpoint) -- one per time-to-event endpoint | For every endpoint with type "time-to-event" |
| Forest Plot of (Endpoint) by Subgroup -- one per primary endpoint | For every primary endpoint, when the protocol defines subgroup analyses |
| Mean Change from Baseline in (Endpoint) Over Time | For every continuous primary endpoint |
| Mean Plasma Concentration-Time Profile (Linear Scale) | When the protocol collects PK samples |
| Mean Plasma Concentration-Time Profile (Semi-Log Scale) | When the protocol collects PK samples |
| CONSORT Flow Diagram | When the study design is superiority, non-inferiority, equivalence, or biosimilar |
| QoL Score Over Time - (Instrument) -- one per QoL instrument | When the protocol collects QoL/PRO instruments |

Note: Deduplication logic ensures that if a figure is captured both by extraction and by deterministic rules, only one copy is generated.

---

### 2.20 Listings (ICH Section 16.2)

Display order: 18

**Extraction-based listings:** Any data domain identified by the extraction layer generates a listing titled "Listing of (Domain)."

**Core listings (always included):**

| Listing Title | Population |
|---------------|------------|
| Listing of Deaths | Safety |
| Listing of Serious Adverse Events | Safety |
| Listing of TEAEs Leading to Discontinuation | Safety |
| Listing of TEAEs Leading to Death | Safety |
| Listing of Protocol Deviations | Enrolled |
| Listing of Screening Failures | Screened |
| Listing of Subject Disposition | Enrolled |
| Listing of Demographics | Enrolled |
| Listing of Medical History | Enrolled |
| Listing of Prior Medications | Safety |
| Listing of Concomitant Medications | Safety |
| Listing of Study Drug Exposure | Safety |
| Listing of All Adverse Events | Safety |

**Efficacy listings:**

| Listing Title | Population | Condition |
|---------------|------------|-----------|
| Listing of (Endpoint Name) Data -- one per endpoint | Enrolled | One listing per study endpoint |

**Conditional listings:**

| Listing Title | Population | Condition |
|---------------|------------|-----------|
| Listing of Adverse Events of Special Interest | Safety | When AESIs are defined in the protocol |
| Listing of (Panel Name) Results -- one per lab panel | Safety | When specific lab panels are identified |
| Listing of Clinical Chemistry Results | Safety | When labs are collected but no specific panels were identified (fallback) |
| Listing of Hematology Results | Safety | When labs are collected but no specific panels were identified (fallback) |
| Listing of Urinalysis Results | Safety | When labs are collected but no specific panels were identified (fallback) |
| Listing of Vital Signs | Safety | When the protocol collects vital signs |
| Listing of ECG Results | Safety | When the protocol collects ECG assessments |
| Listing of PK Concentrations | Safety | When the protocol collects PK samples |
| Listing of PK Parameters | Safety | When the protocol collects PK samples |
| Listing of Immunogenicity Results | Safety | When the protocol assesses immunogenicity |
| Listing of (Instrument) Responses -- one per QoL instrument | Enrolled | When the protocol collects QoL/PRO instruments |

---

## Section 3: Statistical Methods

Each analysis template below defines the complete shell structure for a statistical method, including the rows that appear in the table, footnotes, programming notes, and any associated figures or sensitivity analyses.

---

### 3.1 Time-to-Event Analyses

#### 3.1.1 Cox Proportional Hazards

- **When used:** PFS, OS, DFS, EFS, DOR, TTP, TTF, TTR, RFS
- **Source dataset:** ADTTE
- **Orientation:** Portrait
- **Column structure:** Two-arm

**Primary analysis:** Cox proportional hazards model with Kaplan-Meier estimation.

**Rows displayed:**

- Number of subjects
- Number of events, n (%)
- Number censored, n (%)
- **Kaplan-Meier Estimates**
    - 25th percentile [95% CI]
    - Median [95% CI]
    - 75th percentile [95% CI]
- **Landmark Rates [95% CI]** (optional, included based on protocol timepoints)
    - 6-month rate [95% CI]
    - 12-month rate [95% CI]
    - 24-month rate [95% CI]
- **Number at Risk** (optional)
    - At 6 months
    - At 12 months
    - At 24 months
- **Treatment Comparison** (comparison column only)
    - Hazard Ratio [95% CI]
    - P-value (stratified log-rank)

**Footnotes:**

- Kaplan-Meier estimates; 95% CI by Brookmeyer-Crowley method.
- Hazard ratio from Cox proportional hazards model.
- HR < 1 favors (treatment arm).
- Stratified by randomization stratification factors.

**Programming notes:**

- Use PROC LIFETEST for KM estimates
- Use PROC PHREG for Cox model
- Stratification factors per randomization
- Ties handled by Efron method
- 95% CI for median by Brookmeyer-Crowley (Klein-Moeschberger also acceptable)
- 95% CI for rates by Greenwood formula with log-log transformation

**Associated figures:**

- Kaplan-Meier Plot: Survival curves by treatment arm, number at risk table below x-axis, median lines, censoring tick marks, HR and p-value annotation
- Subgroup Analysis Forest Plot: Subgroup labels, n/N per arm, HR [95% CI] per subgroup, vertical reference at HR=1, interaction p-values

**Sensitivity analyses:**

- **Unstratified:** Removes stratification. P-value label changes to "P-value (unstratified log-rank)." Removes STRATA statement from PROC PHREG.
- **Per-protocol population:** Filters to PPROTFL = 'Y'. Adds per-protocol population footnote.
- **Additional covariates:** Adds "Adjusted Hazard Ratio [95% CI]" row. Includes pre-specified covariates in MODEL statement.

---

#### 3.1.2 Restricted Mean Survival Time (RMST)

- **When used:** PFS, OS, DFS, EFS
- **Source dataset:** ADTTE
- **Orientation:** Portrait
- **Column structure:** Two-arm

**Primary analysis:** Restricted mean survival time analysis, calculated as area under the KM curve up to restriction time tau.

**Rows displayed:**

- Number of subjects
- Number of events, n (%)
- **RMST at (tau) months**
    - RMST [95% CI]
- **Treatment Comparison** (comparison column only)
    - Difference in RMST [95% CI]
    - Ratio of RMST [95% CI]
    - P-value

**Footnotes:**

- RMST calculated as area under KM curve up to restriction time (tau).
- 95% CI based on pseudo-value approach.

**Programming notes:**

- Use %RMST macro or PROC RMSTREG (SAS 9.4 TS1M7+)
- Restriction time tau must be pre-specified
- Consider when PH assumption is violated

---

#### 3.1.3 Competing Risks (Fine-Gray / Cumulative Incidence)

- **When used:** Disease recurrence, cause-specific mortality, graft failure
- **Source dataset:** ADTTE
- **Orientation:** Portrait
- **Column structure:** Two-arm

**Primary analysis:** Competing risks analysis using cumulative incidence function (Aalen-Johansen method) and Fine-Gray subdistribution hazard model.

**Rows displayed:**

- Number of subjects
- Event of interest, n (%)
- Competing event, n (%)
- Censored, n (%)
- **Cumulative Incidence Estimates** (optional timepoints)
    - 6-month CIF [95% CI]
    - 12-month CIF [95% CI]
- **Treatment Comparison** (comparison column only)
    - Subdistribution HR [95% CI]
    - P-value (Gray's test)

**Footnotes:**

- Cumulative incidence function (CIF) estimated by Aalen-Johansen method.
- Subdistribution hazard ratio from Fine-Gray model.
- Gray's test for equality of CIFs.

**Associated figure:** Cumulative Incidence Plot -- CIF curves by treatment arm, number at risk table, competing event indicated.

**Programming notes:**

- Use PROC LIFETEST with EVENTCODE option (SAS 9.4M5+) or %CIF macro
- Fine-Gray model via PROC PHREG with EVENTCODE

---

### 3.2 Categorical / Binary Response Analyses

#### 3.2.1 Exact Binomial (Clopper-Pearson)

- **When used:** ORR, CR rate, DCR, CBR, responder rate
- **Source dataset:** ADRS
- **Orientation:** Portrait
- **Column structure:** Two-arm with Total column

**Primary analysis:** Exact binomial proportion with Clopper-Pearson confidence interval.

**Rows displayed:**

- Evaluable subjects, N
- **Responders, n (%)** (bold)
    - [95% CI]
- Non-responders, n (%)
- **Treatment Comparison** (comparison column only)
    - Difference [95% CI]
    - Odds Ratio [95% CI]
    - P-value

**Footnotes:**

- 95% CI calculated using Clopper-Pearson exact method.
- 95% CI for risk difference by Newcombe method.
- P-value from Fisher's exact test.

**Programming notes:**

- Use PROC FREQ with EXACT BINOMIAL for CI
- Newcombe method for risk difference CI
- Fisher's exact test or CMH for comparison

**Sensitivity analysis:**

- **Stratified CMH:** P-value label changes to "P-value (stratified CMH)." Use PROC FREQ with CMH option and STRATA.

---

#### 3.2.2 Logistic Regression

- **When used:** ORR, responder rate, clinical response
- **Source dataset:** ADRS
- **Orientation:** Portrait
- **Column structure:** Two-arm

**Primary analysis:** Logistic regression for binary endpoint with covariates.

**Rows displayed:**

- Evaluable subjects, N
- Responders, n (%)
    - [95% CI]
- **Logistic Regression** (comparison column only)
    - Odds Ratio [95% CI]
    - P-value
- **Covariates in Model** (list covariates from SAP)

**Footnotes:**

- Odds ratio from logistic regression model.
- 95% CI calculated using Clopper-Pearson exact method.

**Programming notes:**

- Use PROC LOGISTIC
- Include treatment and pre-specified covariates
- Profile likelihood CI for OR

---

#### 3.2.3 Proportional Odds Model (Ordinal Response)

- **When used:** Ordinal response, severity scale, CGI improvement
- **Source dataset:** ADEFF
- **Orientation:** Portrait
- **Column structure:** Two-arm

**Primary analysis:** Proportional odds model (cumulative logit) for ordinal categorical endpoint.

**Rows displayed:**

- Evaluable subjects, N
- **Response Distribution** (categories from therapeutic area configuration)
- **Proportional Odds Model** (comparison column only)
    - Common Odds Ratio [95% CI]
    - P-value

**Footnotes:**

- Proportional odds model (cumulative logit).
- Score test for proportional odds assumption.

**Programming notes:**

- Use PROC LOGISTIC with cumulative logit link
- Test PO assumption with score test

---

### 3.3 Continuous Endpoint Analyses

#### 3.3.1 ANCOVA (Single Timepoint)

- **When used:** Change from baseline, single-visit continuous endpoints
- **Source dataset:** ADEFF
- **Orientation:** Portrait
- **Column structure:** Two-arm

**Primary analysis:** Analysis of covariance for change from baseline.

**Rows displayed:**

- **Baseline**
    - n, Mean, SD, Median
- **Post-baseline (Week X)**
    - n, Mean, SD
- **Change from Baseline**
    - n, Mean, SD
- **ANCOVA Results**
    - LS Mean (SE)
    - LS Mean Difference [95% CI] (comparison only)
    - P-value (comparison only)

**Footnotes:**

- LS means and p-value from ANCOVA model.
- ANCOVA model includes treatment, baseline value, and stratification factors as covariates.

**Programming notes:**

- Use PROC GLM or PROC MIXED
- MODEL: change = treatment baseline strat_factors
- LSMEANS treatment / PDIFF CL

---

#### 3.3.2 MMRM (Repeated Measures)

- **When used:** Longitudinal continuous endpoints, repeated measures, PRO over time
- **Source dataset:** ADEFF
- **Orientation:** Landscape
- **Column structure:** Two-arm, by visit

**Primary analysis:** Mixed model for repeated measures.

**Rows displayed (repeated for each visit):**

- **Baseline**
    - n, Mean, SD
- **Visit X** (repeating)
    - n
    - LS Mean Change from Baseline (SE)
    - LS Mean Difference vs (comparator) [95% CI] (comparison only)
    - P-value (comparison only)

**Footnotes:**

- LS means from mixed model for repeated measures (MMRM).
- MMRM: treatment, visit, treatment x visit interaction, baseline value, stratification factors.
- Unstructured covariance matrix. Kenward-Roger degrees of freedom.

**Programming notes:**

- Use PROC MIXED or PROC GLIMMIX
- MODEL: change = treatment visit treatment*visit baseline strat / DDFM=KR
- REPEATED visit / SUBJECT=subject TYPE=UN
- LSMEANS treatment*visit / PDIFF CL SLICE=visit

**Associated figure:** LS Mean Change from Baseline Over Time -- LS mean with SE by visit and treatment arm, connecting lines, error bars, significance markers.

**Sensitivity analyses:**

- **Pattern mixture model (MNAR sensitivity):** Adds "Pattern Mixture Model" section with "LS Mean Difference (delta = X) [95% CI]." Multiple imputation under delta-adjusted MAR; vary delta from 0 to protocol-specified maximum.
- **Tipping point analysis:** Adds "Tipping Point Analysis" section with "Delta at which conclusion changes." Systematically increase delta until p > 0.05.

---

#### 3.3.3 GEE (Generalized Estimating Equations)

- **When used:** Repeated binary outcomes, clustered data, correlated outcomes
- **Source dataset:** ADEFF
- **Orientation:** Portrait
- **Column structure:** Two-arm

**Primary analysis:** GEE with exchangeable (or specified) working correlation structure.

**Rows displayed:**

- Number of subjects
- Number of observations
- **GEE Results**
    - Estimated Rate/Mean (SE)
    - Treatment Effect [95% CI] (comparison only)
    - P-value (comparison only)

**Footnotes:**

- GEE with exchangeable (or specified) working correlation structure.
- Robust (sandwich) standard errors.

**Programming notes:**

- Use PROC GENMOD with REPEATED statement
- TYPE=EXCH or TYPE=UN for working correlation

---

### 3.4 Count / Rate Data Analyses

#### 3.4.1 Negative Binomial Regression

- **When used:** Exacerbation rate, relapse rate, seizure frequency, bleeding episodes
- **Source dataset:** ADEFF
- **Orientation:** Portrait
- **Column structure:** Two-arm

**Primary analysis:** Negative binomial regression for event count/rate.

**Rows displayed:**

- Number of subjects
- Total exposure (patient-years)
- Total number of events
- **Adjusted Event Rate**
    - Adjusted annualized rate
    - [95% CI]
- **Treatment Comparison** (comparison only)
    - Rate Ratio [95% CI]
    - Rate Difference [95% CI] (optional)
    - P-value

**Footnotes:**

- Negative binomial regression model with log(exposure) as offset.
- Model includes treatment and stratification factors.

**Programming notes:**

- Use PROC GENMOD with DIST=NEGBIN LINK=LOG
- OFFSET = log(exposure time)
- LSMEANS for adjusted rates

---

#### 3.4.2 Poisson Regression

- **When used:** Event rate, incidence rate
- **Source dataset:** ADEFF
- **Orientation:** Portrait
- **Column structure:** Two-arm

**Primary analysis:** Poisson regression for event rates.

**Rows displayed:**

- Number of subjects
- Total exposure (patient-years)
- Total events
- Crude rate per patient-year
- **Poisson Model**
    - Adjusted Rate [95% CI]
    - Rate Ratio [95% CI] (comparison only)
    - P-value (comparison only)

**Footnotes:**

- Poisson regression with log(exposure) as offset.
- Check for overdispersion; use negative binomial if present.

**Programming notes:**

- PROC GENMOD with DIST=POISSON LINK=LOG
- SCALE=DEVIANCE if overdispersion detected

---

### 3.5 Non-Inferiority / Equivalence Analyses

#### 3.5.1 Non-Inferiority for Binary Endpoint

- **When used:** ORR (NI), response rate (NI), conversion rate (NI)
- **Source dataset:** ADRS
- **Orientation:** Portrait
- **Column structure:** Two-arm

**Rows displayed:**

- Evaluable subjects, N
- Responders, n (%)
    - [95% CI]
- **Non-Inferiority Assessment**
    - Risk Difference [95% CI] (comparison only)
    - Risk Ratio [95% CI] (comparison only, optional)
    - NI margin
    - NI conclusion (NI demonstrated if lower bound of CI > -margin)

**Footnotes:**

- 95% CI calculated using Clopper-Pearson exact method.
- 95% CI for risk difference by Newcombe method.
- Non-inferiority margin: -(margin).
- NI concluded if lower bound of 95% CI for risk difference > -(margin).

**Programming notes:**

- PROC FREQ with RISKDIFF (NONINF) option
- Margin from protocol/SAP
- One-sided alpha = 0.025 equivalent to two-sided 95% CI

---

#### 3.5.2 Non-Inferiority for Time-to-Event

- **When used:** PFS (NI), OS (NI)
- **Source dataset:** ADTTE
- **Orientation:** Portrait
- **Column structure:** Two-arm

**Rows displayed:**

- Number of events, n (%)
- Median [95% CI]
- **Non-Inferiority Assessment**
    - Hazard Ratio [95% CI] (comparison only)
    - NI margin (HR)
    - NI conclusion (NI demonstrated if upper bound of CI < margin)

**Footnotes:**

- Hazard ratio from Cox proportional hazards model.
- Non-inferiority margin: HR = (margin).
- NI concluded if upper bound of 95% CI for HR < (margin).

---

#### 3.5.3 Equivalence / Biosimilar (Binary Endpoint)

- **When used:** ORR (equivalence), biosimilar primary endpoint
- **Source dataset:** ADRS
- **Orientation:** Portrait
- **Column structure:** Two-arm

**Rows displayed:**

- Evaluable subjects, N
- Responders, n (%)
    - [95% CI]
- **Equivalence Assessment**
    - Risk Difference [90% CI] (comparison only)
    - Risk Ratio [90% CI] (comparison only)
    - Equivalence margins
    - Equivalence conclusion

**Footnotes:**

- Equivalence concluded if 90% CI for risk difference lies within [lower, upper].
- 90% CI corresponds to two one-sided tests at alpha = 0.05.

**Programming notes:**

- PROC FREQ with EQUIV option or TOST procedure
- 90% CI = two one-sided alpha 0.05
- Margins from protocol/regulatory agreement

---

### 3.6 Early Phase / Dose-Finding Analyses

#### 3.6.1 Traditional 3+3 Dose Escalation

- **When used:** Dose escalation, Phase 1
- **Source dataset:** ADSL
- **Orientation:** Landscape
- **Column structure:** By dose level

**Rows displayed:**

- **Dose Level**
    - Dose (mg or mg/kg)
    - N enrolled
    - N evaluable for DLT
    - DLTs, n (%)
    - DLT descriptions
    - Escalation decision

**Footnotes:**

- DLT = Dose-Limiting Toxicity, assessed during Cycle 1.
- DLT evaluation window: (window).

**Programming notes:**

- Descriptive summary by dose cohort
- No formal statistical testing

---

#### 3.6.2 Simon's Two-Stage

- **When used:** Single-arm Phase 2, ORR single-arm
- **Source dataset:** ADRS
- **Orientation:** Portrait
- **Column structure:** Single-arm

**Rows displayed:**

- **Stage 1**
    - N enrolled
    - Responders, n
    - Futility boundary
    - Decision
- **Stage 2 (cumulative)**
    - N enrolled (total)
    - Responders, n (total)
    - ORR [95% CI]
    - Efficacy boundary
    - Conclusion

**Footnotes:**

- Simon's optimal (or minimax) two-stage design.
- H0: response rate <= p0; H1: response rate >= p1.
- Alpha = (alpha), Power = (power).
- 95% CI calculated using Clopper-Pearson exact method.

**Programming notes:**

- Descriptive with exact binomial CI
- Decision rules from protocol

---

#### 3.6.3 Bayesian Dose-Finding (CRM / BOIN)

- **When used:** CRM, mTPI, BOIN, Bayesian Phase 1
- **Source dataset:** ADSL
- **Orientation:** Landscape
- **Column structure:** By dose level

**Rows displayed:**

- **Dose Level**
    - Dose (mg)
    - N treated
    - DLTs, n (%)
    - Posterior P(DLT) [95% CrI]
    - Escalation/de-escalation decision
    - MTD probability

**Footnotes:**

- Posterior probabilities from (model type) model.
- Target DLT rate: (target).
- 95% credible intervals (CrI).

**Programming notes:**

- R package: dfcrm (CRM), BOIN (BOIN)
- Document prior specification

---

### 3.7 Safety-Specific Table Structures

#### 3.7.1 AE Overview

- **Source dataset:** ADAE
- **Orientation:** Portrait
- **Population filter:** SAFFL = 'Y' and TRTEMFL = 'Y'
- **Column structure:** Two-arm with Total column

**Rows displayed:**

- **Subjects with at least one:**
    - TEAE
    - Grade >=3 TEAE
    - Grade 4 TEAE
    - Grade 5 TEAE (Death)
    - Serious TEAE
    - Treatment-related TEAE
    - Treatment-related Serious TEAE
    - TEAE leading to study drug discontinuation
    - TEAE leading to dose modification
    - TEAE leading to dose interruption
    - TEAE leading to death (Note: AEOUT = 'FATAL', distinct from Grade 5 which uses AETOXGR = '5')
- **Maximum CTCAE Grade:**
    - Grade 1 (Mild)
    - Grade 2 (Moderate)
    - Grade 3 (Severe)
    - Grade 4 (Life-threatening)
    - Grade 5 (Death)

**Footnotes:** Safety Population. TEAE definition. CTCAE version. MedDRA version. A subject is counted once in each applicable category.

**Programming notes:** Subject counted once per category (worst grade). Use PROC FREQ or custom macro.

---

#### 3.7.2 AE by SOC and Preferred Term

- **Source dataset:** ADAE
- **Orientation:** Landscape
- **Population filter:** SAFFL = 'Y' and TRTEMFL = 'Y'
- **Column structure:** Two-arm with Total column

**Rows displayed (dynamic, generated from data):**

- **System Organ Class** (bold, one group per SOC)
    - Preferred Term, n (%) -- sorted by decreasing frequency

**Footnotes:** Safety Population. MedDRA version. A subject is counted once in each applicable category. Sorted by decreasing frequency of total column within SOC. Only PTs with >= threshold% incidence in any group shown (if applicable).

**Programming notes:** Sort SOC by international order or frequency. Sort PT by decreasing frequency within SOC. Apply frequency threshold if specified.

---

#### 3.7.3 Lab Shift Table

- **Source dataset:** ADLB
- **Orientation:** Landscape
- **Column structure:** Shift table (Baseline vs. Post-baseline: Normal, Low, High)

**Rows displayed (dynamic, one block per parameter):**

- **Parameter (Unit)**
    - Baseline Category
        - Normal
        - Low
        - High

**Footnotes:** Baseline: last non-missing value prior to first dose. Post-baseline: worst post-baseline value. Normal ranges per central laboratory.

**Programming notes:** Use ANRIND (Analysis Normal Range Indicator). Baseline = ABLFL = 'Y'.

---

#### 3.7.4 Exposure Summary

- **Source dataset:** ADEX
- **Orientation:** Portrait
- **Column structure:** Two-arm with Total column

**Rows displayed:**

- Number of subjects treated
- **Duration of Treatment (weeks):** Mean, SD, Median, Min, Max
- **Number of Doses/Cycles Received:** Mean, SD, Median, Min, Max
- **Cumulative Dose (unit):** Mean, SD, Median
- **Relative Dose Intensity (%):** Mean, SD, Median, Min, Max

**Footnotes:** Safety Population. Relative dose intensity = 100 x (actual cumulative dose / planned cumulative dose).

---

#### 3.7.5 Concomitant Medications

- **Source dataset:** ADCM
- **Orientation:** Landscape
- **Column structure:** Two-arm with Total column

**Rows displayed (dynamic):**

- Subjects with at least one concomitant medication
- **ATC Class** (one per class)
    - Generic Drug Name, n (%) -- sorted by frequency

**Footnotes:** Safety Population. WHO Drug Dictionary coding. ATC classification. A subject is counted once in each applicable category.

**Programming notes:** Classify as prior (start before first dose) or concomitant (overlap with treatment). Use WHO Drug Dictionary for coding.

---

#### 3.7.6 Immunogenicity (ADA)

- **Source dataset:** ADAB
- **Orientation:** Portrait
- **Population filter:** ADAFL = 'Y'
- **Column structure:** Two-arm with Total column

**Rows displayed:**

- ADA Evaluable, N
- **ADA Status**
    - ADA Positive, n (%)
        - Treatment-emergent, n (%)
        - Treatment-boosted, n (%)
    - ADA Negative, n (%)
- **Neutralizing Antibody (NAb)**
    - NAb Evaluable, N
    - NAb Positive, n (%)
    - NAb Negative, n (%)
- **ADA Titer**
    - Median titer (range)

**Footnotes:** ADA Evaluable Population. Treatment-emergent: negative/missing at baseline, positive post-baseline. Treatment-boosted: positive at baseline with >=4-fold increase post-baseline.

---

#### 3.7.7 PK Parameters Summary

- **Source dataset:** ADPP
- **Orientation:** Landscape
- **Population filter:** PKFL = 'Y'
- **Column structure:** Two-arm

**Rows displayed (one block per PK parameter -- e.g., Cmax, AUC0-inf, Tmax, T1/2, CL, Vd):**

- n, Mean, SD, CV%, Median, Min, Max, Geometric Mean, Geometric CV%

**Footnotes:** PK Evaluable Population. Geometric statistics presented for log-normally distributed parameters. Tmax presented as median (min, max).

**Programming notes:** Log-transform for geometric statistics. Tmax: use median, not mean.

---

#### 3.7.8 PK Concentration-Time

- **Source dataset:** ADPC
- **Orientation:** Landscape
- **Column structure:** By timepoint

**Rows displayed (one block per timepoint):**

- n, Mean, SD, Median, Min, Max

**Associated figure:** Mean (+/-SD) Serum Concentration-Time Profile -- Linear and semi-log scales.

---

#### 3.7.9 Vital Signs by Visit

- **Source dataset:** ADVS
- **Orientation:** Landscape
- **Column structure:** Two-arm

**Parameters:** Systolic Blood Pressure (mmHg), Diastolic Blood Pressure (mmHg), Pulse Rate (beats/min), Body Temperature (deg C), Respiratory Rate (breaths/min), Weight (kg)

**Rows displayed (one block per parameter):**

- n, Mean, SD, Median, Min, Max
- Change from Baseline: Mean, SD, Median

---

#### 3.7.10 Vital Signs -- Markedly Abnormal

- **Source dataset:** ADVS
- **Orientation:** Portrait
- **Column structure:** Two-arm with Total column

**Rows displayed (one block per parameter):**

- High, n (%)
- Low, n (%)

**Footnotes:** Markedly abnormal criteria defined per protocol or regulatory guidance. Subjects counted once per parameter regardless of number of abnormal values.

---

#### 3.7.11 ECG Parameters by Visit

- **Source dataset:** ADEG
- **Orientation:** Landscape
- **Column structure:** Two-arm

**Parameters:** Heart Rate (bpm), PR Interval (msec), QRS Duration (msec), QT Interval (msec), QTcF Interval (msec)

**Rows displayed (one block per parameter):**

- n, Mean, SD, Median, Min, Max
- Change from Baseline: Mean, SD

**Footnotes:** QTcF = QT corrected by Fridericia method (QT/RR^0.33). Triplicate ECGs: use mean of triplicates per timepoint.

---

#### 3.7.12 QTcF Categorical Analysis

- **Source dataset:** ADEG (PARAMCD = 'QTCF')
- **Orientation:** Portrait
- **Column structure:** Two-arm with Total column

**Rows displayed:**

- **Maximum Post-baseline QTcF (msec)**
    - <450, n (%)
    - >=450 to <480, n (%)
    - >=480 to <500, n (%)
    - >=500, n (%)
- **Maximum Change from Baseline in QTcF (msec)**
    - <30, n (%)
    - >=30 to <60, n (%)
    - >=60, n (%)

**Footnotes:** QTcF = QT corrected by Fridericia method. Categories based on ICH E14 guidance. Each subject counted once using maximum post-baseline value.

**Programming notes:** Flag subjects with QTcF >=500 or change >=60 for narrative.

---

#### 3.7.13 ECG Qualitative Results

- **Source dataset:** ADEG
- **Orientation:** Portrait
- **Column structure:** Two-arm with Total column

**Rows displayed:**

- **Overall Interpretation**
    - Normal, n (%)
    - Abnormal - Not Clinically Significant, n (%)
    - Abnormal - Clinically Significant, n (%)

---

#### 3.7.14 Demographics and Baseline Characteristics

- **Source dataset:** ADSL
- **Orientation:** Portrait
- **Column structure:** Two-arm with Total column

**Rows displayed:**

- **Age (years):** n, Mean, SD, Median, Min, Max
- **Age group, n (%):** <65 years, >=65 years, >=75 years (optional)
- **Sex, n (%):** Male, Female
- **Race, n (%):** Categories from data or protocol (dynamic)
- **Ethnicity, n (%):** Hispanic or Latino, Not Hispanic or Latino, Not Reported
- **Weight (kg):** n, Mean, SD, Median
- **Height (cm):** n, Mean, SD, Median
- **BMI (kg/m2):** n, Mean, SD, Median
- Disease-specific baseline characteristics (appended from therapeutic area configuration or protocol extraction)

**Footnotes:** Percentages based on N in column header.

**Programming notes:** Use PROC MEANS for continuous, PROC FREQ for categorical. Percentages based on non-missing N.

---

#### 3.7.15 Disposition

- **Source dataset:** ADSL
- **Orientation:** Portrait
- **Column structure:** Two-arm with Total column

**Rows displayed:**

- Screened
- Screen Failures, n (%)
- **Randomized**
- Treated, n (%)
- **Study Treatment Status**
    - Completed study treatment, n (%)
    - Discontinued study treatment, n (%)
- **Reason for Discontinuation**
    - Adverse event, Disease progression (optional), Withdrawal by subject, Physician decision, Protocol deviation, Lost to follow-up, Death, Other
- **Study Status**
    - Completed study, Ongoing, Discontinued from study

**Footnotes:** Percentages based on N in column header. Percentages for screening based on N screened; all others based on N randomized.

**Associated figure:** CONSORT Flow Diagram.

---

#### 3.7.16 Medical History

- **Source dataset:** ADMH
- **Orientation:** Landscape
- **Column structure:** Two-arm with Total column

**Rows displayed (dynamic):**

- Subjects with at least one medical history
- **System Organ Class** (dynamic)
    - Preferred Term, n (%) (dynamic)

**Footnotes:** MedDRA version. A subject is counted once in each applicable category.

---

#### 3.7.17 Protocol Deviations

- **Source dataset:** ADSL
- **Orientation:** Portrait
- **Column structure:** Two-arm with Total column

**Rows displayed:**

- Subjects with at least one important protocol deviation, n (%)
- **Category of Deviation**
    - Inclusion/exclusion criteria not met
    - Prohibited concomitant medication
    - Incorrect study drug administration
    - Missed visit/assessment outside window
    - Informed consent issue
    - Other
- **Impact on Analysis Population**
    - Excluded from Per-Protocol Population, n (%)

**Footnotes:** ITT Population. Important protocol deviations as determined by the sponsor prior to database lock. A subject may have more than one protocol deviation.

---

### 3.8 Interim Analysis

#### 3.8.1 Group Sequential Monitoring Boundaries

- **Orientation:** Landscape
- **Column structure:** Custom

**Columns:** Analysis, Information Fraction (xx.x%), Nominal Alpha (1-sided, x.xxxx), Cumulative Alpha (x.xxxx), Efficacy Boundary (Z-score, x.xxxx), Futility Boundary (Z-score, x.xxxx), Efficacy Boundary (HR, x.xxx -- optional)

**Rows:** Interim Analysis 1, Interim Analysis 2 (optional), Final Analysis

**Footnotes:**

- Alpha-spending function: Lan-DeMets with O'Brien-Fleming-type boundary.
- Futility boundaries are non-binding.
- Boundaries calculated using EAST (version).

**Programming notes:**

- Use PROC SEQDESIGN / PROC SEQTEST or EAST software
- Document information fraction at each analysis

---

## Section 4: Standard Formatting

### 4.1 Column Structures

**Two-arm (no total):**

| Parameter | Treatment A (N=xxx) | Treatment B (N=xxx) |
|-----------|---------------------|---------------------|

Used for: Efficacy endpoints (time-to-event, binary response, continuous), PK parameters, vital signs by visit, ECG parameters by visit, lab summary by visit.

**Two-arm with Total:**

| Parameter | Treatment A (N=xxx) | Treatment B (N=xxx) | Total (N=xxx) |
|-----------|---------------------|---------------------|----------------|

Used for: Disposition, demographics, AE overview, AE by SOC/PT, exposure, concomitant medications, immunogenicity, QTcF categorical, ECG qualitative, markedly abnormal vitals.

**Three-arm with Total:**

| Parameter | Arm 1 (N=xxx) | Arm 2 (N=xxx) | Arm 3 (N=xxx) | Total (N=xxx) |
|-----------|----------------|----------------|----------------|----------------|

Used when the study has three treatment arms.

**Single-arm:**

| Parameter | Treatment A (N=xxx) |
|-----------|---------------------|

Used for: Simon's two-stage, single-arm studies.

**Shift table:**

| Parameter | Baseline | Post-baseline Normal | Post-baseline Low | Post-baseline High |
|-----------|----------|----------------------|-------------------|--------------------|

Used for: Lab shift tables.

**By dose level:**

| Dose Level 1 | Dose Level 2 | Dose Level 3 | ... |

Used for: 3+3 dose escalation, Bayesian dose-finding.

**By timepoint:**

| Timepoint 1 | Timepoint 2 | ... |

Used for: PK concentration-time tables.

### 4.2 Placeholder Conventions

All table shells use standardized placeholder values to indicate the format of the final numbers:

| Data Type | Placeholder Format |
|-----------|-------------------|
| Count | xx |
| Percentage | xx.x% |
| Count with percentage | n (xx.x%) |
| Mean | xx.x |
| Standard deviation | xx.xx |
| Median | xx.x |
| Minimum | xx.x |
| Maximum | xx.x |
| 1st Quartile | xx.x |
| 3rd Quartile | xx.x |
| 95% Confidence interval | [xx.x, xx.x] |
| Hazard ratio | x.xx |
| P-value | x.xxxx |
| Sample size (column header) | (N=xxx) |

### 4.3 Footnote Conventions

Footnotes are drawn from a standardized library and assembled per table. The standard categories are:

**Statistical method footnotes:**

- Kaplan-Meier estimates; 95% CI by Brookmeyer-Crowley method.
- Hazard ratio from Cox proportional hazards model.
- HR < 1 favors (treatment arm).
- 95% CI calculated using Clopper-Pearson exact method.
- 95% CI calculated using Wald method.
- 95% CI for risk difference by Newcombe method.
- Stratified by randomization stratification factors.
- P-value from Cochran-Mantel-Haenszel test.
- P-value from Fisher's exact test.
- LS means and p-value from ANCOVA model.
- LS means from mixed model for repeated measures (MMRM).
- Odds ratio from logistic regression model.

**Definition footnotes:**

- Treatment-emergent: onset on or after first dose of study drug through safety follow-up.
- Serious: meeting ICH E2A seriousness criteria.
- Related: assessed as possibly, probably, or definitely related by investigator.

**Coding footnotes:**

- Adverse events coded using MedDRA version (version).
- Medications coded using WHO Drug Dictionary.
- Medications classified by ATC coding system.
- Severity graded per NCI CTCAE version (version).

**General footnotes:**

- A subject is counted once in each applicable category.
- Data cutoff: (date).
- Percentages based on N in column header.

**Standard abbreviations footnote:** N = number of subjects in the population; n = number of subjects with data/event; SD = standard deviation; SE = standard error; CI = confidence interval; HR = hazard ratio; OR = odds ratio; LS = least squares; Min = minimum; Max = maximum.

### 4.4 Table Numbering (ICH Sections)

| ICH Section | Category | Table Types |
|-------------|----------|-------------|
| 14.1 | Disposition and Demographics | Disposition, demographics, medical history, baseline characteristics |
| 14.2 | Efficacy | Time-to-event, binary response, continuous endpoint, PRO/QoL, subgroup forest |
| 14.3 | Safety | AE overview, AE by SOC/PT, AESI, labs, lab shift, vitals, ECG, exposure, concomitant medications |
| 12.1 | PK, Immunogenicity, Exposure | PK parameters, PK concentration, immunogenicity, exposure |
| 16.2 | Listings | All patient-level data listings |

### 4.5 Table Orientation Defaults

| Table Type | Orientation |
|------------|-------------|
| Disposition | Portrait |
| Demographics | Portrait |
| AE Overview | Portrait |
| AE by SOC/PT | Landscape |
| Labs summary | Landscape |
| Lab shift tables | Landscape |
| Vital signs | Landscape |
| ECG | Landscape |
| Time-to-event | Portrait |
| Binary response | Portrait |
| Continuous endpoint | Portrait |
| PK parameters | Landscape |
| Exposure | Portrait |
| Subgroup forest | Landscape |
| Listings | Landscape |

### 4.6 Standard Analysis Populations

| Population | Definition | ADaM Flag |
|------------|------------|-----------|
| ITT (Intent-to-Treat) | All randomized subjects | ITTFL = 'Y' |
| Safety | All subjects who received at least one dose of study drug | SAFFL = 'Y' |
| Per-Protocol (PP) | All ITT subjects without major protocol deviations | PPROTFL = 'Y' |
| Modified ITT (mITT) | All randomized subjects who received at least one dose and had baseline assessment | MITTFL = 'Y' |
| PK Evaluable | All subjects with at least one evaluable PK sample | PKFL = 'Y' |
| ADA Evaluable | All subjects with baseline and at least one post-baseline ADA sample | ADAFL = 'Y' |

### 4.7 Standard ADaM Datasets

| Dataset | Description | Used For |
|---------|-------------|----------|
| ADSL | Subject-Level Analysis Dataset | Disposition, demographics, baseline |
| ADAE | Adverse Events Analysis Dataset | AE overview, AE by SOC/PT, AESI |
| ADTTE | Time-to-Event Analysis Dataset | Time-to-event endpoints |
| ADRS | Response Analysis Dataset | Binary response endpoints |
| ADLB | Laboratory Analysis Dataset | Lab summaries, lab shift tables |
| ADVS | Vital Signs Analysis Dataset | Vital signs |
| ADEG | ECG Analysis Dataset | ECG parameters |
| ADEX | Exposure Analysis Dataset | Study drug exposure |
| ADCM | Concomitant Medications Analysis Dataset | Concomitant medications |
| ADMH | Medical History Analysis Dataset | Medical history |
| ADPC | PK Concentration Analysis Dataset | PK concentration-time |
| ADPP | PK Parameters Analysis Dataset | PK parameter summaries |
| ADAB | Immunogenicity Analysis Dataset | ADA/immunogenicity |
| ADEFF | Efficacy Analysis Dataset | Continuous/ordinal endpoints |
| ADQS | Questionnaire Analysis Dataset | PRO/QoL instruments |

### 4.8 CTCAE Grading

| Grade | Label |
|-------|-------|
| 1 | Mild |
| 2 | Moderate |
| 3 | Severe |
| 4 | Life-threatening |
| 5 | Death |

Standard groupings: Grade 1-5 (any grade), Grade >=3, Grade 3-4.

### 4.9 AE Categories (ICH E2A)

| Code | Label | Definition |
|------|-------|------------|
| TEAE | Treatment-Emergent Adverse Event | AE with onset on or after first dose through safety follow-up |
| TRAE | Treatment-Related Adverse Event | TEAE assessed as related to study treatment by investigator |
| SAE | Serious Adverse Event | AE meeting ICH E2A seriousness criteria (death, life-threatening, hospitalization, disability, congenital anomaly, important medical event) |
| AESI | Adverse Event of Special Interest | Pre-specified AEs requiring enhanced monitoring |

---

**End of Document**
