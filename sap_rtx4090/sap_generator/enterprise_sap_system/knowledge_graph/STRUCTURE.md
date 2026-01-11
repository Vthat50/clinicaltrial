# Knowledge Graph System Structure (v78)
## Complete File Inventory & Contents

---

## Directory Structure

```
knowledge_graph/
├── CORE PIPELINE
│   ├── kg_enhanced_pipeline.py        (3319 lines) - Main orchestration
│   ├── kb_tools.py                    (3844 lines) - 83 Claude tools
│   └── sap_structure_config.py        (1031 lines) - Dynamic routing
│
├── KNOWLEDGE BASES
│   ├── comprehensive_sap_elements.py  (1851 lines) - 35 SAP categories
│   ├── methodology_knowledge_base.py  (1813 lines) - Statistical methods
│   ├── complete_tfl_inventory.py      (1686 lines) - TFL templates
│   ├── production_sap_specifications.py (1375 lines) - SAP specs
│   ├── oncology_reference_data.py     (1265 lines) - Disease modules
│   ├── regulatory_standards.py        (691 lines)  - ICH/FDA standards
│   ├── disease_specific_criteria.py   (679 lines)  - Response criteria
│   └── adam_specifications.py         (668 lines)  - ADaM datasets
│
├── EXTRACTION & RAG
│   ├── claude_extractor.py            (1043 lines) - Protocol extraction
│   ├── factual_knowledge_graph.py     (895 lines)  - Fact graph
│   ├── sap_knowledge_graph.py         (845 lines)  - SAP graph
│   ├── graph_rag.py                   (802 lines)  - RAG retrieval
│   └── protocol_specific_extractor.py (702 lines)  - Protocol parser
│
├── UTILITIES
│   ├── pdf_extraction_pipeline.py     (748 lines)  - PDF processing
│   ├── kg_claude_pipeline.py          (461 lines)  - Legacy pipeline
│   ├── visualize_graph.py             (446 lines)  - Graph visualization
│   └── __init__.py                    (34 lines)   - Module exports
│
└── TESTS
    ├── kg_pipeline_test.py            (742 lines)
    ├── kg_sap_generation_test.py      (416 lines)
    ├── test_protocol_driven.py        (162 lines)
    ├── test_metastatic_recist.py      (124 lines)
    ├── test_prostate.py               (124 lines)
    └── test_adjuvant.py               (120 lines)
```

**Total: 25,886 lines of Python code**

---

## CORE PIPELINE FILES

### 1. kg_enhanced_pipeline.py (3319 lines)
**Purpose:** Main pipeline orchestrating extraction → verification → generation

```python
CLASSES:
├── VerificationError          # Error tracking for SAP verification
├── VerificationResult         # Verification outcome container
├── PowerCalculation           # Sample size calculation results
├── SelfRAGVerifier           # Verifies SAP against protocol facts
├── SimplePowerCalculator     # Phase-specific power calculations
├── SimpleRAGRetriever        # Retrieves similar SAP examples
├── EnhancedClaudeSAPGenerator # Claude API integration for generation
└── EnhancedKGPipeline        # Main pipeline class

METHODS (EnhancedClaudeSAPGenerator):
├── generate_sap()                    # Main generation with tools
├── generate_sap_with_tools()         # Tool-augmented generation
├── regenerate_with_corrections()     # Error correction loop
├── _format_facts_with_provenance()   # Format extracted facts
├── _build_prohibition_rules()        # Build anti-hallucination rules
├── _build_protocol_specific_requirements()  # Protocol requirements
├── _build_tool_routing_instructions()      # KB tool routing
├── _format_power_calc()              # Power calculation formatting
└── _strip_conversational_preamble()  # Clean Claude output

METHODS (EnhancedKGPipeline):
├── process_protocol()                # Main entry point
├── _load_existing_kg()              # Load knowledge graph
├── _extract_entities()              # Entity extraction
└── _build_extraction_prompt()       # Extraction prompt building
```

---

### 2. kb_tools.py (3844 lines)
**Purpose:** 83 Claude-callable tools for knowledge base retrieval

