"""
Configuration for SAP validation and contamination detection.

This file contains configurable values that were previously hardcoded,
making it easier to update without modifying core logic.
"""

# Known drug names from other studies that indicate contamination
# Format: drug_name -> source study description
KNOWN_CONTAMINANTS = {
    'etrolizumab': 'Roche UC study (HICKORY, LAUREL)',
    'vedolizumab': 'Entyvio UC/CD studies',
    'ustekinumab': 'Stelara UC/CD studies',
    'adalimumab': 'Humira UC/CD studies',
    'infliximab': 'Remicade UC/CD studies',
    'tofacitinib': 'Xeljanz UC study',
    'ozanimod': 'Zeposia UC study',
    'filgotinib': 'Jyseleca UC study',
    'risankizumab': 'Skyrizi CD study',
    'mirikizumab': 'Omvoh UC study',
    'golimumab': 'Simponi UC study',
}

# Required SAP sections for validation
# Format: section_key -> (header_patterns, content_patterns)
# header_patterns: regex patterns to find section header
# content_patterns: regex patterns to verify section has content
REQUIRED_SAP_SECTIONS = {
    'Introduction': (
        [r'#+\s*\d*\.?\s*introduction', r'\bintroduction\b'],
        [r'statistical\s+analysis\s+plan', r'SAP\s+describes', r'study\s+overview']
    ),
    'Objectives': (
        [r'#+\s*\d*\.?\s*(?:study\s+)?objectives?', r'#+\s*\d*\.?\s*estimands?'],
        [r'primary\s+objective', r'estimand', r'treatment\s+effect']
    ),
    'Study Design': (
        [r'#+\s*\d*\.?\s*study\s+design'],
        [r'randomized', r'placebo', r'double[- ]blind', r'treatment\s+arms?']
    ),
    'Analysis Populations': (
        [r'#+\s*\d*\.?\s*(?:analysis\s+)?populations?'],
        [r'ITT|intent[- ]to[- ]treat', r'FAS|full\s+analysis', r'PP|per[- ]protocol', r'safety\s+population']
    ),
    'Endpoints': (
        [r'#+\s*\d*\.?\s*endpoints?', r'#+\s*\d*\.?\s*efficacy\s+endpoints?'],
        [r'primary\s+endpoint', r'secondary\s+endpoint', r'outcome']
    ),
    'Sample Size': (
        [r'#+\s*\d*\.?\s*sample\s+size'],
        [r'power', r'alpha', r'patients?', r'subjects?']
    ),
    'Statistical Methods': (
        [r'#+\s*\d*\.?\s*statistical\s+(?:methods?|analysis)'],
        [r'logistic', r'regression', r'ANCOVA', r'MMRM', r'analysis']
    ),
    'Missing Data': (
        [r'#+\s*\d*\.?\s*missing\s+data', r'#+\s*\d*\.?\s*data\s+handling'],
        [r'imputation', r'missing', r'sensitivity', r'LOCF', r'NRI']
    ),
    'Safety': (
        [r'#+\s*\d*\.?\s*safety'],
        [r'adverse\s+event', r'AE', r'TEAE', r'SAE', r'MedDRA']
    ),
}

# Section order for SAP assembly
SAP_SECTION_ORDER = [
    '1_introduction',
    '2_objectives_estimands',
    '3_study_design',
    'study_design',  # Legacy key
    '4_analysis_populations',
    '5_endpoints',
    '6_sample_size',
    'sample_size',  # Legacy key
    '7_statistical_methods',
    '8_missing_data',
    '9_safety_analysis',
    '10_pk_analysis',
]

# Critical facts that must be extracted (non-None) for valid SAP generation
CRITICAL_EXTRACTION_FIELDS = [
    'nct_id',
    'drug_name',
    'num_arms',
    'total_n',
    'primary_endpoint',
    'primary_timepoint',
    'alpha',
    'alpha_sidedness',
    'primary_analysis_method',
]

# Default values to use when extraction fails
DEFAULT_VALUES = {
    'power': '80%',
    'alpha': 0.05,
    'alpha_sidedness': 'one-sided',  # Changed from two-sided
    'num_arms': 2,
    'ratio': '1:1',
    'primary_timepoint': 'Week 12',
    'primary_population': 'FAS',
    'route': 'intravenous',
}

# PK analysis parameters for non-compartmental analysis
PK_PARAMETERS = {
    'AUCinf': 'Area under the concentration-time curve from time 0 extrapolated to infinity',
    'AUClast': 'Area under the concentration-time curve from time 0 to last measurable concentration',
    'AUCτ': 'Area under the concentration-time curve over dosing interval',
    'Cmax': 'Maximum observed plasma concentration',
    'tmax': 'Time to maximum plasma concentration',
    'CL': 'Total body clearance',
    'Vz': 'Volume of distribution during terminal phase',
    'λz': 'Terminal elimination rate constant',
    't½': 'Terminal elimination half-life',
    'MRT': 'Mean residence time',
    '%ExtrapAUC': 'Percentage of AUCinf extrapolated beyond last measurable concentration',
}

# Biomarkers commonly assessed in clinical trials
COMMON_BIOMARKERS = [
    'ESR',
    'CRP',
    'IL-6',
    'IL-6/sIL-6R',
    'fecal calprotectin',
    'neutrophil count',
    'platelet count',
]

# Default subgroup analysis factors
DEFAULT_SUBGROUP_FACTORS = [
    'Age group (<65, ≥65 years)',
    'Sex',
    'Geographic region',
    'Baseline disease severity',
    'Prior treatment history',
    'Baseline IL-6/sIL-6R complex levels',
]

# Visit window definitions (default)
DEFAULT_VISIT_WINDOWS = {
    'Week 4': 'Day 28 ± 2 days',
    'Week 6': 'Day 42 ± 2 days',
    'Week 8': 'Day 56 ± 2 days',
    'Week 10': 'Day 70 ± 3 days',
    'Week 12': 'Day 84 ± 3 days',
}