```python
CLASSES:
├── TrialPrecedentKG          # Similar trial lookup (vector search)
├── KBRetrievalResult         # Standardized return type
└── KnowledgeBaseTools        # Main tool container (83 methods)

TOOL CATEGORIES (83 total):

Statistical Methods (15 tools):
├── get_statistical_method()           # Cox, log-rank, CMH, etc.
├── get_missing_data_method()          # LOCF, MMRM, MI, MNAR
├── get_sensitivity_analysis()         # Per-protocol, tipping point
├── get_sensitivity_analysis_catalog() # Full sensitivity catalog
├── get_multiplicity_adjustment()      # Hochberg, Holm, gatekeeping
├── get_multiplicity_methods()         # Extended multiplicity
├── get_confidence_interval_methods()  # Clopper-Pearson, Wilson
├── get_interim_analysis()             # O'Brien-Fleming, alpha spending
├── get_interim_analysis_specs()       # Detailed interim specs
├── get_time_to_event_analysis()       # K-M, Cox, restricted mean
├── get_censoring_rules()              # PFS, OS, DOR censoring
├── get_subgroup_analysis_specs()      # Forest plots, interaction
├── get_stratification_specs()         # Stratified analyses
├── get_stratification_balance_specs() # Balance assessment
└── get_phase2_design_specs()          # Simon two-stage, Fleming

Population & Baseline (10 tools):
├── get_population_definitions()       # ITT, mITT, Safety, PP
├── get_demographics_baseline_specs()  # Age, sex, race, ECOG
├── get_prior_therapy_specs()          # Prior lines, refractory
├── get_concomitant_medication_specs() # WHO Drug, ATC
├── get_medical_history_specs()        # MedDRA coding
├── get_organ_function_specs()         # Hepatic, renal, cardiac
├── get_organ_function_scores()        # Child-Pugh, CrCl
├── get_performance_status_scales()    # ECOG, Karnofsky
├── get_prognostic_scores()            # IPI, FLIPI, ISS, IMDC
└── get_enrollment_specifications()    # Enrollment summaries

Endpoint & Response (12 tools):
├── get_tumor_response_specs()         # Response assessment methodology
├── get_response_criteria()            # RECIST, Lugano by name
├── get_all_response_criteria()        # All criteria combined
├── get_recist_specifications()        # RECIST 1.1 details
├── get_cml_criteria()                 # CML ELN criteria
├── get_iwcll_criteria()               # iwCLL 2018 criteria
├── get_concordance_analysis()         # IRC vs Investigator
├── get_concordance_specs()            # Kappa, concordance matrix
├── get_estimand_framework()           # ICH E9(R1) estimands
├── get_estimand_specifications()      # Detailed estimand specs
├── get_mrd_assessment_specs()         # MRD analysis
└── get_biomarker_endpoints()          # Biomarker analysis

Safety Analysis (12 tools):
├── get_safety_analysis_specs()        # AE, SAE, AESI analysis
├── get_safety_specifications()        # Safety methodology
├── get_safety_tables()                # Safety TFL shells
├── get_ae_period_specifications()     # TEAE windows
├── get_death_analysis_specs()         # Death summaries, last alive
├── get_exposure_specifications()      # Dose, duration, compliance
├── get_treatment_compliance_specs()   # Dose modifications
├── get_subsequent_therapy_specs()     # Post-study therapy
├── get_immunogenicity_specs()         # ADA analysis
├── get_meddra_search_strategies()     # SMQ, MST, custom queries
├── get_healthcare_utilization_specs() # HRU analysis
└── get_covid19_variations()           # COVID-19 sensitivity

TFL Templates (12 tools):
├── get_disposition_tables()           # Disposition shells
├── get_efficacy_tables()              # Efficacy shells
├── get_safety_tables()                # Safety shells
├── get_all_figures()                  # All figure specs
├── get_figure_template()              # Figure by ID
├── get_table_template()               # Table by ID
├── get_listings()                     # Listing shells
├── get_tfl_shells()                   # Combined TFL shells
├── get_oncology_tfl_templates()       # Oncology-specific TFL
├── get_single_arm_tables()            # Phase 2 tables
├── get_lymphoma_tables()              # Lymphoma-specific
└── get_cart_tables()                  # CAR-T specific

Therapy-Specific (6 tools):
├── get_cart_specifications()          # CAR-T: CRS, ICANS, kinetics
├── get_cart_manufacturing_specs()     # Leukapheresis, V2V time
├── get_bispecific_specifications()    # Bispecific safety
├── get_adc_specifications()           # ADC toxicities
├── get_pkpd_analysis_specs()          # PK/PD analysis
└── get_blinding_specifications()      # Blinding procedures

Data & Programming (10 tools):
├── get_adam_dataset_spec()            # ADSL, ADAE, ADTTE, etc.
├── get_data_handling_rules()          # Data conventions
├── get_programming_specifications()   # Programming specs
├── get_derived_variables()            # Derived variable specs
├── get_analysis_windows()             # Visit windows
├── get_analysis_timing_specs()        # Assessment timing
├── get_data_cutoff_specs()            # Data cutoff rules
├── get_date_imputation_rules()        # Partial date handling
├── get_tte_derivation_tables()        # DOR, PFS, OS circumstance
└── get_protocol_deviation_specs()     # Protocol deviations

Study Design & References (6 tools):
├── get_study_design_specs()           # Design methodology
├── get_study_type_template()          # Adjuvant, basket, umbrella
├── get_study_definitions()            # Study Day, baseline, TEAE
├── get_required_references()          # ICH, FDA citations
├── get_qol_analysis_specs()           # PRO/QoL instruments
└── get_pro_qol_analysis()             # PRO analysis methods

Meta & Utility (3 tools):
├── get_comprehensive_sap_elements()   # All SAP elements
├── get_similar_trials()               # Trial precedent lookup
└── get_retrieval_log()                # Internal logging

API Schema:
└── get_claude_tool_definitions()      # Returns 83 tool schemas
```

---

### 3. sap_structure_config.py (1031 lines)
**Purpose:** Dynamic SAP section routing based on protocol characteristics

```python
CLASSES:
└── SAPSection                         # Section definition dataclass
    ├── number: str                    # "1", "7.1", "A1"
    ├── title: str                     # Section title
    ├── required: bool                 # Always include?
    ├── condition: str                 # Condition key
    ├── subsections: List[SAPSection]  # Nested sections
    ├── description: str               # Section description
    └── kb_tools: List[str]            # Tools to call

MASTER_SAP_SECTIONS (24 main sections):
├── 1.  TITLE PAGE & ADMINISTRATIVE INFORMATION
├── 2.  INTRODUCTION
│       └── 2.1 Study Background
│       └── 2.2 Study Objectives
│       └── 2.3 Study Endpoints
├── 3.  STUDY DESIGN
│       └── 3.1 Overall Design
│       └── 3.2 Treatment Arms
│       └── 3.3 Randomization (conditional)
│       └── 3.4 Blinding (conditional)
│       └── 3.5 Stratification Factors (conditional)
├── 4.  SAMPLE SIZE & POWER
│       └── 4.1 Primary Endpoint Sample Size
│       └── 4.2 Assumptions
│       └── 4.3 Power Calculation Details
├── 5.  ANALYSIS POPULATIONS
│       └── 5.1-5.7 ITT, Safety, PP, Response-Evaluable, PK, mITT, Re-treatment
├── 5A. BASELINE CHARACTERISTICS AND DISEASE HISTORY
│       └── 5A.1 Demographics
│       └── 5A.2 Baseline Disease Characteristics
│       └── 5A.3 Prognostic Scores
│       └── 5A.4 Prior Anti-Cancer Therapy
│       └── 5A.5 Medical History
│       └── 5A.6 Prior and Concomitant Medications
├── 6.  ENDPOINTS & ESTIMANDS
│       └── 6.1-6.7 Primary, Secondary, Exploratory, Estimands, Response, Concordance, Retreatment
├── 7.  STATISTICAL METHODS
│       └── 7.1-7.7 General, TTE, Binary, Continuous, Multiplicity, Single-Arm, MRD
├── 8.  CENSORING RULES (conditional: has_tte_endpoints)
│       └── 8.1-8.4 PFS, OS, DOR, EFS censoring
├── 9.  MISSING DATA HANDLING
│       └── 9.1-9.3 Conventions, Date Imputation, Missing Endpoint
├── 10. SENSITIVITY ANALYSES
│       └── 10.1-10.4 Primary Endpoint, Per-Protocol, Tipping Point, COVID-19
├── 11. SUBGROUP ANALYSES
│       └── 11.1-11.3 Pre-specified, Methods, Forest Plots
├── 12. SAFETY ANALYSIS
│       └── 12.1-12.17 AE, Deaths, Labs, Vitals, ECG, Exposure, Subsequent,
│                      CRS, ICANS, Kinetics, Manufacturing, Cytopenias,
│                      B-Cell Aplasia, HRU, Immunogenicity, ADC, Bispecific
├── 13. INTERIM ANALYSIS (conditional: has_interim_analysis)
│       └── 13.1-13.5 Timing, Alpha Spending, Boundaries, Futility, DMC
├── 14. BIOMARKER ANALYSIS (conditional: has_biomarker_endpoints)
│       └── 14.1-14.3 Endpoints, Correlations, Subgroups
├── 15. PATIENT-REPORTED OUTCOMES (conditional: has_pro_endpoints)
│       └── 15.1-15.4 Instruments, Scoring, Missing PRO, Methods
├── 16. DEFINITIONS
│       └── 16.1-16.4 Time Points, Safety Events, Follow-up, Enrollment
├── 17. PROGRAMMING SPECIFICATIONS
│       └── 17.1-17.4 Windows, Baseline, Derived Variables, Cutoff
├── 18. TABLE, FIGURE, AND LISTING SHELLS
│       └── 18.1-18.6 Disposition, Demographics, Efficacy, Safety, Figures, Listings
├── 19. DATA SCREENING AND ACCEPTANCE
│       └── 19.1-19.5 Handling, Transfer, Bias, Outliers, Distributions
├── 20. FOLLOW-UP ANALYSIS (conditional: has_follow_up_analyses)
│       └── 20.1-20.2 Schedule, Objectives
├── 21. CHANGES FROM PROTOCOL-SPECIFIED ANALYSES
│       └── 21.1 Summary of Changes
├── 22. REFERENCES
│       └── 22.1-22.3 Response Criteria, Statistical, Safety Grading
└── A.  APPENDICES
        └── A.1 Date Imputation Algorithm
        └── A.2 Time-to-Event Derivation Rules
        └── A.3 MedDRA Search Strategies
        └── A.4 Response Criteria Reference
        └── A.5 ADaM Dataset Specifications

CONDITION DETECTION (30+ conditions):
├── is_randomized              # Design type check
├── is_single_arm              # Single-arm study
├── is_blinded                 # Blinding status
├── is_adaptive                # Adaptive design
├── has_multiple_arms          # Multi-arm study
├── has_stratification         # Stratification factors
├── has_tte_endpoints          # Time-to-event endpoints
├── has_pfs_endpoint           # PFS primary/secondary
├── has_os_endpoint            # OS primary/secondary
├── has_dor_endpoint           # DOR endpoint
├── has_efs_endpoint           # EFS endpoint
├── has_response_endpoint      # ORR, CR, PR endpoints
├── has_continuous_endpoints   # CFB, PRO endpoints
├── has_exploratory_endpoints  # Exploratory endpoints exist
├── has_multiple_primary       # Co-primary endpoints
├── has_biomarker_endpoints    # Biomarker endpoints
├── has_pro_endpoints          # PRO/QoL endpoints
├── has_pk_endpoints           # PK endpoints
├── is_cart                    # CAR-T therapy
├── is_cart_with_retreatment   # CAR-T with retreatment
├── is_bispecific              # Bispecific antibody
├── is_adc                     # ADC drug
├── is_immunotherapy           # IO drug
├── is_biologic                # Any biologic
├── is_lymphoma                # Lymphoma indication
├── is_hematologic             # Hematologic malignancy
├── is_solid_tumor             # Solid tumor
├── has_interim_analysis       # Interim analysis planned
├── has_mrd_endpoint           # MRD endpoint
├── has_hru_endpoints          # Healthcare utilization
├── has_covid_impact           # COVID-19 era study
├── has_follow_up_analyses     # Long-term follow-up
├── is_phase_2                 # Phase 2 study
└── is_phase_3                 # Phase 3 study

FUNCTIONS:
├── detect_sap_conditions()    # Analyze protocol → conditions dict
├── get_required_sections()    # Filter sections by conditions
├── format_section_outline()   # Format sections as markdown
├── get_all_kb_tools_for_sections()  # Get all tools needed
└── get_section_summary()      # Summary stats
```

---

## KNOWLEDGE BASE FILES

### 4. comprehensive_sap_elements.py (1851 lines)
**Purpose:** Master SAP element definitions for 100% Phase 2/3 coverage

```python
DATA STRUCTURES (35 categories):

Study Framework:
├── STUDY_DEFINITIONS           # Study Day, baseline, TEAE, follow-up definitions
├── ESTIMAND_FRAMEWORK          # ICH E9(R1) estimand specifications
├── BLINDING_CONSIDERATIONS     # Blinding procedures and assessments
└── RANDOMIZATION_SPECS         # Randomization methodology

Baseline & Demographics:
├── DEMOGRAPHICS_BASELINE       # Age, sex, race, ethnicity, weight, BSA, BMI
├── PRIOR_THERAPY_ANALYSIS      # Prior lines, specific agents, refractory status
├── CONCOMITANT_MEDICATIONS     # WHO Drug, ATC classification
├── MEDICAL_HISTORY             # MedDRA SOC/PT coding
└── ORGAN_FUNCTION_SPECS        # Hepatic (Child-Pugh), renal (CrCl), cardiac (LVEF)

Efficacy Analysis:
├── TUMOR_RESPONSE_ASSESSMENT   # RECIST, Lugano, IWCLL, IMWG methodology
├── CONCORDANCE_ANALYSIS        # IRC vs Investigator, kappa statistic
├── MRD_ASSESSMENT              # Minimal residual disease analysis
└── BIOMARKER_SUBGROUPS         # Biomarker-defined subgroups

Safety Analysis:
├── EXPOSURE_ANALYSIS           # Dose, duration, BSA-adjusted, relative intensity
├── AE_PERIOD_ANALYSIS          # TEAE windows, pre-treatment, follow-up
├── DEATH_ANALYSIS              # Death summary, cause, last known alive
├── TREATMENT_COMPLIANCE        # Dose modifications, interruptions
├── IMMUNOGENICITY_ANALYSIS     # ADA incidence, neutralizing Ab, impact
└── HEALTHCARE_UTILIZATION      # Hospitalization, ICU, length of stay

CAR-T Specific:
├── CART_MANUFACTURING_METRICS  # Leukapheresis, vein-to-vein, bridging
├── SUBSEQUENT_THERAPY          # Post-study anti-cancer therapy
└── ENROLLMENT_SUMMARIES        # Enrollment by region, site

Statistical Methods:
├── SENSITIVITY_ANALYSES        # Catalog of sensitivity analyses
├── MULTIPLICITY_ADJUSTMENTS    # Alpha spending, gatekeeping
├── INTERIM_ANALYSIS            # Timing, boundaries, futility
├── SUBGROUP_ANALYSIS_SPECS     # Pre-specified subgroups, forest plots
└── DATA_HANDLING_RULES         # Missing data conventions

PRO & QoL:
├── QOL_PRO_ANALYSIS            # EORTC, FACT, EQ-5D, PGIC analysis
└── PK_PD_ANALYSIS              # PK parameters, exposure-response

Programming:
├── PROTOCOL_DEVIATIONS         # Major/minor classification
├── DATA_CUTOFF_SPECS           # Event-driven cutoff, maturity
├── ANALYSIS_TIMING             # Visit windows, assessment timing
└── STRATIFICATION_BALANCE      # Balance assessment methods

FUNCTIONS:
├── get_comprehensive_sap_elements(study_type)  # Get all for study type
└── get_element_category(category)              # Get specific category
```

---

### 5. methodology_knowledge_base.py (1813 lines)
**Purpose:** Statistical methodology specifications

```python
DATA STRUCTURES (15 categories):

├── STRATIFICATION_SPECIFICATIONS
│   └── CMH test, stratified log-rank, stratified Cox

├── DERIVED_VARIABLE_SPECIFICATIONS
│   └── BSA, BMI, age categories, disease duration

├── TIME_TO_EVENT_ANALYSIS
│   └── Kaplan-Meier, Cox regression, restricted mean, landmark

├── CENSORING_RULES
│   └── PFS censoring (12 circumstances)
│   └── OS censoring (8 circumstances)
│   └── DOR censoring (10 circumstances)
│   └── EFS censoring (8 circumstances)

├── STATISTICAL_METHODS
│   └── kaplan_meier, cox_regression, log_rank, clopper_pearson
│   └── wilson_score, cmh_test, mmrm, ancova

├── CONFIDENCE_INTERVAL_METHODS
│   └── clopper_pearson, wilson, jeffreys, agresti_coull
│   └── wald, exact_binomial

├── MISSING_DATA_HANDLING
│   └── locf, mmrm, multiple_imputation, tipping_point

├── SENSITIVITY_ANALYSES
│   └── Per-protocol, tipping point, MNAR, pattern mixture

├── MULTIPLICITY_ADJUSTMENT
│   └── hochberg, holm, bonferroni, fixed_sequence, gatekeeping

├── SUBGROUP_ANALYSIS_SPECIFICATIONS
│   └── Forest plots, interaction tests, consistency

├── SAFETY_ANALYSIS_SPECIFICATIONS
│   └── AE tables, exposure-adjusted rates, shift tables

├── PRO_QOL_ANALYSIS
│   └── MMRM, time-to-deterioration, responder analysis

├── ANALYSIS_WINDOWS
│   └── Visit windows, baseline definition, post-baseline

├── INTERIM_ANALYSIS_SPECIFICATIONS
│   └── O'Brien-Fleming, Lan-DeMets, Pocock, beta-spending

└── DATA_CUTOFF_SPECIFICATIONS
    └── Event-driven, calendar-based, maturity criteria

FUNCTIONS:
├── export_methodology_knowledge_base()  # Export to JSON
└── count_specifications()               # Count specs by category
```

---

### 6. complete_tfl_inventory.py (1686 lines)
**Purpose:** TFL shell templates

```python
DATA STRUCTURES (10 categories):

├── DISPOSITION_TABLES
│   ├── T-DISP-01: Subject Disposition
│   ├── T-DISP-02: Protocol Deviations
│   └── T-DISP-03: Analysis Sets

├── EFFICACY_TABLES
│   ├── T-EFF-01: Best Overall Response
│   ├── T-EFF-02: Duration of Response
│   ├── T-EFF-03: Progression-Free Survival
│   ├── T-EFF-04: Overall Survival
│   └── T-EFF-05: Time to Response

├── SAFETY_TABLES
│   ├── T-SAF-01: Overview of TEAEs
│   ├── T-SAF-02: TEAEs by SOC/PT
│   ├── T-SAF-03: Grade ≥3 TEAEs
│   ├── T-SAF-04: Serious AEs
│   ├── T-SAF-05: AEs Leading to Discontinuation
│   ├── T-SAF-06: Deaths
│   └── T-SAF-07: Laboratory Abnormalities

├── FIGURES
│   ├── F-EFF-01: Kaplan-Meier PFS
│   ├── F-EFF-02: Kaplan-Meier OS
│   ├── F-EFF-03: Waterfall Plot
│   ├── F-EFF-04: Spider Plot
│   ├── F-EFF-05: Forest Plot (Subgroups)
│   └── F-EFF-06: Swimmer Plot

├── LISTINGS
│   ├── L-DISP-01: Subject Disposition Detail
│   ├── L-SAF-01: Deaths
│   ├── L-SAF-02: Serious AEs
│   └── L-SAF-03: AEs Leading to Discontinuation

├── SINGLE_ARM_DISPOSITION_TABLES
│   └── Phase 2 specific disposition

├── LYMPHOMA_BASELINE_TABLES
│   ├── Ann Arbor Stage
│   ├── IPI Score
│   ├── FLIPI Score
│   └── Bulky Disease

├── LYMPHOMA_EFFICACY_TABLES
│   └── Lugano response tables

├── CAR_T_SAFETY_TABLES
│   ├── CRS Summary by Grade
│   ├── ICANS Summary by Grade
│   ├── Prolonged Cytopenias
│   └── B-Cell Aplasia

└── CAR_T_RETREATMENT_TABLES
    └── Retreatment-specific efficacy

FUNCTIONS:
├── export_tfl_inventory()     # Export all TFL specs
├── get_table_shell()          # Get table by ID
├── get_figure_spec()          # Get figure by ID
├── get_listing_spec()         # Get listing by ID
└── list_all_tfls()            # List all TFL IDs
```

---

### 7. production_sap_specifications.py (1375 lines)
**Purpose:** Production-ready SAP specifications

```python
DATA STRUCTURES (8 categories):

├── TFL_SHELLS
│   └── Complete TFL shell definitions with footnotes

├── ADAM_SPECIFICATIONS
│   └── ADaM dataset variable lists

├── ESTIMANDS_FRAMEWORK
│   └── Treatment policy, composite, hypothetical strategies

├── PROGRAMMING_SPECIFICATIONS
│   └── Programming conventions, validation rules

├── STUDY_DESIGN
│   └── Parallel, crossover, factorial designs

├── RECIST_SPECIFICATIONS
│   └── RECIST 1.1 complete criteria

├── SAFETY_SPECIFICATIONS
│   └── Safety analysis methodology

└── DATA_HANDLING
    └── Data handling conventions

FUNCTIONS:
├── export_production_specs()  # Export all specs
├── get_tfl_shell()            # Get specific TFL
├── get_adam_spec()            # Get ADaM spec
└── list_all_tables()          # List all table IDs
```

---

### 8. oncology_reference_data.py (1265 lines)
**Purpose:** Oncology-specific modules and criteria

```python
DATA STRUCTURES (16 categories):

Response Criteria:
├── IMWG_CRITERIA              # Multiple myeloma response
├── CML_CRITERIA               # CML ELN 2020 criteria
└── IWCLL_CRITERIA             # iwCLL 2018 criteria

Study Templates:
├── ADJUVANT_TRIAL_TEMPLATE    # Adjuvant study design
├── NEOADJUVANT_TRIAL_TEMPLATE # Neoadjuvant design
├── BASKET_TRIAL_TEMPLATE      # Basket trial design
└── UMBRELLA_TRIAL_TEMPLATE    # Umbrella trial design

Therapy Modules:
├── CAR_T_MODULE               # CAR-T specific elements
│   ├── CRS grading (ASTCT, Lee, Penn)
│   ├── ICANS grading
│   ├── Cellular kinetics
│   └── Manufacturing metrics
├── BISPECIFIC_ANTIBODY_MODULE # Bispecific safety
│   ├── Step-up dosing
│   ├── CRS for bispecifics
│   └── Target engagement
└── ADC_MODULE                 # ADC-specific toxicities
    ├── Ocular toxicity
    ├── Peripheral neuropathy
    └── Payload-related AEs

Baseline Variables:
├── BIOMARKER_ENDPOINTS        # Biomarker analysis specs
├── PERFORMANCE_STATUS_SCALES  # ECOG, Karnofsky definitions
├── ORGAN_FUNCTION_SCORES      # Child-Pugh, CrCl, LVEF
└── PROGNOSTIC_SCORES          # IPI, FLIPI, ISS, IMDC

TFL Templates:
├── EFFICACY_TFL_TEMPLATES     # Response tables, survival
└── SAFETY_TFL_TEMPLATES       # AE tables, exposure

FUNCTIONS:
├── get_all_response_criteria()    # All response criteria
├── get_all_study_templates()      # All study designs
├── get_all_therapy_modules()      # CAR-T, bispecific, ADC
├── get_all_biomarker_endpoints()  # Biomarker specs
├── get_all_baseline_variables()   # All baseline vars
└── get_all_tfl_templates()        # All TFL templates
```

---

### 9. disease_specific_criteria.py (679 lines)
**Purpose:** Disease-specific response criteria

```python
DATA STRUCTURES (4 criteria sets):

├── RANO_CRITERIA
│   ├── Complete Response (CR)
│   ├── Partial Response (PR)
│   ├── Stable Disease (SD)
│   ├── Progressive Disease (PD)
│   └── Assessment schedule

├── LUGANO_CRITERIA
│   ├── Complete Metabolic Response (CMR)
│   ├── Partial Metabolic Response (PMR)
│   ├── No Metabolic Response (NMR)
│   ├── Progressive Metabolic Disease (PMD)
│   ├── PET-based assessment
│   └── CT-based assessment

├── IMWG_CRITERIA
│   ├── Stringent CR (sCR)
│   ├── Complete Response (CR)
│   ├── Very Good PR (VGPR)
│   ├── Partial Response (PR)
│   ├── Minimal Response (MR)
│   ├── Stable Disease (SD)
│   ├── Progressive Disease (PD)
│   └── M-protein, FLC, bone marrow criteria

└── RANO_BM_CRITERIA
    └── Brain metastases response criteria

FUNCTIONS:
└── export_disease_criteria()  # Export all criteria
```

---

### 10. adam_specifications.py (668 lines)
**Purpose:** ADaM dataset specifications

```python
DATA STRUCTURES (11 ADaM datasets):

├── ADSL_SPECIFICATION
│   └── Subject-Level Analysis Dataset
│   └── Variables: USUBJID, AGE, SEX, RACE, ARM, SAFFL, ITTFL, etc.

├── ADAE_SPECIFICATION
│   └── Adverse Events Analysis Dataset
│   └── Variables: AETERM, AEDECOD, AEBODSYS, AETOXGR, AEREL, etc.

├── ADTTE_SPECIFICATION
│   └── Time-to-Event Analysis Dataset
│   └── Variables: PARAMCD, AVAL, CNSR, EVNTDESC, STARTDT, ADT, etc.

├── ADRS_SPECIFICATION
│   └── Response Analysis Dataset
│   └── Variables: PARAMCD, AVALC, AVAL, ADT, RSSTRESC, etc.

├── ADLB_SPECIFICATION
│   └── Laboratory Analysis Dataset
│   └── Variables: PARAMCD, AVAL, ANRLO, ANRHI, ATOXGR, etc.

├── ADEX_SPECIFICATION
│   └── Exposure Analysis Dataset
│   └── Variables: PARAMCD, AVAL, EXDOSE, EXDOSU, EXSTDTC, etc.

├── ADVS_SPECIFICATION
│   └── Vital Signs Analysis Dataset
│   └── Variables: PARAMCD, AVAL, ATPT, ABLFL, CHG, etc.

├── ADEG_SPECIFICATION
│   └── ECG Analysis Dataset
│   └── Variables: PARAMCD, AVAL, ATPT, QT, QTcF, etc.

├── ADPR_SPECIFICATION
│   └── PRO Analysis Dataset
│   └── Variables: PARAMCD, AVAL, QSTESTCD, QSCAT, etc.

├── ADCM_SPECIFICATION
│   └── Concomitant Medications Dataset
│   └── Variables: CMTRT, CMDECOD, CMCLAS, CMSTDTC, etc.

└── ADMH_SPECIFICATION
    └── Medical History Dataset
    └── Variables: MHTERM, MHDECOD, MHBODSYS, etc.

FUNCTIONS:
└── export_adam_specifications()  # Export all ADaM specs
```

---

### 11. regulatory_standards.py (691 lines)
**Purpose:** ICH, FDA, EMA regulatory standards

```python
CLASSES:

├── CodingStandards
│   ├── MEDDRA_VERSION = "26.0"
│   ├── WHODRUG_VERSION = "March 2024"
│   └── CTCAE_VERSION = "5.0"

├── TEAESummaryTypes
│   └── Standard TEAE table specifications

├── EstimandFramework
│   └── ICH E9(R1) estimand definitions
│   ├── Treatment policy strategy
│   ├── Composite strategy
│   ├── Hypothetical strategy
│   └── Principal stratum strategy

├── OncologyStandards
│   ├── RECIST 1.1 requirements
│   ├── Lugano 2014 requirements
│   ├── iwCLL 2018 requirements
│   └── IMWG requirements

├── Phase1Standards
│   └── Phase 1 dose-escalation standards

├── LaboratoryStandards
│   └── Lab grading (CTCAE), shift tables

└── RegulatoryKnowledgeBase
    └── Combined regulatory reference

FUNCTIONS:
├── get_regulatory_context()   # Get context for phase/TA
└── get_standard_versions()    # Get all standard versions
```

---

## EXTRACTION & RAG FILES

### 12. claude_extractor.py (1043 lines)
**Purpose:** Protocol extraction using Claude API

```python
CLASSES:
└── ClaudeProtocolExtractor
    ├── extract_protocol()         # Main extraction
    ├── _extract_study_design()    # Design extraction
    ├── _extract_endpoints()       # Endpoint extraction
    ├── _extract_populations()     # Population extraction
    └── _extract_safety()          # Safety extraction
```

### 13. factual_knowledge_graph.py (895 lines)
**Purpose:** Factual knowledge graph construction

```python
CLASSES:
└── FactualKnowledgeGraph
    ├── add_fact()                 # Add fact to graph
    ├── query_facts()              # Query facts
    ├── get_provenance()           # Get fact sources
    └── export_graph()             # Export to JSON
```

### 14. sap_knowledge_graph.py (845 lines)
**Purpose:** SAP-specific knowledge graph

```python
CLASSES:
└── SAPKnowledgeGraph
    ├── add_sap_element()          # Add SAP element
    ├── link_to_protocol()         # Link to protocol facts
    └── generate_section()         # Generate SAP section
```

### 15. graph_rag.py (802 lines)
**Purpose:** RAG retrieval from knowledge graphs

```python
CLASSES:
└── GraphRAG
    ├── retrieve()                 # Retrieve relevant context
    ├── rank_results()             # Rank by relevance
    └── format_context()           # Format for Claude
```

### 16. protocol_specific_extractor.py (702 lines)
**Purpose:** Protocol-specific element extraction

```python
CLASSES:
└── ProtocolSpecificExtractor
    ├── extract_cart_elements()    # CAR-T specific
    ├── extract_biomarker_elements()  # Biomarker specific
    └── extract_design_elements()  # Design specific
```

---

## IMPORT CHAIN

```
main.py
└── kg_enhanced_pipeline.py
    │
    ├── kb_tools.py (83 tools)
    │   ├── methodology_knowledge_base.py
    │   │   └── STATISTICAL_METHODS, CENSORING_RULES, etc.
    │   │
    │   ├── complete_tfl_inventory.py
    │   │   └── DISPOSITION_TABLES, EFFICACY_TABLES, etc.
    │   │
    │   ├── production_sap_specifications.py
    │   │   └── TFL_SHELLS, ADAM_SPECIFICATIONS, etc.
    │   │
    │   ├── adam_specifications.py
    │   │   └── ADSL, ADAE, ADTTE, etc.
    │   │
    │   ├── disease_specific_criteria.py
    │   │   └── RANO, LUGANO, IMWG, etc.
    │   │
    │   ├── oncology_reference_data.py
    │   │   └── CAR_T_MODULE, BISPECIFIC_MODULE, etc.
    │   │
    │   └── comprehensive_sap_elements.py
    │       └── 35 SAP element categories
    │
    ├── sap_structure_config.py
    │   └── MASTER_SAP_SECTIONS (24 sections)
    │   └── detect_sap_conditions() (30+ conditions)
    │
    └── regulatory_standards.py
        └── CodingStandards, EstimandFramework, etc.
```

---

## STATISTICS

| Category | Files | Lines |
|----------|-------|-------|
| Core Pipeline | 3 | 8,194 |
| Knowledge Bases | 8 | 11,028 |
| Extraction & RAG | 5 | 4,287 |
| Utilities | 4 | 1,689 |
| Tests | 6 | 1,688 |
| **TOTAL** | **26** | **25,886** |

| KB Tools | Count |
|----------|-------|
| Statistical Methods | 15 |
| Population & Baseline | 10 |
| Endpoint & Response | 12 |
| Safety Analysis | 12 |
| TFL Templates | 12 |
| Therapy-Specific | 6 |
| Data & Programming | 10 |
| Study Design & References | 6 |
| **TOTAL TOOLS** | **83** |
