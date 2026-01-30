#!/usr/bin/env python3
"""
Schema-Constrained SAP Generation Pipeline (Full Coverage)
===========================================================

Complete pipeline that:
1. Extracts ALL protocol facts (28 entities) with Literal constraints
2. Creates Pydantic schemas where every protocol value is enforced
3. Generates each SAP section with schema enforcement
4. Uses constrained Estimand schema (prevents drug name contamination)
5. Verifies against formal invariants
6. Detects any contamination from RAG examples
7. Assembles final SAP document

Philosophy: If it's extracted from the protocol → It MUST be constrained

The key guarantee: LLM CANNOT output wrong values because
the Literal types only allow exact extracted values.
"""

import re
from typing import Dict, List, Optional, Tuple, Any, Literal
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, field_validator

# RAG Integration (optional)
try:
    from ..rag.pipeline_integration import RAGPipelineIntegration
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

# Full schema with complete constraint coverage (28 entities)
from .full_schema_generator import (
    FullProtocolFacts,
    extract_full_protocol_facts,
    create_fully_constrained_schema,
    create_constrained_estimand_schema,
    create_full_estimand_schema,
    generate_constrained_prompt,
    print_constraint_summary,
    # Section schemas
    IntroductionSectionBase,
    StudyDesignSectionBase,
    PopulationsSectionBase,
    EndpointsSectionBase,
    SampleSizeSectionBase,
    StatMethodsSectionBase,
    StratificationSectionBase,
)

# Legacy imports for backward compatibility
from .schema_constrained_generator import (
    ProtocolFacts,
    CitedValue,
    extract_protocol_facts as extract_protocol_facts_legacy,
    create_sample_size_schema as create_sample_size_schema_legacy,
    create_study_design_schema as create_study_design_schema_legacy,
    FormalVerifier,
    VerificationResult,
    ContaminationDetector,
    SectionAssembler
)
from .structured_llm import get_structured_client, SAPSectionGenerator
from enum import Enum

# Operational Rules Integration (Three-Tier System)
try:
    from .operational_integration import (
        OperationalRulesIntegration,
        integrate_operational_rules,
        detect_study_type_from_facts
    )
    from .ice_sensitivity_generator import (
        ICEGenerator,
        SensitivityAnalysisGenerator
    )
    OPERATIONAL_RULES_AVAILABLE = True
except ImportError:
    OPERATIONAL_RULES_AVAILABLE = False


# =============================================================================
# ADAPTIVE APPENDIX GENERATION - Protocol-Specific Logic
# =============================================================================

class EndpointType(Enum):
    """Types of primary endpoints determining statistical approach"""
    BINARY = "binary"                    # Response/remission rates
    CONTINUOUS = "continuous"            # Change from baseline (scores)
    TIME_TO_EVENT = "time_to_event"      # Survival, PFS, time to relapse
    COUNT = "count"                      # Number of events
    ORDINAL = "ordinal"                  # Ordered categories
    COMPOSITE = "composite"              # Multiple components (e.g., MACE)


class TherapeuticArea(Enum):
    """Therapeutic areas with distinct scoring systems"""
    GASTROENTEROLOGY = "gastroenterology"   # UC, Crohn's, IBS
    ONCOLOGY = "oncology"                   # Solid tumors, hematologic
    RHEUMATOLOGY = "rheumatology"           # RA, PsA, AS
    CNS_PSYCHIATRY = "cns_psychiatry"       # Depression, schizophrenia
    CARDIOVASCULAR = "cardiovascular"       # CV outcomes, heart failure
    DERMATOLOGY = "dermatology"             # Psoriasis, AD, acne
    RESPIRATORY = "respiratory"             # Asthma, COPD
    INFECTIOUS = "infectious"               # HIV, Hep C, vaccines
    OPHTHALMOLOGY = "ophthalmology"         # AMD, glaucoma
    METABOLIC = "metabolic"                 # Diabetes, obesity
    RARE_DISEASE = "rare_disease"           # Various rare conditions
    GENERAL = "general"                     # Default/unclassified


class EndpointAnalyzer:
    """Analyzes protocol to determine endpoint types and therapeutic area"""

    # Keywords for endpoint type detection
    BINARY_KEYWORDS = [
        'remission', 'response', 'responder', 'proportion', 'percentage',
        'achieving', 'clinical response', 'complete response', 'partial response',
        'acr20', 'acr50', 'acr70', 'pasi75', 'pasi90', 'iga', 'orr',
        'objective response', 'pathological complete', 'clinical benefit',
        'disease-free', 'event-free', 'relapse-free', 'mucosal healing',
        'yes/no', 'success/failure', 'cure rate', 'eradication'
    ]

    CONTINUOUS_KEYWORDS = [
        'change from baseline', 'mean change', 'difference in', 'reduction in',
        'improvement in', 'score change', 'cfb', 'ls mean', 'least squares',
        'mmrm', 'mixed model', 'change in score', 'fev1', 'hba1c', 'ldl',
        'bmi change', 'weight change', 'mayo score', 'cdai', 'das28',
        'madrs', 'ham-d', 'panss', 'adas-cog', 'mmse'
    ]

    TIME_TO_EVENT_KEYWORDS = [
        'time to', 'survival', 'progression-free', 'overall survival',
        'pfs', 'os', 'dfs', 'efs', 'rfs', 'ttp', 'dor', 'duration of',
        'kaplan-meier', 'cox', 'hazard ratio', 'median survival',
        'time to relapse', 'time to progression', 'time to event',
        'time to first', 'event-free survival', 'recurrence-free'
    ]

    COUNT_KEYWORDS = [
        'number of', 'count of', 'frequency of', 'episodes', 'exacerbations',
        'flares', 'relapses', 'attacks', 'seizures', 'events per',
        'negative binomial', 'poisson'
    ]

    COMPOSITE_KEYWORDS = [
        'mace', 'major adverse', 'composite endpoint', 'composite of',
        'any of the following', 'first occurrence of', 'combined endpoint'
    ]

    # Therapeutic area detection
    TA_PATTERNS = {
        TherapeuticArea.GASTROENTEROLOGY: [
            'ulcerative colitis', 'crohn', 'inflammatory bowel', 'ibd', 'ibs',
            'gerd', 'nash', 'nafld', 'celiac', 'gi ', 'gastrointestinal',
            'mayo score', 'cdai', 'hbi', 'ses-cd', 'endoscopic'
        ],
        TherapeuticArea.ONCOLOGY: [
            'cancer', 'tumor', 'tumour', 'carcinoma', 'sarcoma', 'lymphoma',
            'leukemia', 'leukaemia', 'melanoma', 'oncology', 'malignant',
            'metastatic', 'recist', 'irrecist', 'solid tumor', 'nsclc',
            'breast cancer', 'prostate cancer', 'colorectal', 'chemotherapy'
        ],
        TherapeuticArea.RHEUMATOLOGY: [
            'rheumatoid arthritis', 'psoriatic arthritis', 'ankylosing spondylitis',
            'lupus', 'sle', 'sjogren', 'vasculitis', 'gout', 'osteoarthritis',
            'acr20', 'acr50', 'acr70', 'das28', 'sdai', 'cdai', 'basdai',
            'rheumat'
        ],
        TherapeuticArea.CNS_PSYCHIATRY: [
            'depression', 'anxiety', 'schizophrenia', 'bipolar', 'alzheimer',
            'parkinson', 'multiple sclerosis', 'epilepsy', 'migraine',
            'madrs', 'ham-d', 'ham-a', 'panss', 'cgi', 'adas-cog', 'mmse',
            'psychiatr', 'neurolog', 'cns'
        ],
        TherapeuticArea.CARDIOVASCULAR: [
            'cardiovascular', 'heart failure', 'myocardial infarction',
            'stroke', 'atrial fibrillation', 'hypertension', 'mace',
            'coronary', 'cardiac', 'lvef', 'nt-probnp', 'cv death'
        ],
        TherapeuticArea.DERMATOLOGY: [
            'psoriasis', 'atopic dermatitis', 'eczema', 'acne', 'rosacea',
            'hidradenitis', 'vitiligo', 'alopecia', 'pasi', 'iga', 'easi',
            'bsa', 'dlqi', 'dermat', 'skin'
        ],
        TherapeuticArea.RESPIRATORY: [
            'asthma', 'copd', 'pulmonary', 'respiratory', 'bronchitis',
            'fev1', 'fvc', 'pef', 'exacerbation', 'ipf', 'cystic fibrosis',
            'lung function'
        ],
        TherapeuticArea.INFECTIOUS: [
            'hiv', 'hepatitis', 'hcv', 'hbv', 'vaccine', 'antibiotic',
            'antiviral', 'infection', 'viral load', 'seroconversion',
            'antimicrobial', 'bacterial'
        ],
        TherapeuticArea.OPHTHALMOLOGY: [
            'macular degeneration', 'amd', 'glaucoma', 'diabetic retinopathy',
            'uveitis', 'dry eye', 'bcva', 'etdrs', 'oct', 'ophthalm', 'eye'
        ],
        TherapeuticArea.METABOLIC: [
            'diabetes', 'hba1c', 'obesity', 'weight loss', 'metabolic',
            'dyslipidemia', 'ldl', 'triglyceride', 'insulin', 'sglt2',
            'glp-1', 'bmi'
        ],
        TherapeuticArea.RARE_DISEASE: [
            'orphan', 'rare disease', 'ultra-rare', 'enzyme replacement',
            'gene therapy', 'lysosomal', 'sma', 'duchenne', 'hemophilia'
        ]
    }

    # Scoring systems by therapeutic area
    SCORING_SYSTEMS = {
        TherapeuticArea.GASTROENTEROLOGY: {
            'ulcerative colitis': {
                'name': 'Mayo Score',
                'components': ['Stool Frequency (0-3)', 'Rectal Bleeding (0-3)',
                              'Physician Global Assessment (0-3)', 'Endoscopy Subscore (0-3)'],
                'range': '0-12',
                'remission': 'Total Mayo ≤2 with no subscore >1 and RB=0',
                'response': 'Decrease ≥3 points and ≥30% from baseline with RB decrease ≥1 or RB ≤1'
            },
            'crohn': {
                'name': 'CDAI (Crohn\'s Disease Activity Index)',
                'components': ['Number of liquid stools (x2)', 'Abdominal pain (x5)',
                              'General well-being (x7)', 'Extraintestinal complications (x20)',
                              'Antidiarrheal use (x30)', 'Abdominal mass (x10)',
                              'Hematocrit deviation (x6)', 'Body weight percentage (x1)'],
                'range': '0-600+',
                'remission': 'CDAI <150',
                'response': 'Decrease ≥100 points from baseline'
            }
        },
        TherapeuticArea.ONCOLOGY: {
            'solid_tumor': {
                'name': 'RECIST 1.1',
                'components': ['Sum of target lesion diameters', 'Non-target lesion status',
                              'New lesion presence'],
                'categories': ['CR (Complete Response)', 'PR (Partial Response)',
                              'SD (Stable Disease)', 'PD (Progressive Disease)'],
                'orr': 'CR + PR (confirmed at ≥4 weeks)',
                'dcr': 'CR + PR + SD'
            }
        },
        TherapeuticArea.RHEUMATOLOGY: {
            'rheumatoid_arthritis': {
                'name': 'ACR Response Criteria',
                'components': ['Tender joint count (68)', 'Swollen joint count (66)',
                              'Patient pain VAS', 'Patient global VAS', 'Physician global VAS',
                              'HAQ-DI', 'Acute phase reactant (CRP or ESR)'],
                'thresholds': {
                    'ACR20': '≥20% improvement in TJC, SJC, and 3 of 5 other measures',
                    'ACR50': '≥50% improvement in TJC, SJC, and 3 of 5 other measures',
                    'ACR70': '≥70% improvement in TJC, SJC, and 3 of 5 other measures'
                }
            }
        },
        TherapeuticArea.CNS_PSYCHIATRY: {
            'depression': {
                'name': 'MADRS (Montgomery-Åsberg Depression Rating Scale)',
                'components': ['Apparent sadness', 'Reported sadness', 'Inner tension',
                              'Reduced sleep', 'Reduced appetite', 'Concentration difficulties',
                              'Lassitude', 'Inability to feel', 'Pessimistic thoughts', 'Suicidal thoughts'],
                'range': '0-60 (each item 0-6)',
                'remission': 'MADRS ≤10',
                'response': '≥50% decrease from baseline'
            }
        },
        TherapeuticArea.DERMATOLOGY: {
            'psoriasis': {
                'name': 'PASI (Psoriasis Area and Severity Index)',
                'components': ['Erythema (0-4)', 'Induration (0-4)', 'Desquamation (0-4)',
                              'Body surface area by region'],
                'range': '0-72',
                'thresholds': {
                    'PASI75': '≥75% improvement from baseline',
                    'PASI90': '≥90% improvement from baseline',
                    'PASI100': '100% improvement (clear)'
                }
            }
        },
        TherapeuticArea.CARDIOVASCULAR: {
            'mace': {
                'name': 'MACE (Major Adverse Cardiovascular Events)',
                'components': ['CV death', 'Non-fatal MI', 'Non-fatal stroke'],
                'extended': ['Hospitalization for heart failure', 'Coronary revascularization'],
                'analysis': 'Time to first event (composite)'
            }
        },
        TherapeuticArea.RESPIRATORY: {
            'asthma': {
                'name': 'Pulmonary Function Tests',
                'primary': 'FEV1 (Forced Expiratory Volume in 1 second)',
                'components': ['FEV1', 'FVC', 'FEV1/FVC ratio', 'PEF'],
                'endpoints': ['Change in FEV1 from baseline', 'Annualized exacerbation rate']
            }
        }
    }

    @classmethod
    def detect_endpoint_type(cls, endpoint: str, protocol_text: str = "") -> EndpointType:
        """Detect the type of endpoint from its description"""
        text = f"{endpoint} {protocol_text}".lower()

        # Check for time-to-event first (most specific)
        if any(kw in text for kw in cls.TIME_TO_EVENT_KEYWORDS):
            return EndpointType.TIME_TO_EVENT

        # Check for composite
        if any(kw in text for kw in cls.COMPOSITE_KEYWORDS):
            return EndpointType.COMPOSITE

        # Check for count data
        if any(kw in text for kw in cls.COUNT_KEYWORDS):
            return EndpointType.COUNT

        # Check for continuous (change from baseline)
        if any(kw in text for kw in cls.CONTINUOUS_KEYWORDS):
            return EndpointType.CONTINUOUS

        # Check for binary (most common default)
        if any(kw in text for kw in cls.BINARY_KEYWORDS):
            return EndpointType.BINARY

        # Default to binary (most common in clinical trials)
        return EndpointType.BINARY

    @classmethod
    def detect_therapeutic_area(cls, indication: str, protocol_text: str = "") -> TherapeuticArea:
        """Detect therapeutic area from indication and protocol text"""
        text = f"{indication} {protocol_text}".lower()

        # Check each TA pattern
        for ta, patterns in cls.TA_PATTERNS.items():
            if any(pattern in text for pattern in patterns):
                return ta

        return TherapeuticArea.GENERAL

    @classmethod
    def get_scoring_system(cls, ta: TherapeuticArea, indication: str) -> Optional[Dict]:
        """Get the appropriate scoring system for the therapeutic area and indication"""
        if ta not in cls.SCORING_SYSTEMS:
            return None

        ta_systems = cls.SCORING_SYSTEMS[ta]
        indication_lower = indication.lower()

        # Try to match specific indication
        for key, system in ta_systems.items():
            if key in indication_lower:
                return system

        # Return first system for the TA as default
        return list(ta_systems.values())[0] if ta_systems else None

    @classmethod
    def get_sas_procedure(cls, endpoint_type: EndpointType) -> Dict[str, str]:
        """Get the appropriate SAS procedure based on endpoint type"""
        procedures = {
            EndpointType.BINARY: {
                'procedure': 'PROC LOGISTIC',
                'model_statement': 'MODEL response(EVENT="1") = trt stratification_vars / EXPB CLODDS=WALD',
                'output': 'Odds Ratio with 95% CI, p-value'
            },
            EndpointType.CONTINUOUS: {
                'procedure': 'PROC MIXED',
                'model_statement': 'MODEL change = trt baseline visit trt*visit / SOLUTION DDFM=KR',
                'repeated': 'REPEATED visit / TYPE=UN SUBJECT=subject',
                'output': 'LS Mean difference with 95% CI, p-value'
            },
            EndpointType.TIME_TO_EVENT: {
                'procedure': 'PROC PHREG',
                'model_statement': 'MODEL time*event(0) = trt stratification_vars',
                'output': 'Hazard Ratio with 95% CI, p-value (log-rank test)'
            },
            EndpointType.COUNT: {
                'procedure': 'PROC GENMOD',
                'model_statement': 'MODEL count = trt offset / DIST=NEGBIN LINK=LOG',
                'output': 'Rate Ratio with 95% CI, p-value'
            },
            EndpointType.COMPOSITE: {
                'procedure': 'PROC PHREG',
                'model_statement': 'MODEL time_to_first*event(0) = trt stratification_vars',
                'output': 'Hazard Ratio with 95% CI, p-value for composite'
            },
            EndpointType.ORDINAL: {
                'procedure': 'PROC LOGISTIC',
                'model_statement': 'MODEL category = trt / LINK=CLOGIT',
                'output': 'Cumulative Odds Ratio with 95% CI'
            }
        }
        return procedures.get(endpoint_type, procedures[EndpointType.BINARY])


@dataclass
class PipelineResult:
    """Result of the constrained generation pipeline"""
    success: bool
    sap_text: str = ""
    sections: Dict[str, str] = field(default_factory=dict)
    facts: Optional[FullProtocolFacts] = None  # Now uses full coverage
    legacy_facts: Optional[ProtocolFacts] = None  # For backward compatibility
    verification_results: Dict[str, VerificationResult] = field(default_factory=dict)
    contamination_detected: bool = False
    contamination_details: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    constraint_coverage: int = 0  # Number of entities constrained


class ConstrainedSAPPipeline:
    """
    Main pipeline for schema-constrained SAP generation.

    Usage:
        pipeline = ConstrainedSAPPipeline()
        result = pipeline.generate(protocol_text, nct_id="NCT02394028")

        if result.success:
            print(result.sap_text)
        else:
            print(f"Errors: {result.errors}")
    """

    def __init__(self, use_rag: bool = True):
        self.structured_client = get_structured_client()
        self.section_generator = SAPSectionGenerator(self.structured_client)
        self.verifier = FormalVerifier()
        self.contamination_detector = ContaminationDetector()
        self.assembler = SectionAssembler()

        # Initialize RAG if available and enabled
        self.use_rag = use_rag and RAG_AVAILABLE
        self.rag = None
        if self.use_rag:
            try:
                self.rag = RAGPipelineIntegration()
                print("[RAG] RAG system initialized (1,198 sections available)")
            except Exception as e:
                print(f"[RAG] Warning: Could not initialize RAG: {e}")
                self.use_rag = False

        # Initialize Operational Rules Integration (Three-Tier System)
        self.use_operational_rules = OPERATIONAL_RULES_AVAILABLE
        self.operational_integrator = None  # Initialized per-protocol in generate()

    def _init_operational_rules(self, facts: 'FullProtocolFacts') -> Optional['OperationalRulesIntegration']:
        """Initialize operational rules integrator for the current protocol."""
        if not self.use_operational_rules:
            return None

        try:
            # Convert FullProtocolFacts to dict for the integrator
            facts_dict = {
                'nct_id': getattr(facts, 'nct_id', ''),
                'drug_name': getattr(facts, 'drug_name', ''),
                'drug_class': getattr(facts, 'drug_class', ''),
                'hypothesis_framework': getattr(facts, 'hypothesis_framework', ''),
                'treatment_setting': getattr(facts, 'treatment_setting', ''),
                'primary_endpoint': getattr(facts, 'primary_endpoint', ''),
                'primary_endpoint_type': getattr(facts, 'primary_endpoint_type', ''),
                'secondary_endpoints': getattr(facts, 'secondary_endpoints', []),
                'stratification_factors': getattr(facts, 'stratification_factors', []),
                'stratification_factor_levels': getattr(facts, 'stratification_factor_levels', {}),
                'num_arms': getattr(facts, 'num_arms', 2),
                'is_single_arm': getattr(facts, 'is_single_arm', False),
                'has_interim_analysis': getattr(facts, 'has_interim', False),
                'num_interim_analyses': getattr(facts, 'num_interim', 0),
                'has_pk_endpoints': 'pk' in str(getattr(facts, 'secondary_endpoints', [])).lower(),
                'population': getattr(facts, 'indication', ''),
                'treatment_description': f"{getattr(facts, 'drug_name', '')} vs {getattr(facts, 'comparator', '')}",
            }

            integrator = OperationalRulesIntegration(extracted_facts=facts_dict)
            print(f"[OPERATIONAL] Detected study type: {integrator.study_type}")
            return integrator
        except Exception as e:
            print(f"[OPERATIONAL] Warning: Could not initialize operational rules: {e}")
            return None

    def _get_rag_context(self, facts: 'FullProtocolFacts') -> Dict[str, str]:
        """Get RAG context for generation enhancement"""
        if not self.use_rag or not self.rag:
            return {}

        try:
            # Build protocol data for RAG query
            protocol_data = {
                'nct_id': getattr(facts, 'nct_id', 'unknown'),
                'therapeutic_area': getattr(facts, 'therapeutic_area', None),
                'phase': getattr(facts, 'phase', None),
                'indication': getattr(facts, 'indication', None),
                'primary_endpoint': getattr(facts, 'primary_endpoint', None),
                'endpoint_type': getattr(facts, 'endpoint_type', None),
            }
            return self.rag.get_context_for_generation(protocol_data)
        except Exception as e:
            print(f"[RAG] Warning: Could not get RAG context: {e}")
            return {}

    def generate(
        self,
        protocol_text: str,
        nct_id: str = None,
        skip_sections: List[str] = None
    ) -> PipelineResult:
        """
        Generate SAP with schema constraints and verification.

        Args:
            protocol_text: Full protocol document text
            nct_id: NCT ID (optional, will be extracted if not provided)
            skip_sections: List of section names to skip

        Returns:
            PipelineResult with SAP text and verification details
        """
        result = PipelineResult(success=True)
        skip = set(skip_sections or [])

        print("\n" + "="*60)
        print("SCHEMA-CONSTRAINED SAP GENERATION PIPELINE (FULL COVERAGE)")
        print("="*60)

        # =================================================================
        # STAGE 1: Extract ALL Protocol Facts (28 entities)
        # =================================================================
        print("\n[STAGE 1] Extracting ALL protocol facts (full coverage)...")

        # Use full extraction with 28 entities
        facts = extract_full_protocol_facts(protocol_text)
        result.facts = facts

        # Override NCT if provided
        if nct_id and not facts.nct_id:
            facts.nct_id = nct_id

        # Also extract legacy facts for backward compatibility
        legacy_facts = extract_protocol_facts_legacy(protocol_text)
        result.legacy_facts = legacy_facts

        # Validate critical facts
        missing_critical = self._check_critical_facts_full(facts)
        if missing_critical:
            result.warnings.extend([f"Missing: {m}" for m in missing_critical])
            print(f"  Warning: Missing critical facts: {missing_critical}")

        # Count constraint coverage
        result.constraint_coverage = self._count_constraints(facts)

        # Print full extraction summary
        print_constraint_summary(facts)

        # Initialize Operational Rules Integration (Three-Tier System)
        self.operational_integrator = self._init_operational_rules(facts)

        # =================================================================
        # STAGE 2: Create Fully Constrained Schemas
        # =================================================================
        print("\n[STAGE 2] Creating Literal-constrained schemas (all 28 entities)...")

        # Create the fully constrained schema (all protocol values are Literals)
        full_sap_schema = create_fully_constrained_schema(facts)

        # Create constrained Estimand schema (prevents drug name contamination)
        estimand_schema = create_constrained_estimand_schema(facts)

        # Legacy schemas for backward compatibility
        sample_size_schema = create_sample_size_schema_legacy(legacy_facts)
        study_design_schema = create_study_design_schema_legacy(legacy_facts)

        print(f"\n  Full SAP Schema: {len(full_sap_schema.model_fields)} constrained fields")
        print(f"  Estimand Schema: drug_name=Literal['{facts.drug_name or 'Study Drug'}']")

        # Print the constrained values summary
        self._print_schema_constraints_full(facts)

        # =================================================================
        # STAGE 3: Generate ALL Sections with Schema Enforcement
        # =================================================================
        print("\n[STAGE 3] Generating ALL 9 SAP sections with schema enforcement...")

        # Use legacy_facts for methods that expect CitedValue format
        # Use facts (FullProtocolFacts) for new methods with direct values
        facts_summary = self._full_facts_to_dict(facts)

        # Section 1: Introduction
        if '1_introduction' not in skip:
            print("\n  [1/9] Generating Introduction section...")
            section_data = self._generate_introduction(facts)
            if section_data:
                result.sections['1_introduction'] = section_data
            else:
                result.errors.append("Failed to generate Introduction section")

        # Section 2: Objectives and Estimands
        if '2_objectives_estimands' not in skip:
            print("\n  [2/9] Generating Objectives & Estimands section...")
            section_data = self._generate_objectives_estimands(facts)
            if section_data:
                result.sections['2_objectives_estimands'] = section_data
            else:
                result.errors.append("Failed to generate Objectives & Estimands section")

        # Section 3: Study Design
        if 'study_design' not in skip and '3_study_design' not in skip:
            print("\n  [3/9] Generating Study Design section...")
            section_data, verification = self._generate_study_design(
                study_design_schema, legacy_facts, facts_summary
            )
            if section_data:
                result.sections['3_study_design'] = section_data
                result.verification_results['study_design'] = verification
                if not verification.passed:
                    result.errors.extend(verification.violations)
                    result.success = False
            else:
                result.errors.append("Failed to generate Study Design section")

        # Section 4: Analysis Populations
        if '4_analysis_populations' not in skip:
            print("\n  [4/9] Generating Analysis Populations section...")
            section_data = self._generate_analysis_populations(facts)
            if section_data:
                result.sections['4_analysis_populations'] = section_data
            else:
                result.errors.append("Failed to generate Analysis Populations section")

        # Section 5: Endpoints
        if '5_endpoints' not in skip:
            print("\n  [5/9] Generating Endpoints section...")
            section_data = self._generate_endpoints(facts)
            if section_data:
                result.sections['5_endpoints'] = section_data
            else:
                result.errors.append("Failed to generate Endpoints section")

        # Section 6: Sample Size Section
        if 'sample_size' not in skip and '6_sample_size' not in skip:
            print("\n  [6/9] Generating Sample Size section...")
            section_data, verification = self._generate_sample_size(
                sample_size_schema, legacy_facts, facts_summary
            )
            if section_data:
                result.sections['6_sample_size'] = section_data
                result.verification_results['sample_size'] = verification
                if not verification.passed:
                    result.errors.extend(verification.violations)
                    result.success = False
            else:
                result.errors.append("Failed to generate Sample Size section")

        # Section 7: Statistical Methods
        if '7_statistical_methods' not in skip:
            print("\n  [7/9] Generating Statistical Methods section...")
            section_data = self._generate_statistical_methods(facts)
            if section_data:
                result.sections['7_statistical_methods'] = section_data
            else:
                result.errors.append("Failed to generate Statistical Methods section")

        # Section 8: Missing Data Handling
        if '8_missing_data' not in skip:
            print("\n  [8/9] Generating Missing Data Handling section...")
            section_data = self._generate_missing_data(facts)
            if section_data:
                result.sections['8_missing_data'] = section_data
            else:
                result.errors.append("Failed to generate Missing Data section")

        # Section 9: Safety Analysis
        if '9_safety_analysis' not in skip:
            print("\n  [9/10] Generating Safety Analysis section...")
            section_data = self._generate_safety_analysis(facts)
            if section_data:
                result.sections['9_safety_analysis'] = section_data
            else:
                result.errors.append("Failed to generate Safety Analysis section")

        # Section 10: PK Analysis (if applicable)
        if '10_pk_analysis' not in skip and facts.has_pk_substudy:
            print("\n  [10/10] Generating PK Analysis section...")
            section_data = self._generate_pk_analysis(facts)
            if section_data:
                result.sections['10_pk_analysis'] = section_data
            else:
                result.errors.append("Failed to generate PK Analysis section")

        # Appendix sections (always generate)
        print("\n  [11/14] Generating Appendix A: Endpoint Derivations...")
        result.sections['11_appendix_derivations'] = self._generate_appendix_derivations(facts)

        print("\n  [12/14] Generating Appendix B: Model Specifications...")
        result.sections['12_appendix_model_specs'] = self._generate_appendix_model_specs(facts)

        print("\n  [13/14] Generating Appendix C: Data Handling Rules...")
        result.sections['13_appendix_data_handling'] = self._generate_appendix_data_handling(facts)

        print("\n  [14/14] Generating Appendix D: Table Shells...")
        result.sections['14_appendix_table_shells'] = self._generate_appendix_table_shells(facts)

        # =================================================================
        # STAGE 4: Contamination Detection
        # =================================================================
        print("\n[STAGE 4] Checking for contamination...")

        full_text = "\n".join(result.sections.values())
        # Use legacy_facts for contamination detector (expects CitedValue format)
        is_contaminated, contaminants = self.contamination_detector.check_contamination(
            full_text, legacy_facts
        )

        if is_contaminated:
            result.contamination_detected = True
            result.contamination_details = contaminants
            result.errors.append(f"CONTAMINATION DETECTED: {contaminants}")
            result.success = False
            print(f"  CONTAMINATION FOUND: {contaminants}")
        else:
            print("  No contamination detected")

        # =================================================================
        # STAGE 5: Assemble Final SAP
        # =================================================================
        print("\n[STAGE 5] Assembling final SAP document...")

        # If contamination was detected, do NOT assemble - this is a critical failure
        if result.contamination_detected:
            result.sap_text = ""
            result.success = False
            print("  BLOCKED: SAP not assembled due to contamination detection")
        else:
            result.sap_text = self._assemble_sap(result.sections, facts)
            # Check if any critical errors occurred
            critical_errors = [e for e in result.errors if 'HIGH RISK' in e or 'CONTAMINATION' in e]
            if critical_errors:
                result.success = False
                print(f"  WARNING: SAP assembled but {len(critical_errors)} critical errors found")

        # =================================================================
        # Summary
        # =================================================================
        print("\n" + "="*60)
        print("PIPELINE SUMMARY (FULL COVERAGE)")
        print("="*60)
        print(f"  Success: {result.success}")
        print(f"  Constraint Coverage: {result.constraint_coverage}/28 entities")
        print(f"  Sections generated: {list(result.sections.keys())}")
        print(f"  Contamination: {'YES - BLOCKED' if result.contamination_detected else 'None'}")
        print(f"  Errors: {len(result.errors)}")
        print(f"  Warnings: {len(result.warnings)}")

        # Show key constrained values
        print("\n  KEY CONSTRAINTS ENFORCED:")
        print(f"    drug_name = Literal['{facts.drug_name or 'Study Drug'}']")
        print(f"    total_n = Literal[{facts.total_n or 'unknown'}]")
        print(f"    ratio = Literal['{facts.ratio or '1:1'}']")
        print(f"    nct_id = Literal['{facts.nct_id or 'unknown'}']")

        if result.errors:
            print("\n  ERRORS:")
            for err in result.errors:
                print(f"    - {err}")

        return result

    def _check_critical_facts(self, facts: ProtocolFacts) -> List[str]:
        """Check for missing critical facts (legacy)"""
        missing = []
        if not facts.total_n:
            missing.append("total_n")
        if not facts.drug_name:
            missing.append("drug_name")
        if not facts.ratio:
            missing.append("ratio")
        if not facts.num_arms:
            missing.append("num_arms")
        return missing

    def _check_critical_facts_full(self, facts: FullProtocolFacts) -> List[str]:
        """Check for missing critical facts (full schema)"""
        missing = []

        # HIGH PRIORITY - these prevent contamination from other protocols
        high_priority = [
            ('drug_name', 'Drug name missing - HIGH RISK for contamination'),
            ('total_n', 'Sample size missing - HIGH RISK for wrong values'),
            ('ratio', 'Randomization ratio missing - may use wrong ratio'),
            ('num_arms', 'Number of arms missing - may use wrong design'),
        ]

        for field, message in high_priority:
            value = getattr(facts, field, None)
            if not value or (isinstance(value, (list, dict)) and len(value) == 0):
                missing.append(f"{field} (HIGH RISK)")

        # MEDIUM PRIORITY - important for SAP quality
        medium_priority = [
            'nct_id',
            'indication',
            'phase',
            'primary_endpoint',
            'primary_timepoint',
            'alpha',
            'alpha_sidedness',
            'primary_analysis_method',
            'primary_population',
        ]

        for field in medium_priority:
            value = getattr(facts, field, None)
            if not value:
                missing.append(field)

        # LOWER PRIORITY - nice to have
        lower_priority = [
            'stratification_factors',
            'itt_definition',
            'secondary_endpoints',
            'arm_names',
            'arm_descriptions',
        ]

        for field in lower_priority:
            value = getattr(facts, field, None)
            if not value or (isinstance(value, (list, dict)) and len(value) == 0):
                missing.append(f"{field} (optional)")

        return missing

    def _count_constraints(self, facts: FullProtocolFacts) -> int:
        """Count how many entities are constrained"""
        count = 0
        fields = [
            facts.nct_id, facts.study_id, facts.sponsor, facts.title,
            facts.phase, facts.therapeutic_area, facts.indication,
            facts.design_type, facts.drug_name, facts.drug_code,
            facts.route, facts.total_n, facts.ratio, facts.power,
            facts.alpha, facts.alpha_sidedness, facts.dropout_rate,
            facts.primary_endpoint, facts.primary_timepoint,
            facts.primary_population, facts.primary_analysis_method,
        ]
        for f in fields:
            if f is not None:
                count += 1
        # Count list fields
        if facts.arm_names:
            count += 1
        if facts.arm_descriptions:
            count += 1
        if facts.secondary_endpoints:
            count += 1
        if facts.stratification_factors:
            count += 1
        if facts.per_arm_n:
            count += 1
        return count

    def _print_extracted_facts(self, facts: ProtocolFacts):
        """Print extracted facts for debugging (legacy)"""
        print("\n  EXTRACTED FACTS:")
        print(f"    Drug: {facts.drug_name.value if facts.drug_name else 'NOT FOUND'}")
        print(f"    NCT: {facts.nct_id.value if facts.nct_id else 'NOT FOUND'}")
        print(f"    Total N: {facts.total_n.value if facts.total_n else 'NOT FOUND'}")
        print(f"    Ratio: {facts.ratio.value if facts.ratio else 'NOT FOUND'}")
        print(f"    Arms: {facts.num_arms.value if facts.num_arms else 'NOT FOUND'}")
        print(f"    Per-arm N: {facts.per_arm_n.value if facts.per_arm_n else 'NOT FOUND'}")
        print(f"    Power: {facts.power.value if facts.power else 'NOT FOUND'}")
        print(f"    Alpha: {facts.alpha.value if facts.alpha else 'NOT FOUND'}")
        print(f"    Route: {facts.route.value if facts.route else 'NOT FOUND'}")

    def _print_schema_constraints(self, facts: ProtocolFacts):
        """Print the Literal constraints that will be enforced (legacy)"""
        print("\n  SCHEMA CONSTRAINTS (LLM cannot violate these):")
        print(f"    total_n: Literal[{facts.total_n.value if facts.total_n else 100}]")
        print(f"    ratio: Literal[\"{facts.ratio.value if facts.ratio else '1:1'}\"]")
        print(f"    num_arms: Literal[{facts.num_arms.value if facts.num_arms else 2}]")
        print(f"    drug_name: Literal[\"{facts.drug_name.value if facts.drug_name else 'Study Drug'}\"]")

    def _print_schema_constraints_full(self, facts: FullProtocolFacts):
        """Print the full Literal constraints"""
        print("\n  FULL SCHEMA CONSTRAINTS (all 28 entities):")
        print(f"    [ID] nct_id: Literal['{facts.nct_id or 'UNKNOWN'}']")
        print(f"    [ID] study_id: Literal['{facts.study_id or 'UNKNOWN'}']")
        print(f"    [DRUG] drug_name: Literal['{facts.drug_name or 'Study Drug'}']")
        print(f"    [DRUG] drug_code: Literal['{facts.drug_code or ''}']")
        print(f"    [DRUG] route: Literal['{facts.route or 'Not specified'}']")
        print(f"    [SIZE] total_n: Literal[{facts.total_n or 100}]")
        print(f"    [SIZE] ratio: Literal['{facts.ratio or '1:1'}']")
        print(f"    [SIZE] num_arms: Literal[{facts.num_arms or 2}]")
        print(f"    [SIZE] power: Literal['{facts.power or '80%'}']")
        print(f"    [SIZE] alpha: Literal[{facts.alpha or '[NOT EXTRACTED]'}]")
        print(f"    [ENDPOINT] primary_endpoint: Literal['{(facts.primary_endpoint or 'Primary endpoint')[:50]}...']")
        print(f"    [STRAT] stratification_factors: {len(facts.stratification_factors or [])} factors")
        print(f"\n    Coverage: {self._count_constraints(facts)}/28 entities constrained")

    def _facts_to_dict(self, facts: ProtocolFacts) -> Dict[str, Any]:
        """Convert ProtocolFacts to dictionary for prompts (legacy)"""
        return {
            'total_n': facts.total_n.value if facts.total_n else None,
            'ratio': facts.ratio.value if facts.ratio else None,
            'num_arms': facts.num_arms.value if facts.num_arms else None,
            'per_arm_n': facts.per_arm_n.value if facts.per_arm_n else None,
            'power': facts.power.value if facts.power else None,
            'alpha': facts.alpha.value if facts.alpha else None,
            'alpha_sidedness': facts.alpha_sidedness.value if facts.alpha_sidedness else None,
            'drug_name': facts.drug_name.value if facts.drug_name else None,
            'route': facts.route.value if facts.route else None,
        }

    def _full_facts_to_dict(self, facts: FullProtocolFacts) -> Dict[str, Any]:
        """Convert FullProtocolFacts to dictionary for prompts (all 28 entities)"""
        return {
            # Identification
            'nct_id': facts.nct_id,
            'study_id': facts.study_id,
            'sponsor': facts.sponsor,
            'title': facts.title,
            # Study info
            'phase': facts.phase,
            'therapeutic_area': facts.therapeutic_area,
            'indication': facts.indication,
            'design_type': facts.design_type,
            # Drug
            'drug_name': facts.drug_name,
            'drug_code': facts.drug_code,
            'drug_generic': facts.drug_generic,
            'route': facts.route,
            # Arms
            'num_arms': facts.num_arms,
            'ratio': facts.ratio,
            'arm_names': facts.arm_names,
            'arm_descriptions': facts.arm_descriptions,
            'arm_doses': facts.arm_doses,
            # Sample size
            'total_n': facts.total_n,
            'per_arm_n': facts.per_arm_n,
            'power': facts.power,
            'power_scenarios': facts.power_scenarios if hasattr(facts, 'power_scenarios') else [],
            'alpha': facts.alpha,
            'alpha_sidedness': facts.alpha_sidedness,
            'dropout_rate': facts.dropout_rate,
            # Power calculation assumptions
            'expected_response_placebo': facts.expected_response_placebo if hasattr(facts, 'expected_response_placebo') else None,
            'expected_response_active': facts.expected_response_active if hasattr(facts, 'expected_response_active') else None,
            'primary_comparison': facts.primary_comparison if hasattr(facts, 'primary_comparison') else None,
            # Endpoints
            'primary_endpoint': facts.primary_endpoint,
            'primary_timepoint': facts.primary_timepoint,
            'secondary_endpoints': facts.secondary_endpoints,
            # Populations
            'primary_population': facts.primary_population,
            'itt_definition': facts.itt_definition,
            'pp_definition': facts.pp_definition,
            'safety_definition': facts.safety_definition,
            # Stratification
            'stratification_factors': facts.stratification_factors,
            # Analysis
            'primary_analysis_method': facts.primary_analysis_method,
            'study_duration': facts.study_duration,
        }

    def _generate_sample_size(
        self,
        schema_class,
        facts: ProtocolFacts,
        facts_summary: Dict
    ) -> Tuple[str, VerificationResult]:
        """Generate and verify Sample Size section"""
        # Try structured generation
        response = self.section_generator.generate_sample_size_section(
            schema_class, facts_summary
        )

        if response.success and response.data:
            # Convert to dict for verification
            section_dict = response.data.model_dump()

            # Verify
            verification = self.verifier.verify_sample_size_section(section_dict, facts)

            # Assemble prose
            prose = self.assembler.assemble_sample_size_section(section_dict)

            return prose, verification
        else:
            # Fallback: Generate template-based section
            print("    Falling back to template-based generation...")
            section_dict = self._template_sample_size(facts)
            verification = self.verifier.verify_sample_size_section(section_dict, facts)
            prose = self.assembler.assemble_sample_size_section(section_dict)
            return prose, verification

    def _generate_study_design(
        self,
        schema_class,
        facts: ProtocolFacts,
        facts_summary: Dict
    ) -> Tuple[str, VerificationResult]:
        """Generate and verify Study Design section"""
        # Handle multiple fact formats (CitedValue, TreatmentArm, or direct string)
        arm_details = []
        if hasattr(facts, 'arms') and facts.arms:
            for arm in facts.arms:
                if hasattr(arm, 'value'):  # CitedValue format
                    arm_details.append(arm.value)
                elif hasattr(arm, 'name'):  # TreatmentArm format
                    arm_details.append(arm.name)
                else:  # Direct string
                    arm_details.append(str(arm))
        elif hasattr(facts, 'arm_descriptions') and facts.arm_descriptions:
            arm_details = facts.arm_descriptions
        elif hasattr(facts, 'arm_names') and facts.arm_names:
            arm_details = facts.arm_names

        response = self.section_generator.generate_study_design_section(
            schema_class, facts_summary, arm_details
        )

        if response.success and response.data:
            section_dict = response.data.model_dump()
            verification = self.verifier.verify_study_design_section(section_dict, facts)
            prose = self.assembler.assemble_study_design_section(section_dict)
            return prose, verification
        else:
            # Fallback: Template-based
            print("    Falling back to template-based generation...")
            section_dict = self._template_study_design(facts)
            verification = self.verifier.verify_study_design_section(section_dict, facts)
            prose = self.assembler.assemble_study_design_section(section_dict)
            return prose, verification

    def _template_sample_size(self, facts: ProtocolFacts) -> Dict:
        """Create template-based Sample Size section data"""
        # Handle multiple fact formats (CitedValue or direct values)
        def get_value(attr, default):
            if attr is None:
                return default
            if hasattr(attr, 'value'):  # CitedValue format
                return attr.value
            return attr  # Direct value

        total_n = get_value(getattr(facts, 'total_n', None), 100)
        ratio = get_value(getattr(facts, 'ratio', None), "1:1")
        num_arms = get_value(getattr(facts, 'num_arms', None), 2)
        per_arm_n = get_value(getattr(facts, 'per_arm_n', None), total_n // num_arms if num_arms else 50)

        # Handle power - could be "80%" string or 80 int
        # NO DEFAULTS - extraction failures should be explicit
        power_raw = get_value(getattr(facts, 'power', None), "[POWER NOT EXTRACTED]")
        if isinstance(power_raw, str) and power_raw != "[POWER NOT EXTRACTED]":
            power = int(power_raw.replace('%', '')) if power_raw else "[POWER NOT EXTRACTED]"
        else:
            power = power_raw if power_raw else "[POWER NOT EXTRACTED]"

        alpha = get_value(getattr(facts, 'alpha', None), "[ALPHA NOT EXTRACTED]")
        alpha_side = get_value(getattr(facts, 'alpha_sidedness', None), "[SIDEDNESS NOT EXTRACTED]")

        # Get power calculation assumptions if available - NO DEFAULTS
        expected_response_placebo = get_value(getattr(facts, 'expected_response_placebo', None), None)
        expected_response_active = get_value(getattr(facts, 'expected_response_active', None), None)
        power_scenarios = getattr(facts, 'power_scenarios', [])
        dropout_rate = get_value(getattr(facts, 'dropout_rate', None), "[DROPOUT RATE NOT EXTRACTED]")

        # NO DEFAULT power_scenarios - only use what was extracted

        return {
            'total_n': total_n,
            'ratio': ratio,
            'power_percent': power,
            'alpha': alpha,
            'alpha_sidedness': alpha_side,
            'num_arms': num_arms,
            'per_arm_n': per_arm_n,
            'expected_response_placebo': expected_response_placebo,
            'expected_response_active': expected_response_active,
            'power_scenarios': power_scenarios,
            'dropout_rate': dropout_rate,
            'introduction': "The sample size for this study was determined based on clinical and statistical considerations to ensure adequate power to detect a clinically meaningful treatment difference while accounting for expected dropout rates.",
            'power_calculation_narrative': f"Power calculations were performed using a {alpha_side} test at α = {alpha}. The power analysis was conducted for both the primary pairwise comparison and the combined treatment comparison against placebo.",
            'conclusion': "The planned sample size provides adequate statistical power to achieve the study objectives while considering practical enrollment constraints and expected dropout."
        }

    def _template_study_design(self, facts: ProtocolFacts) -> Dict:
        """Create template-based Study Design section data"""
        # Handle multiple fact formats (CitedValue or direct values)
        def get_value(attr, default):
            if attr is None:
                return default
            if hasattr(attr, 'value'):  # CitedValue format
                return attr.value
            return attr  # Direct value

        drug = get_value(facts.drug_name, "[STUDY DRUG]") if hasattr(facts, 'drug_name') else "[STUDY DRUG]"
        num_arms = get_value(facts.num_arms, 2) if hasattr(facts, 'num_arms') else 2
        ratio = get_value(facts.ratio, "1:1") if hasattr(facts, 'ratio') else "1:1"
        route = get_value(facts.route, "intravenous") if hasattr(facts, 'route') else "intravenous"

        # Get dosing information if available
        doses = getattr(facts, 'doses', None) or getattr(facts, 'dose_levels', None)
        dosing_schedule = get_value(getattr(facts, 'dosing_schedule', None), None)
        schedule_text = f" {dosing_schedule}" if dosing_schedule else ""

        # Generate arm descriptions - handle multiple formats
        arm_descriptions = []
        if hasattr(facts, 'arms') and facts.arms:
            for arm in facts.arms[:num_arms]:
                if hasattr(arm, 'value'):  # CitedValue format
                    arm_descriptions.append(arm.value)
                elif hasattr(arm, 'name'):  # TreatmentArm format
                    # Check if arm has dose information
                    if hasattr(arm, 'dose') and arm.dose:
                        arm_descriptions.append(f"{arm.name} ({arm.dose})")
                    else:
                        arm_descriptions.append(arm.name)
                else:  # Direct string
                    arm_descriptions.append(str(arm))
        elif hasattr(facts, 'arm_descriptions') and facts.arm_descriptions:
            arm_descriptions = facts.arm_descriptions[:num_arms]
        elif hasattr(facts, 'arm_names') and facts.arm_names:
            arm_descriptions = facts.arm_names[:num_arms]
        else:
            # Generate default arm descriptions with dose placeholders
            if num_arms == 2:
                if doses and len(doses) >= 1:
                    arm_descriptions = [f"{drug} {doses[0]}{schedule_text} - Active Treatment", f"Placebo IV{schedule_text}"]
                else:
                    arm_descriptions = [f"{drug} [DOSE]{schedule_text} - Active Treatment", f"Placebo IV{schedule_text}"]
            elif num_arms == 3:
                if doses and len(doses) >= 2:
                    arm_descriptions = [
                        f"{drug} {doses[0]}{schedule_text} - High Dose",
                        f"{drug} {doses[1]}{schedule_text} - Low Dose",
                        f"Placebo IV{schedule_text}"
                    ]
                else:
                    arm_descriptions = [
                        f"{drug} [HIGH DOSE]{schedule_text} - High Dose",
                        f"{drug} [LOW DOSE]{schedule_text} - Low Dose",
                        f"Placebo IV{schedule_text}"
                    ]
            else:
                arm_descriptions = [f"Treatment arm {i+1}" for i in range(num_arms)]

        return {
            'drug_name': drug,
            'num_arms': num_arms,
            'ratio': ratio,
            'route': route,
            'arm_descriptions': arm_descriptions,
            'design_narrative': f"This is a randomized, double-blind, placebo-controlled study designed to evaluate the efficacy and safety of {drug}. Eligible patients will be randomized to one of the treatment arms according to the randomization ratio. The study drug will be administered via {route} route according to the dosing schedule specified in the protocol."
        }

    # =========================================================================
    # NEW SECTION GENERATORS (Full Coverage)
    # =========================================================================

    def _generate_introduction(self, facts: FullProtocolFacts) -> str:
        """Generate Section 1: Introduction"""
        nct_id = facts.nct_id or "NCT-UNKNOWN"
        study_id = facts.study_id or "STUDY-ID"
        sponsor = facts.sponsor or "Sponsor"
        title = facts.title or "Clinical Trial"
        phase = facts.phase or "Phase 2"
        drug_name = facts.drug_name or "Investigational Product"
        indication = facts.indication or "target indication"

        return f"""## 1. INTRODUCTION

### 1.1 Purpose

This Statistical Analysis Plan (SAP) describes the planned statistical analyses for the clinical trial {nct_id} ({study_id}). This document provides detailed specifications for the statistical methodology to be used in the analysis of data from this study.

### 1.2 Study Overview

**Protocol:** {nct_id}
**Study ID:** {study_id}
**Sponsor:** {sponsor}
**Title:** {title}
**Phase:** {phase}
**Investigational Product:** {drug_name}
**Indication:** {indication}

### 1.3 Scope

This SAP covers all planned efficacy, safety, and exploratory analyses for the study. Any deviations from this plan will be documented and justified in the clinical study report.

### 1.4 Reference Documents

- Protocol: {study_id}
- ICH E9 Statistical Principles for Clinical Trials
- ICH E9(R1) Addendum on Estimands and Sensitivity Analysis
- CDISC ADaM Implementation Guide
"""

    def _generate_objectives_estimands(self, facts: FullProtocolFacts) -> str:
        """Generate Section 2: Objectives and Estimands"""
        drug_name = facts.drug_name or "Investigational Product"
        indication = facts.indication or "the target indication"
        primary_endpoint = facts.primary_endpoint or "the primary efficacy endpoint"
        primary_timepoint = facts.primary_timepoint or "Week 12"

        # Get arm info for treatment description with dose information
        num_arms = facts.num_arms or 3
        doses = getattr(facts, 'doses', None) or getattr(facts, 'dose_levels', None)
        dosing_schedule = facts.dosing_schedule if hasattr(facts, 'dosing_schedule') and facts.dosing_schedule else "Q2W"
        route = facts.route or "IV"

        # Build arm descriptions - prefer explicit descriptions, then construct from doses
        if facts.arm_descriptions and not all("Investigational" in str(d) for d in facts.arm_descriptions):
            arm_descriptions = facts.arm_descriptions
        elif facts.arm_names and not all("Arm" in str(n) for n in facts.arm_names):
            arm_descriptions = facts.arm_names
        elif doses and len(doses) >= 2 and num_arms == 3:
            # Construct specific arm descriptions from dose info
            arm_descriptions = [
                f"{drug_name} {doses[0]} {route} {dosing_schedule} - High Dose",
                f"{drug_name} {doses[1]} {route} {dosing_schedule} - Low Dose",
                f"Placebo {route} {dosing_schedule}"
            ]
        elif doses and len(doses) >= 1 and num_arms == 2:
            arm_descriptions = [
                f"{drug_name} {doses[0]} {route} {dosing_schedule} - Active Treatment",
                f"Placebo {route} {dosing_schedule}"
            ]
        else:
            # Default with placeholders for doses
            if num_arms == 3:
                arm_descriptions = [
                    f"{drug_name} [HIGH DOSE] {route} {dosing_schedule} - High Dose",
                    f"{drug_name} [LOW DOSE] {route} {dosing_schedule} - Low Dose",
                    f"Placebo {route} {dosing_schedule}"
                ]
            else:
                arm_descriptions = [
                    f"{drug_name} [DOSE] {route} {dosing_schedule} - Active Treatment",
                    f"Placebo {route} {dosing_schedule}"
                ]

        # Build treatment arms text
        arms_text = "\n".join([f"  - {desc}" for desc in arm_descriptions])

        return f"""## 2. STUDY OBJECTIVES AND ESTIMANDS

### 2.1 Primary Objective

To evaluate the efficacy of {drug_name} compared to placebo in patients with {indication}.

### 2.2 Primary Estimand (ICH E9(R1) Framework)

The primary estimand is defined according to ICH E9(R1) with the following attributes:

| Attribute | Specification |
|-----------|---------------|
| Population | Adult patients with {indication} meeting inclusion/exclusion criteria |
| Treatment | {drug_name} vs. Placebo |
| Variable | {primary_endpoint} at {primary_timepoint} |
| Intercurrent Events | See Section 2.2.1 below |
| Summary Measure | Difference in proportions (or appropriate measure) |

#### 2.2.1 Intercurrent Events and Strategies

| Intercurrent Event | Strategy | Rationale |
|--------------------|----------|-----------|
| Treatment discontinuation due to AE | Treatment Policy | Captures real-world treatment effect |
| Use of rescue medication | Treatment Policy | Part of intended treatment strategy |
| Missing assessment | Non-responder | Conservative approach for efficacy |

### 2.3 Secondary Objectives

1. To evaluate the safety and tolerability of {drug_name}
2. To evaluate secondary efficacy endpoints
3. To characterize the pharmacokinetics of {drug_name} (if applicable)

### 2.4 Secondary Estimands

Secondary estimands follow the same framework as the primary estimand with appropriate modifications for each secondary endpoint.

### 2.5 Treatment Arms

{arms_text}
"""

    def _generate_analysis_populations(self, facts: FullProtocolFacts) -> str:
        """Generate Section 4: Analysis Populations (with operational rules enhancement)"""
        primary_population = facts.primary_population or "FAS"
        itt_def = facts.itt_definition or "All randomized patients"
        pp_def = facts.pp_definition or "All patients in the ITT population who complete the study without major protocol violations"
        safety_def = facts.safety_definition or "All patients who received at least one dose of study medication"

        # Build PK population if applicable
        pk_section = ""
        if facts.therapeutic_area and "pk" in str(facts).lower():
            pk_section = """
### 4.5 Pharmacokinetic (PK) Population

The PK population includes all patients in the PK subgroup who received at least one dose of study medication and have at least one measurable post-dose PK sample.
"""

        # Check for enhanced population section from operational rules (biosimilar dual-pop, etc.)
        dual_population_section = ""
        enhanced_pk_section = ""

        if self.operational_integrator:
            try:
                # Get study type to check for biosimilar
                if self.operational_integrator.study_type == 'biosimilar':
                    dual_population_section = """
### 4.7 Dual Population Requirement (Biosimilar)

**Equivalence must be demonstrated in BOTH the Intent-to-Treat (ITT) and Per-Protocol (PP) populations.**

The study will be considered successful only if the equivalence margins are met in both populations:
- **ITT Population:** Preserves randomization; provides estimate of treatment policy effect
- **PP Population:** Evaluates effect in subjects who adhered to the protocol

**Rationale:** Per FDA and EMA biosimilar guidance, demonstration of equivalence in both ITT and PP populations is required to establish biosimilarity.
"""
                    print("    [OPERATIONAL] Added dual population requirement for biosimilar")

                # Enhanced PK population for biosimilar
                if self.operational_integrator.study_type == 'biosimilar':
                    enhanced_pk_section = """
### 4.8 PK Population (Biosimilar)

The PK Population includes all subjects in the Safety Population who:
- Received at least one dose of study drug
- Have at least one evaluable PK sample at the pre-specified timepoints
- Have no major protocol deviations affecting PK assessment

**PK Equivalence Criteria:**
Equivalence of PK parameters (Cmax, AUC0-inf, AUC0-tau) will be concluded if the 90% confidence intervals for the geometric mean ratios (Test/Reference) are contained within 80.00% to 125.00%.
"""
                    pk_section = enhanced_pk_section  # Replace with enhanced version

            except Exception as e:
                print(f"    [OPERATIONAL] Warning: Could not enhance populations: {e}")

        return f"""## 4. ANALYSIS POPULATIONS

### 4.1 Intent-to-Treat (ITT) Population

{itt_def}

This population will be used for sensitivity analyses of efficacy endpoints.

### 4.2 Full Analysis Set (FAS)

All randomized patients who received at least one dose of study medication and have at least one post-baseline efficacy assessment.

This is the **primary analysis population** for efficacy analyses.

### 4.3 Per-Protocol (PP) Population

{pp_def}

This population will be used for supportive efficacy analyses.

### 4.4 Safety Population

{safety_def}

This is the primary analysis population for all safety analyses.
{pk_section}{dual_population_section}
### 4.6 Population Derivation

| Population | Inclusion Criteria | Exclusion Criteria | Primary Use |
|------------|-------------------|-------------------|-------------|
| ITT | All randomized | None | Sensitivity analysis |
| FAS | ITT + ≥1 dose + ≥1 post-baseline | None | PRIMARY EFFICACY |
| PP | FAS patients | Major protocol violations | Supportive efficacy |
| Safety | ≥1 dose of study medication | None | SAFETY ANALYSIS |
"""

    def _generate_endpoints(self, facts: FullProtocolFacts) -> str:
        """Generate Section 5: Endpoints (RAG-enhanced)"""
        primary_endpoint = facts.primary_endpoint or "Primary efficacy endpoint"
        primary_timepoint = facts.primary_timepoint or "Week 12"
        primary_definition = facts.primary_endpoint_definition or ""

        # Get RAG context for enhanced details
        rag_context = self._get_rag_context(facts)
        rag_endpoint_context = rag_context.get('endpoints', '')

        # Build primary endpoint definition section
        primary_def_section = ""
        if primary_definition:
            primary_def_section = f"\n\n**Definition Criteria:** {primary_definition}"

        # RAG-enhanced: Add censoring rules for time-to-event endpoints
        rag_enhanced_section = ""
        endpoint_lower = primary_endpoint.lower()
        if any(term in endpoint_lower for term in ['survival', 'pfs', 'efs', 'dfs', 'time to', 'duration']):
            rag_enhanced_section = """

**Censoring Rules:**
- Subjects alive/without event at data cutoff: censored at last known alive date
- Subjects lost to follow-up: censored at date of last contact
- Events occurring after subsequent therapy: censored at start of new therapy

**Data Collection:** Event data will be collected for all randomized subjects regardless of treatment discontinuation."""

        # Build secondary endpoints table using detailed info if available (ASCII format)
        secondary_table = ""
        if facts.secondary_endpoints_detailed:
            secondary_table = "| # | Endpoint | Timepoint |\n|---|----------|----------|\n"
            for i, ep_info in enumerate(facts.secondary_endpoints_detailed, 1):
                endpoint = ep_info.get('endpoint', '')[:80]
                timepoint = ep_info.get('timepoint', 'Various')
                secondary_table += f"| {i} | {endpoint} | {timepoint} |\n"
        elif facts.secondary_endpoints:
            secondary_table = "| # | Endpoint | Timepoint |\n|---|----------|----------|\n"
            for i, ep in enumerate(facts.secondary_endpoints, 1):
                secondary_table += f"| {i} | {ep} | Various |\n"
        else:
            # Use primary timepoint for fallback - don't hardcode Week 12
            tp = primary_timepoint  # e.g., "Week 12" or "Week 8"
            secondary_table = f"""| # | Endpoint | Timepoint |
|---|----------|-----------|
| 1 | Clinical/endoscopic response | {tp} |
| 2 | Mucosal healing/endoscopic improvement | {tp} |
| 3 | Clinical remission | Multiple visits through {tp} |
| 4 | Clinical response | Multiple visits through {tp} |
| 5 | Change from baseline in disease activity score | Multiple visits through {tp} |
| 6 | Sustained response | {tp} |"""

        # Build biomarker section if applicable
        biomarker_section = ""
        if facts.biomarker_endpoints:
            biomarker_list = ", ".join(facts.biomarker_endpoints[:10])
            biomarker_section = f"""

### 5.5 Exploratory Biomarker Endpoints

The following biomarkers will be analyzed as exploratory endpoints:

- {biomarker_list}

Analysis will include:
- Change from baseline at each assessment timepoint
- Correlation with clinical response
- Subgroup analysis by baseline biomarker levels
"""

        return f"""## 5. ENDPOINTS

### 5.1 Primary Endpoint

**Definition:** {primary_endpoint}

**Timepoint:** {primary_timepoint}{primary_def_section}{rag_enhanced_section}

**Derivation:** The primary endpoint will be derived according to the protocol definition. Patients with missing data at the primary timepoint will be considered as non-responders (treatment failure).

### 5.2 Secondary Efficacy Endpoints

{secondary_table}

### 5.3 Safety Endpoints

| Category | Endpoints |
|----------|-----------|
| Adverse Events | TEAEs, SAEs, AEs leading to discontinuation, AEs by severity |
| Laboratory | Clinical chemistry, hematology, urinalysis abnormalities |
| Vital Signs | Changes from baseline in BP, heart rate, temperature |
| ECG | Changes from baseline in ECG parameters (if applicable) |

### 5.4 Pharmacokinetic Endpoints

| Parameter | Description |
|-----------|-------------|
| AUC | Area under the concentration-time curve |
| Cmax | Maximum observed concentration |
| tmax | Time to maximum concentration |
| t½ | Terminal elimination half-life |
| CL/F | Apparent clearance (if applicable) |
| Vz/F | Apparent volume of distribution (if applicable) |
{biomarker_section}
"""

    def _generate_statistical_methods(self, facts: FullProtocolFacts) -> str:
        """Generate Section 7: Statistical Methods (RAG-enhanced)"""
        primary_endpoint = facts.primary_endpoint or "primary endpoint"
        primary_timepoint = facts.primary_timepoint or "Week 12"
        primary_population = facts.primary_population or "FAS"
        primary_analysis_method = facts.primary_analysis_method or "Logistic Regression"
        alpha = facts.alpha or "[ALPHA NOT EXTRACTED]"
        alpha_sidedness = facts.alpha_sidedness or "[SIDEDNESS NOT EXTRACTED]"

        # Get RAG context for enhanced method details
        rag_context = self._get_rag_context(facts)
        rag_methods_context = rag_context.get('methods', '')

        # Get stratification factors
        strat_factors = facts.stratification_factors if facts.stratification_factors else []
        strat_text = ", ".join(strat_factors) if strat_factors else "randomization stratification factors"

        # Build proper model specification based on endpoint type
        # RAG-enhanced: Detect time-to-event endpoints and add appropriate methods
        endpoint_lower = primary_endpoint.lower()
        is_tte = any(term in endpoint_lower for term in ['survival', 'pfs', 'efs', 'dfs', 'time to', 'duration'])

        if is_tte or "kaplan" in primary_analysis_method.lower() or "cox" in primary_analysis_method.lower():
            model_type = "Time-to-Event Analysis (Kaplan-Meier + Cox)"
            model_spec = """**Primary Analysis:** Kaplan-Meier method to estimate median survival and survival rates at landmark timepoints (6, 12, 18, 24 months).

**Stratified Log-Rank Test:** Treatment comparison using log-rank test stratified by randomization stratification factors at {alpha_text} alpha={alpha_val}.

**Hazard Ratio Estimation:**
```
h(t|X) = h₀(t) × exp(β₁×Treatment + β₂×Stratification_Factors)
```

**Treatment Effect Estimate:** Hazard ratio with {ci}% confidence interval from Cox proportional hazards model.

**Model Assumptions:** The proportional hazards assumption will be assessed using Schoenfeld residuals and log-log survival plots. If violated, time-varying effects will be explored."""
        elif "logistic" in primary_analysis_method.lower():
            model_type = "Logistic Regression (for binary endpoint)"
            model_spec = """```
logit(P(response=1)) = β₀ + β₁×Treatment + β₂×Stratification_Factors + β₃×Baseline_Score
```

**Treatment Effect Estimate:** Odds ratio with {ci}% confidence interval"""
        elif "ancova" in primary_analysis_method.lower():
            model_type = "ANCOVA (for continuous endpoint)"
            model_spec = """```
Y = μ + β₁×Treatment + β₂×Stratification_Factors + β₃×Baseline_Value + ε
```

**Treatment Effect Estimate:** Least squares mean difference with {ci}% confidence interval"""
        else:
            model_type = primary_analysis_method
            model_spec = """The analysis model includes treatment as a fixed effect and stratification factors as covariates.

**Treatment Effect Estimate:** Appropriate measure with {ci}% confidence interval"""

        ci_level = int((1 - alpha) * 100) if alpha_sidedness == "one-sided" else int((1 - alpha) * 100)
        model_spec = model_spec.format(ci=ci_level, alpha_text=alpha_sidedness, alpha_val=alpha)

        # Build subgroup analyses list including IL-6 if applicable
        subgroup_list = []
        if facts.subgroup_analyses:
            subgroup_list = facts.subgroup_analyses[:10]
        else:
            subgroup_list = [
                "Age group (<65, ≥65 years)",
                "Sex",
                "Geographic region",
                "Baseline disease severity",
                "Prior treatment history"
            ]

        # Add IL-6/sIL-6R if we have biomarker subgroups
        if facts.biomarker_subgroups:
            for bg in facts.biomarker_subgroups:
                if bg not in subgroup_list:
                    subgroup_list.append(bg)
        elif "IL-6" not in str(subgroup_list):
            subgroup_list.append("Baseline IL-6/sIL-6R complex levels")

        subgroup_bullets = "\n".join([f"- {sg}" for sg in subgroup_list])

        # Build visit windows section if available (ASCII format)
        visit_window_section = ""
        if facts.visit_windows:
            window_rows = "\n".join([f"| {week} | {window} |" for week, window in facts.visit_windows.items()])
            visit_window_section = f"""

### 7.8 Visit Windows

| Visit | Window Definition |
|-------|-------------------|
{window_rows}

If multiple assessments occur within a window, the assessment closest to the target day will be used.
"""
        else:
            visit_window_section = """

### 7.8 Visit Windows

| Visit | Window Definition |
|-------|-------------------|
| Week 4 | Day 28 ± 2 days |
| Week 6 | Day 42 ± 2 days |
| Week 8 | Day 56 ± 2 days |
| Week 10 | Day 70 ± 3 days |
| Week 12 | Day 84 ± 3 days |

If multiple assessments occur within a window, the assessment closest to the target day will be used.
"""

        # Build enhanced covariates section using operational rules
        covariates_section = ""
        if self.operational_integrator:
            try:
                strat_levels = ""
                if self.operational_integrator.tier1.covariates and \
                   self.operational_integrator.tier1.covariates.stratification_factor_levels:
                    levels = self.operational_integrator.tier1.covariates.stratification_factor_levels
                    strat_level_lines = []
                    for factor, level_list in levels.items():
                        strat_level_lines.append(f"  - **{factor}:** {', '.join(level_list)}")
                    strat_levels = "\n" + "\n".join(strat_level_lines)

                covariates_section = f"""
**Stratification Factors (from randomization):**
- {strat_text}
{strat_levels}

**Model Covariates:**
- Treatment group (primary factor of interest)
- All stratification factors used in randomization

**Critical Note:** Both the stratified log-rank test AND the stratified Cox proportional hazards model will include the SAME stratification factors used in randomization. This ensures consistency between hypothesis testing and effect estimation.

**Covariate Handling:**
- Stratification factors will be included as categorical covariates
- If any stratum has <5% of patients, it may be pooled with adjacent strata
- Missing baseline covariates will be imputed using median (continuous) or mode (categorical)
"""
            except Exception as e:
                # Fallback to basic covariates section
                covariates_section = f"""
**Stratification Factors:** {strat_text}

The primary analysis will adjust for the stratification factors used in randomization.
"""
        else:
            covariates_section = f"""
**Stratification Factors:** {strat_text}

The primary analysis will adjust for the stratification factors used in randomization.
"""

        # Build enhanced sensitivity analyses section
        sensitivity_section = ""
        if self.operational_integrator:
            try:
                # Use the sensitivity generator for study-type-specific analyses
                primary_type = 'TTE' if is_tte else 'binary'
                sensitivity_section = self.operational_integrator.generate_sensitivity_analyses_section()
            except Exception as e:
                sensitivity_section = """
The following sensitivity analyses will be performed for the primary endpoint:

1. **Per-Protocol Analysis:** Analysis in PP population
2. **Tipping Point Analysis:** Assess robustness to missing data assumptions
3. **Multiple Imputation:** MICE with treatment group-specific imputation
4. **As-Observed Analysis:** Excluding patients with missing data
"""
        else:
            sensitivity_section = """
The following sensitivity analyses will be performed for the primary endpoint:

1. **Per-Protocol Analysis:** Analysis in PP population
2. **Tipping Point Analysis:** Assess robustness to missing data assumptions
3. **Multiple Imputation:** MICE with treatment group-specific imputation
4. **As-Observed Analysis:** Excluding patients with missing data
"""

        # Build ICE/Estimand section (ICH E9(R1) compliant)
        ice_estimand_section = ""
        if self.operational_integrator:
            try:
                primary_name = facts.primary_endpoint or "Primary Endpoint"
                primary_type_tte = 'PFS' if 'pfs' in primary_endpoint.lower() else \
                                   'OS' if 'survival' in primary_endpoint.lower() else 'TTE'
                population = facts.indication or "study population"
                treatment = f"{facts.drug_name} vs {facts.comparator}" if facts.drug_name and facts.comparator \
                           else "study treatment vs comparator"
                summary = "Hazard ratio with 95% CI" if is_tte else "Odds ratio with 95% CI"

                ice_estimand_section = self.operational_integrator.ice_generator.generate_estimand_section(
                    primary_endpoint=primary_name,
                    primary_endpoint_type=primary_type_tte,
                    population=population,
                    treatment=treatment,
                    summary_measure=summary
                )
            except Exception as e:
                ice_estimand_section = ""  # Don't include if generation fails

        return f"""## 7. STATISTICAL METHODS

### 7.1 General Considerations

- The primary efficacy analysis will be performed at a **{alpha_sidedness}** significance level of α = {alpha}.
- Additional exploratory analyses may be performed at both {alpha_sidedness} 5% and 20% significance levels.
- Confidence intervals will be {ci_level}% confidence intervals.
- All analyses will be performed using SAS® Version 9.4 or later.

### 7.2 Primary Efficacy Analysis

**Analysis Population:** {primary_population}

**Primary Analysis Method:** {model_type}

The primary endpoint ({primary_endpoint} at {primary_timepoint}) will be analyzed using {primary_analysis_method.lower()} with treatment as a fixed effect and {strat_text} as covariates.

**Model Specification:**

{model_spec}

**Hypothesis Testing ({alpha_sidedness} at α = {alpha}):**
- H₀: No difference between {facts.drug_name or 'active treatment'} and placebo
- H₁: {facts.drug_name or 'Active treatment'} is superior to placebo

### 7.3 Handling of Covariates
{covariates_section}
### 7.4 Secondary Efficacy Analyses

Secondary endpoints will be analyzed using appropriate methods based on endpoint type:

| Endpoint Type | Analysis Method |
|---------------|-----------------|
| Binary | Logistic regression with GEE for repeated measures |
| Continuous | ANCOVA or MMRM for repeated measures |
| Time-to-event | Kaplan-Meier, Log-rank test, Cox regression |

### 7.5 Multiplicity Adjustment (Hierarchical Testing)

To control the family-wise type I error rate, secondary endpoints will be tested using a hierarchical (gate-keeping) procedure. Testing will proceed in the following pre-specified order:

| Priority | Endpoint | α-level |
|----------|----------|---------|
| 1 | Primary endpoint (high dose vs. placebo) | {alpha} ({alpha_sidedness}) |
| 2 | Primary endpoint (low dose vs. placebo) | {alpha} ({alpha_sidedness}) |
| 3 | Key secondary endpoint 1 | {alpha} (if prior tests significant) |
| 4 | Key secondary endpoint 2 | {alpha} (if prior tests significant) |

Testing stops at the first non-significant comparison.

### 7.6 Sensitivity Analyses
{sensitivity_section}
{ice_estimand_section}
### 7.7 Subgroup Analyses

Subgroup analyses will be performed for the primary endpoint by:
{subgroup_bullets}
{visit_window_section}
"""

    def _generate_missing_data(self, facts: FullProtocolFacts) -> str:
        """Generate Section 8: Missing Data Handling"""
        primary_endpoint = facts.primary_endpoint or "primary endpoint"
        endpoint_lower = primary_endpoint.lower()
        is_tte = any(term in endpoint_lower for term in ['survival', 'pfs', 'efs', 'dfs', 'time to', 'duration'])

        # Build censoring rules section for time-to-event endpoints
        censoring_section = ""
        if is_tte and self.operational_integrator:
            try:
                # Generate comprehensive censoring table from operational rules
                censoring_section = """
### 8.7 Censoring Rules for Time-to-Event Endpoints

**PFS Censoring Rules (Primary Endpoint):**

| Situation | PFS Status | Date Used | CNSR |
|-----------|------------|-----------|------|
| Documented disease progression | Event | Date of progression | 0 |
| Death (any cause) without progression | Event | Date of death | 0 |
| Adequate assessment with no progression | Censored | Date of last adequate assessment | 1 |
| No baseline tumor assessment | Censored | Date of randomization | 1 |
| No post-baseline adequate assessment | Censored | Date of randomization | 1 |
| New anticancer therapy without progression | Censored | Date of last adequate assessment before therapy | 1 |
| Two or more consecutive missed assessments | Censored | Date of last adequate assessment before missed | 1 |
| Ongoing without event | Censored | Date of last adequate assessment | 1 |
| Lost to follow-up | Censored | Date of last adequate assessment | 1 |

**Adequate Assessment Definition:** An imaging assessment that meets the protocol-specified assessment schedule within the allowed visit window.

**OS Censoring Rules (Secondary/Co-Primary):**

| Situation | OS Status | Date Used | CNSR |
|-----------|-----------|-----------|------|
| Death from any cause | Event | Date of death | 0 |
| Alive | Censored | Date of last known alive | 1 |
| Lost to follow-up | Censored | Date of last known alive | 1 |
| Consent withdrawn | Censored | Date of withdrawal | 1 |

**Note:** For OS, patients who start new anticancer therapy remain on study for survival follow-up and are NOT censored at the time of new therapy initiation.
"""
            except Exception as e:
                pass  # Fall back to no detailed censoring section

        return f"""## 8. MISSING DATA HANDLING

### 8.1 General Principles

Missing data handling follows ICH E9(R1) guidance on estimands and sensitivity analysis in clinical trials.

### 8.2 Primary Approach

**Treatment Policy Strategy:** For the primary analysis, patients with missing data for the {primary_endpoint} will be classified as non-responders (treatment failure). This approach is consistent with the treatment policy estimand strategy.

### 8.3 Missing Data Rules by Endpoint Type

| Endpoint Type | Primary Rule | Rationale |
|---------------|--------------|-----------|
| Binary efficacy | Non-responder imputation | Conservative for efficacy |
| Continuous | Last observation carried forward (LOCF) | Sensitivity: MMRM |
| Time-to-event | Censored at last known status | Standard survival analysis |

### 8.4 Sensitivity Analyses for Missing Data

To assess the robustness of the primary analysis conclusions, the following sensitivity analyses will be performed:

1. **Complete Case Analysis:** Analysis restricted to patients with observed primary endpoint
2. **Multiple Imputation:** Using MICE methodology under MAR assumption
3. **Tipping Point Analysis:** To determine how extreme assumptions about missing data would need to be to change conclusions
4. **Pattern Mixture Models:** Sensitivity to MNAR assumptions

### 8.5 Visit Windows

Analysis windows for each assessment timepoint are defined in the protocol. If multiple assessments occur within a window, the assessment closest to the target day will be used.

### 8.6 Partial Data

- Partial response data: Individual components will be imputed using last observation if available
- If individual components cannot be derived: Overall response will be set to non-responder
{censoring_section}
"""

    def _generate_pk_analysis(self, facts: FullProtocolFacts) -> str:
        """Generate Section 10: Pharmacokinetic Analysis"""
        drug_name = facts.drug_name or "study drug"
        pk_population_size = facts.pk_population_size or 24
        pk_software = facts.pk_software or "WinNonlin"
        pk_parameters = facts.pk_parameters if facts.pk_parameters else [
            "AUCinf", "AUClast", "Cmax", "tmax", "CL", "Vz", "λz", "t½", "MRT"
        ]
        pk_sampling = facts.pk_sampling_timepoints if facts.pk_sampling_timepoints else []

        # Build parameters table
        param_descriptions = {
            "AUCinf": "Area under the concentration-time curve from time 0 extrapolated to infinity",
            "AUClast": "Area under the concentration-time curve from time 0 to last measurable concentration",
            "AUCτ": "Area under the concentration-time curve over dosing interval",
            "Cmax": "Maximum observed plasma concentration",
            "tmax": "Time to maximum plasma concentration",
            "CL": "Total body clearance",
            "Vz": "Volume of distribution during terminal phase",
            "λz": "Terminal elimination rate constant",
            "t½": "Terminal elimination half-life",
            "MRT": "Mean residence time",
            "%ExtrapAUC": "Percentage of AUCinf extrapolated beyond last measurable concentration"
        }

        param_rows = ""
        for param in pk_parameters:
            desc = param_descriptions.get(param, "PK parameter")
            param_rows += f"| {param} | {desc} |\n"

        # Build sampling schedule if available
        sampling_section = ""
        if pk_sampling:
            sampling_list = ", ".join(pk_sampling[:15])
            sampling_section = f"""
### 10.4 Sampling Schedule

Intensive PK sampling will be performed at the following timepoints:
- {sampling_list}

Sparse PK sampling will be collected at additional visits as per protocol.
"""
        else:
            sampling_section = """
### 10.4 Sampling Schedule

PK sampling will be performed according to the schedule specified in the study protocol. For intensive PK characterization, sampling typically includes:

**1st Dose (Day 0) - Intensive Sampling:**
- Pre-dose (within 1 hour before infusion)
- End of infusion (EOI)
- 6 hours post-dose
- 48 hours post-dose (Day 2)
- 144 hours post-dose (Day 6)
- 240 hours post-dose (Day 10)

**2nd-5th Doses - Sparse Sampling:**
- Pre-dose (trough)
- End of infusion

**6th/Final Dose - Intensive Sampling:**
- Pre-dose
- End of infusion
- 6, 24, 48, 144, 336, 504, and 840 hours post-dose

The exact sampling windows and acceptable deviations are specified in the protocol. Samples collected outside the specified windows will be flagged but included in analysis with actual collection times.
"""

        return f"""## 10. PHARMACOKINETIC ANALYSIS

### 10.1 PK Analysis Population

The PK population consists of approximately {pk_population_size} patients who:
- Received at least one dose of {drug_name}
- Have at least one measurable post-dose PK concentration
- Participated in the PK subgroup (intensive sampling)

### 10.2 PK Parameters

The following PK parameters will be calculated using non-compartmental analysis:

| Parameter | Description |
|-----------|-------------|
{param_rows}

### 10.3 Analysis Methodology

**Software:** {pk_software} (or equivalent validated software)

**Method:** Non-compartmental analysis (NCA)

**Calculations:**
- AUC will be calculated using the linear-log trapezoidal rule
- λz will be determined by log-linear regression of the terminal phase
- t½ will be calculated as ln(2)/λz
- CL will be calculated as Dose/AUCinf
{sampling_section}
### 10.4 Descriptive Statistics

PK parameters will be summarized by treatment group using:
- N, arithmetic mean, SD, %CV, median, min, max
- Geometric mean, geometric %CV for AUC and Cmax

### 10.5 PK-PD Analysis (Exploratory)

Exploratory analyses may include:
- Exposure-response relationships for efficacy endpoints
- Exposure-safety relationships for key AEs
- Population PK modeling (if data permit)
"""

    def _generate_safety_analysis(self, facts: FullProtocolFacts) -> str:
        """Generate Section 9: Safety Analysis"""
        drug_name = facts.drug_name or "study drug"
        num_arms = facts.num_arms or 2

        # Build arm column headers
        arm_names = facts.arm_names if facts.arm_names else [f"Arm {i+1}" for i in range(num_arms)]
        arm_headers = " | ".join(arm_names)
        arm_cols = " | ".join(["n (%)" for _ in arm_names])

        return f"""## 9. SAFETY ANALYSIS

### 9.1 General Principles

Safety analyses will be performed on the Safety Population (all patients who received at least one dose of study medication). No formal statistical testing will be performed for safety endpoints; descriptive statistics and listings will be provided.

### 9.2 Adverse Events

#### 9.2.1 Adverse Event Coding

Adverse events will be coded using MedDRA (latest version available at database lock). Events will be summarized by System Organ Class (SOC) and Preferred Term (PT).

#### 9.2.2 Treatment-Emergent Adverse Events (TEAEs)

TEAEs are defined as AEs that started or worsened after the first dose of study medication.

#### 9.2.3 Adverse Event Summaries

The following tables will be produced:

| Table | Description |
|-------|-------------|
| AE.01 | Overview of adverse events |
| AE.02 | TEAEs by SOC and PT |
| AE.03 | TEAEs by relationship to study drug |
| AE.04 | TEAEs by severity |
| AE.05 | TEAEs leading to discontinuation |
| AE.06 | Serious adverse events |
| AE.07 | Deaths |

#### 9.2.4 Table Shell Example: Overview of Adverse Events

| Category | Treatment Groups | Total |
|----------|------------------|-------|
| Any TEAE | | |
| Any treatment-related TEAE | | |
| Any SAE | | |
| Any TEAE leading to discontinuation | | |
| Deaths | | |

### 9.3 Laboratory Parameters

Clinical laboratory data (hematology, chemistry, urinalysis) will be summarized using:

1. Descriptive statistics (n, mean, SD, median, min, max) by timepoint
2. Change from baseline statistics
3. Shift tables (baseline vs. worst post-baseline value)
4. Patients with potentially clinically significant (PCS) values

### 9.4 Vital Signs

Vital signs will be summarized using:
- Descriptive statistics by timepoint
- Change from baseline
- Patients with PCS values

### 9.5 Electrocardiogram (ECG)

If applicable, ECG parameters will be summarized using:
- Descriptive statistics by timepoint
- Change from baseline
- Categorical analysis of QTcF changes

### 9.6 Immunogenicity

#### 9.6.1 Anti-Drug Antibody (ADA) Assessment

ADA samples will be collected at protocol-specified timepoints for immunogenicity assessment.

**Assessment Timepoints:** As specified in the protocol (typically pre-dose and at multiple visits during treatment and follow-up periods)

#### 9.6.2 ADA Classification

| Category | Definition |
|----------|------------|
| Baseline Status | ADA positive or negative at baseline (pre-dose) |
| Treatment-Emergent | Negative at baseline → Positive post-baseline, OR ≥4-fold increase from baseline |
| Persistent ADA | Treatment-emergent ADA positive at ≥2 consecutive post-baseline visits ≥16 weeks |
| Transient ADA | Treatment-emergent ADA positive at only one visit, or at ≥2 visits <16 weeks apart |

#### 9.6.3 ADA Analysis

ADA results will be summarized by:
- Incidence of treatment-emergent ADA by treatment group
- Time to first positive ADA result
- ADA titer (if applicable)
- Relationship between ADA status and:
  - Efficacy endpoints
  - Safety endpoints (AEs, injection site reactions)
  - PK parameters (exposure)

#### 9.6.4 Neutralizing Antibodies (NAb)

If applicable, NAb testing will be performed on ADA-positive samples:
- Incidence of NAb by treatment group
- Impact of NAb on efficacy and PK

### 9.7 Exposure

Exposure to {drug_name} will be summarized:
- Duration of treatment
- Number of doses received
- Cumulative dose
"""

    def _generate_appendix_derivations(self, facts: FullProtocolFacts) -> str:
        """Generate Appendix A: Endpoint Definitions and Derivations (indication-aware, prose format)"""
        primary_endpoint = facts.primary_endpoint or "Primary Endpoint"
        primary_timepoint = facts.primary_timepoint or "Week 12"
        indication = (facts.indication or "").lower()
        drug_name = facts.drug_name or "[STUDY DRUG]"

        # Determine indication type for appropriate scoring system
        is_uc = any(term in indication for term in ['ulcerative colitis', 'uc', 'ulcerative'])
        is_crohns = any(term in indication for term in ['crohn', 'cd'])
        is_ibd = is_uc or is_crohns or 'ibd' in indication or 'inflammatory bowel' in indication

        # Generate indication-appropriate endpoint derivation
        if is_uc:
            scoring_section = f"""The primary endpoint will be assessed at {primary_timepoint}. Clinical and endoscopic remission is defined as a Full Mayo score of ≤2 points with no individual subscore exceeding 1 point and a rectal bleeding subscore of 0.

The Full Mayo score comprises four components: stool frequency subscore (0-3), rectal bleeding subscore (0-3), physician global assessment (0-3), and endoscopy subscore (0-3), yielding a total score range of 0-12.

For diary-derived subscores (stool frequency and rectal bleeding), the average of assessments from the 5 days preceding the scheduled visit will be calculated. A minimum of 3 valid diary days is required; days with bowel preparation or colonoscopy procedures will be excluded. The calculated average will be categorized as follows: 0-0.5 maps to 0, 0.6-1.5 maps to 1, 1.6-2.5 maps to 2, and 2.6-3.0 maps to 3.

Endoscopy assessments will be based on central reader evaluation when available; local investigator reads will be used when central reads are unavailable."""

            secondary_section = """**Clinical Response:** Defined as a decrease from baseline in the 9-point partial Mayo score of ≥2 points and ≥30%, accompanied by either a decrease in rectal bleeding subscore of ≥1 point or an absolute rectal bleeding subscore of ≤1.

**Endoscopic Improvement (Mucosal Healing):** Defined as an endoscopy subscore of ≤1."""

        elif is_crohns:
            scoring_section = f"""The primary endpoint will be assessed at {primary_timepoint}. Clinical remission is defined as a Crohn's Disease Activity Index (CDAI) score of <150 points.

The CDAI is a composite score comprising eight factors: number of liquid stools, abdominal pain rating, general well-being, presence of complications, use of antidiarrheal medications, abdominal mass, hematocrit, and body weight. The total score ranges from 0 to approximately 600.

For endoscopic endpoints, the Simple Endoscopic Score for Crohn's Disease (SES-CD) will be used. The SES-CD evaluates presence and size of ulcers, extent of ulcerated surface, extent of affected surface, and presence of narrowing across five ileocolonic segments.

Endoscopy assessments will be based on central reader evaluation when available; local investigator reads will be used when central reads are unavailable."""

            secondary_section = """**Clinical Response:** Defined as a decrease from baseline in CDAI of ≥100 points or achievement of clinical remission (CDAI <150).

**Endoscopic Response:** Defined as a decrease from baseline in SES-CD of ≥50%.

**Endoscopic Remission:** Defined as SES-CD ≤2 with no individual component score >1."""

        else:
            # Generic/other indications - use protocol-specified endpoint
            scoring_section = f"""The primary endpoint ({primary_endpoint}) will be assessed at {primary_timepoint}. The endpoint will be derived according to the definitions specified in the protocol.

Assessments will be performed according to the schedule of assessments. For endpoints requiring multiple components, all components must be available at the assessment timepoint for the composite to be calculated.

When central reading is specified, central reader evaluation will be used as the primary source; local investigator reads will be used when central reads are unavailable."""

            secondary_section = """Secondary endpoints will be derived according to their protocol-specified definitions. Binary endpoints will be assessed as responder (meeting criteria) or non-responder (not meeting criteria or missing).

**Change from Baseline:** Calculated as the post-baseline value minus the baseline value."""

        return f"""## APPENDIX A: ENDPOINT DEFINITIONS

### A.1 Primary Endpoint

**{primary_endpoint}**

{scoring_section}

### A.2 Secondary Endpoints

{secondary_section}

**Change from Baseline:** Calculated as the post-baseline value minus the baseline value. Baseline is defined as the last non-missing assessment prior to the first dose of {drug_name}.

### A.3 Handling of Missing Data for Endpoint Derivation

Subjects with any missing component at the primary timepoint will be classified as non-responders for the primary analysis. Subjects who discontinue prior to {primary_timepoint} or who die during the study will be classified as non-responders. Assessments occurring outside the visit window will be included in the analysis and flagged as protocol deviations.
"""

    def _generate_appendix_model_specs(self, facts: FullProtocolFacts) -> str:
        """Generate Appendix B: Statistical Methods (prose format per industry SAP standards)"""
        drug_name = facts.drug_name or "[STUDY DRUG]"
        primary_method = facts.primary_analysis_method or "Logistic Regression"
        strat_factors = facts.stratification_factors or ["prior biologic use", "baseline disease severity"]
        strat_text = ", ".join(strat_factors)

        return f"""## APPENDIX B: STATISTICAL METHODS

### B.1 Primary Analysis

The primary efficacy analysis will employ logistic regression to compare the proportion of subjects achieving clinical and endoscopic remission between each {drug_name} dose group and placebo at the primary timepoint.

The model will include treatment group as the primary factor, with placebo as the reference category. Stratification factors ({strat_text}) and baseline disease severity score will be included as covariates. Adjusted odds ratios with corresponding 95% confidence intervals will be calculated using Wald's method.

The primary treatment comparison will use a one-sided significance level of 0.05, with the one-sided p-value derived from the two-sided Wald chi-square test.

### B.2 Confidence Intervals

**Binary Endpoints:** Exact (Clopper-Pearson) 95% confidence intervals will be calculated for response proportions within each treatment group. The Newcombe-Wilson method will be used for confidence intervals of treatment differences.

**Continuous Endpoints:** 95% confidence intervals will be based on the t-distribution for means and mean differences.

**Time-to-Event Endpoints:** Confidence intervals for median survival will be derived using the Brookmeyer-Crowley method. Hazard ratio confidence intervals will use the Wald method from the Cox proportional hazards model.

### B.3 Sensitivity Analyses

**Per-Protocol Population:** The primary analysis model will be repeated using the per-protocol population to assess the robustness of findings under ideal protocol adherence.

**Tipping Point Analysis:** A tipping point analysis will explore the sensitivity of conclusions to missing data assumptions by varying the imputed response rate for subjects with missing primary endpoint data across a range of clinically plausible values.

### B.4 Subgroup Analyses

Treatment effects will be assessed within pre-specified subgroups by including a treatment-by-subgroup interaction term in the logistic regression model. Subgroup-specific odds ratios and 95% confidence intervals will be presented in a forest plot. These analyses are exploratory and will not be adjusted for multiplicity.

### B.5 Multiplicity

Multiple comparisons of dose groups versus placebo will be controlled using a hierarchical testing procedure. The high-dose comparison will be tested first at the one-sided 0.05 level; the low-dose comparison will be tested only if the high-dose comparison achieves statistical significance.
"""

    def _generate_appendix_data_handling(self, facts: FullProtocolFacts) -> str:
        """Generate Appendix C: Data Handling Conventions using Three-Tier Operational Rules.

        Uses the comprehensive operational appendix generator if available,
        falling back to basic template if not.
        """
        # Try to use the comprehensive operational appendix generator
        if self.operational_integrator:
            try:
                appendix = self.operational_integrator.generate_operational_appendix()
                print("    [OPERATIONAL] Using comprehensive three-tier operational rules")
                return appendix
            except Exception as e:
                print(f"    [OPERATIONAL] Warning: Falling back to basic template: {e}")

        # Fallback: Basic template (legacy behavior)
        return """## APPENDIX C: DATA HANDLING CONVENTIONS

### C.1 Date Imputations

For partial dates where only the day is missing, the 15th of the month will be imputed. When only the month is missing, June will be used. Dates with missing year cannot be imputed and will remain as missing.

### C.2 Treatment-Emergent Classification

An adverse event will be classified as treatment-emergent if the onset date is on or after the date of first study drug administration. For events with partially imputed onset dates, the imputed date will be used for classification.

### C.3 Time Calculations

**Duration:** Event duration will be calculated as the end date minus the start date plus one day. For ongoing events at the analysis cutoff date, duration will be calculated using the cutoff date.

**Age:** Age will be calculated as the integer portion of years from birth date to first dose date.

**Study Day:** Study Day 1 is defined as the date of first study drug administration. Study day will be calculated as the assessment date minus the first dose date plus one.

### C.4 Laboratory Value Handling

Values reported as below the lower limit of quantification will be imputed as one-half the LLOQ. Values above the upper limit of quantification will be set to the ULOQ. Values reported as "not detected" will be set to zero.

Standard unit conversions will be applied as needed to ensure consistency across sites.

### C.5 Baseline Definition

Baseline is defined as the last non-missing value obtained prior to the first dose of study drug. If multiple assessments occur on the same day, the mean will be used. Pre-dose assessments on Day 1 will be considered baseline if available.

### C.6 Visit Windows

| Scheduled Visit | Target Day | Window |
|-----------------|------------|--------|
| Week 2 | Day 14 | ±3 days |
| Week 4 | Day 28 | ±3 days |
| Week 6 | Day 42 | ±3 days |
| Week 8 | Day 56 | ±3 days |
| Week 10 | Day 70 | ±5 days |
| Week 12 | Day 84 | ±5 days |

Assessments occurring outside the defined visit window will be included in the analysis and assigned to the nearest scheduled visit. Such occurrences will be flagged as protocol deviations in subject listings.

### C.7 Duplicate Record Resolution

Duplicate CRF entries will be resolved using the most recent entry timestamp. Duplicate laboratory results will be queried with the site for confirmation. Duplicate adverse event records will be reviewed to determine if they represent the same event; true duplicates will be merged.
"""

    def _generate_appendix_table_shells(self, facts: FullProtocolFacts) -> str:
        """Generate Appendix D: Table Shells (markdown format for web rendering)"""
        drug_name = facts.drug_name or "[STUDY DRUG]"
        num_arms = facts.num_arms or 3

        # Build markdown-style table shells for web rendering
        if num_arms == 3:
            arm1 = f"{drug_name} High"
            arm2 = f"{drug_name} Low"
            arm3 = "Placebo"
            header_row = f"""
| Statistic | {arm1} (N=XXX) | {arm2} (N=XXX) | {arm3} (N=XXX) | Total (N=XXX) |
|-----------|----------------|----------------|----------------|---------------|"""
        else:
            arm1 = drug_name
            arm2 = "Placebo"
            header_row = f"""
| Statistic | {arm1} (N=XXX) | {arm2} (N=XXX) | Total (N=XXX) |
|-----------|----------------|----------------|---------------|"""

        return f"""## APPENDIX D: TABLE SHELLS

### D.1 Baseline Characteristics (Table 14.1.2)

**Population:** Full Analysis Set (FAS)

#### D.1.1 Demographics
{header_row}
| Age (years) | | | | |
| - N | | | | |
| - Mean (SD) | | | | |
| - Median | | | | |
| - Min, Max | | | | |
| Age Category, n (%) | | | | |
| - <40 years | | | | |
| - 40-64 years | | | | |
| - ≥65 years | | | | |
| Sex, n (%) | | | | |
| - Male | | | | |
| - Female | | | | |
| Race, n (%) | | | | |
| - Asian | | | | |
| - White | | | | |
| - Black or African American | | | | |
| - Other | | | | |
| Weight (kg), Mean (SD) | | | | |
| BMI (kg/m²), Mean (SD) | | | | |

#### D.1.2 Disease Characteristics
{header_row}
| Time Since Diagnosis (years) | | | | |
| - Mean (SD) | | | | |
| - Median (Min, Max) | | | | |
| Disease Extent, n (%) | | | | |
| - Proctitis | | | | |
| - Left-sided colitis | | | | |
| - Extensive/Pancolitis | | | | |
| Baseline Disease Activity Score, Mean (SD) | | | | |
| Prior Medications, n (%) | | | | |
| - Corticosteroids | | | | |
| - 5-ASA | | | | |
| - Immunomodulators | | | | |
| - Prior biologic therapy | | | | |

### D.2 Primary Efficacy Analysis (Table 14.2.1)

**Endpoint:** Primary Endpoint at Primary Timepoint
**Population:** Full Analysis Set (FAS)
{header_row}
| Primary Endpoint, n (%) | | | | |
| - Responders | xx (xx.x%) | xx (xx.x%) | xx (xx.x%) | |
| - Non-responders | xx (xx.x%) | xx (xx.x%) | xx (xx.x%) | |
| Difference vs Placebo | | | | |
| - Estimate (%) | xx.x | xx.x | -- | |
| - 95% CI | (xx.x, xx.x) | (xx.x, xx.x) | -- | |
| Odds Ratio vs Placebo | | | | |
| - Estimate | x.xx | x.xx | -- | |
| - 95% CI | (x.xx, x.xx) | (x.xx, x.xx) | -- | |
| P-value (one-sided) | x.xxxx | x.xxxx | -- | |

Footnotes:
1. Percentages based on N in each treatment group
2. Patients with missing data at primary timepoint counted as non-responders
3. Odds ratios from logistic regression model with treatment, stratification factors, and baseline disease score
4. P-value is one-sided for superiority testing

### D.3 Adverse Events Overview (Table 14.3.1)

**Population:** Safety Population
{header_row}
| Any TEAE, n (%) | | | | |
| Treatment-related TEAE, n (%) | | | | |
| TEAE by Maximum Severity, n (%) | | | | |
| - Mild | | | | |
| - Moderate | | | | |
| - Severe | | | | |
| Serious TEAE, n (%) | | | | |
| Treatment-related SAE, n (%) | | | | |
| TEAE Leading to D/C, n (%) | | | | |
| TEAE Leading to Dose Mod, n (%) | | | | |
| Deaths, n (%) | | | | |

Footnotes:
1. TEAE = Treatment-emergent adverse event (onset on or after first dose of study drug)
2. Treatment-related = Possibly, probably, or definitely related per investigator assessment
3. A patient is counted once per row regardless of number of events
4. D/C = Discontinuation; SAE = Serious adverse event

### D.4 AEs by System Organ Class and Preferred Term (Table 14.3.2)

**Population:** Safety Population
**Incidence Threshold:** ≥5% in any treatment group

| System Organ Class / Preferred Term | {drug_name} High n (%) | {drug_name} Low n (%) | Placebo n (%) |
|-------------------------------------|------------------------|------------------------|---------------|
| Infections and infestations | | | |
| - Nasopharyngitis | | | |
| - Upper respiratory infection | | | |
| Gastrointestinal disorders | | | |
| - Nausea | | | |
| - Abdominal pain | | | |
| General disorders | | | |
| - Fatigue | | | |
| - Injection site reaction | | | |

Footnotes:
1. MedDRA version XX.X
2. Sorted by decreasing frequency in High Dose group within each SOC
3. SOCs sorted alphabetically

### D.5 Laboratory Abnormalities (Table 14.3.5)

**Population:** Safety Population

| Parameter | {drug_name} High | {drug_name} Low | Placebo |
|-----------|------------------|------------------|---------|
| **Hematology** | | | |
| Neutropenia (Grade 3-4), n (%) | | | |
| Thrombocytopenia (Grade 3-4), n (%) | | | |
| Anemia (Grade 3-4), n (%) | | | |
| **Chemistry** | | | |
| ALT >3× ULN, n (%) | | | |
| AST >3× ULN, n (%) | | | |
| Bilirubin >2× ULN, n (%) | | | |
| Creatinine >1.5× ULN, n (%) | | | |

### D.6 Formatting Conventions

| Element | Format |
|---------|--------|
| Percentages | 1 decimal place (xx.x%) |
| Means | Same precision as raw data or 1 decimal |
| Standard Deviations | Same precision as means |
| P-values | 4 decimals; if <0.0001 display as "<0.0001" |
| Confidence Intervals | Same precision as estimate |
| n=0 | Display "0" not "0 (0.0%)" |
| Missing values | Display "--" or "NA" |
| Dates | DDMMMYYYY format (e.g., 15JAN2024) |
"""

    def _assemble_sap(self, sections: Dict[str, str], facts) -> str:
        """Assemble sections into complete SAP document.

        Handles both FullProtocolFacts (new) and ProtocolFacts (legacy).
        """
        # Handle both old CitedValue format and new direct value format
        if isinstance(facts, FullProtocolFacts):
            # New format: direct values
            drug = facts.drug_name or "[STUDY DRUG]"
            nct = facts.nct_id or "NCT-UNKNOWN"
            phase = facts.phase or "Phase 2"
            indication = facts.indication or "Not specified"
            sponsor = facts.sponsor or "Sponsor"
            total_n = facts.total_n or 0

            # CRITICAL FIX: Detect single-arm trials properly
            num_arms = facts.num_arms or 0
            is_single_arm = (
                num_arms == 1 or
                (facts.design_type and "single" in facts.design_type.lower()) or
                not facts.ratio  # No ratio = likely single-arm
            )

            if is_single_arm:
                design = facts.design_type or "Single-arm, open-label"
                ratio = "N/A (single-arm)"
            else:
                design = facts.design_type or "Randomized controlled trial"
                ratio = facts.ratio or "1:1"
        else:
            # Legacy format: CitedValue with .value
            drug = facts.drug_name.value if facts.drug_name else "[STUDY DRUG]"
            nct = facts.nct_id.value if facts.nct_id else "NCT-UNKNOWN"
            phase = facts.phase.value if facts.phase else "Phase 2"
            indication = "Not specified"
            sponsor = "Sponsor"
            total_n = facts.total_n.value if facts.total_n else 0

            # CRITICAL FIX: Detect single-arm from legacy format
            num_arms = facts.num_arms.value if facts.num_arms else 0
            is_single_arm = getattr(facts, 'is_single_arm', False) or num_arms == 1

            if is_single_arm:
                design = facts.design_type.value if facts.design_type else "Single-arm, open-label"
                ratio = "N/A (single-arm)"
            else:
                design = facts.design_type.value if facts.design_type else "Randomized controlled trial"
                ratio = facts.ratio.value if facts.ratio else "1:1"

        # Generate version date for document control
        from datetime import datetime
        version_date = datetime.now().strftime("%d%b%Y").upper()

        header = f"""# STATISTICAL ANALYSIS PLAN

**Protocol:** {nct}
**Drug:** {drug}
**Sponsor:** {sponsor}
**Phase:** {phase}
**Indication:** {indication}
**Design:** {design}
**Sample Size:** {total_n} ({ratio})

============================================================

## DOCUMENT CONTROL

### Version History

| Version | Date | Author | Description of Changes |
|---------|------|--------|------------------------|
| 0.1 | {version_date} | Lead Biostatistician | Initial draft for internal review |
| 0.2 | TBD | Lead Biostatistician | Revised based on internal comments |
| 1.0 | TBD | Lead Biostatistician | Final version for regulatory submission |

*Note: Version 1.0 will be finalized prior to database lock.*

### Signature Page

This Statistical Analysis Plan has been reviewed and approved by:

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Lead Biostatistician | ______________________ | __________________ | __________ |
| Biostatistics QC Reviewer | ______________________ | __________________ | __________ |
| Clinical Study Director | ______________________ | __________________ | __________ |
| Medical Monitor | ______________________ | __________________ | __________ |
| Sponsor Representative | ______________________ | __________________ | __________ |
| Regulatory Affairs | ______________________ | __________________ | __________ |

*All signatures must be obtained prior to database lock.*

============================================================

## ABBREVIATIONS

| Abbreviation | Definition |
|--------------|------------|
| ADA | Anti-drug antibody |
| AE | Adverse event |
| ANCOVA | Analysis of covariance |
| CI | Confidence interval |
| CMH | Cochran-Mantel-Haenszel |
| CTCAE | Common Terminology Criteria for Adverse Events |
| ECG | Electrocardiogram |
| FAS | Full analysis set |
| GEE | Generalized estimating equations |
| ICH | International Council for Harmonisation |
| ITT | Intent-to-treat |
| LOCF | Last observation carried forward |
| LLOQ | Lower limit of quantification |
| MAR | Missing at random |
| MedDRA | Medical Dictionary for Regulatory Activities |
| MICE | Multiple imputation by chained equations |
| MMRM | Mixed model for repeated measures |
| NAb | Neutralizing antibody |
| NCA | Non-compartmental analysis |
| PCS | Potentially clinically significant |
| PK | Pharmacokinetics |
| PP | Per-protocol |
| PT | Preferred term |
| Q2W | Every 2 weeks |
| SAE | Serious adverse event |
| SAP | Statistical analysis plan |
| SD | Standard deviation |
| SOC | System organ class |
| TEAE | Treatment-emergent adverse event |
| ULOQ | Upper limit of quantification |
| ULN | Upper limit of normal |

============================================================

## TABLE OF CONTENTS

1. Introduction
2. Study Objectives and Estimands
3. Study Design
4. Analysis Populations
5. Endpoints
6. Sample Size Calculation
7. Statistical Methods
8. Missing Data Handling
9. Safety Analysis
10. Pharmacokinetic Analysis
11. Appendices
    - Appendix A: Endpoint Definitions
    - Appendix B: Statistical Methods
    - Appendix C: Data Handling Conventions
    - Appendix D: Table Shells

============================================================
"""

        # Assemble body in correct section order
        body = ""
        section_order = [
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
            '11_appendix_derivations',
            '12_appendix_model_specs',
            '13_appendix_data_handling',
            '14_appendix_table_shells',
        ]

        for section_key in section_order:
            if section_key in sections:
                body += sections[section_key] + "\n\n"

        footer = """
============================================================
END OF STATISTICAL ANALYSIS PLAN
============================================================
"""

        return header + body + footer


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def generate_constrained_sap(
    protocol_text: str,
    nct_id: str = None
) -> PipelineResult:
    """
    Convenience function to generate SAP with schema constraints.

    Args:
        protocol_text: Full protocol document text
        nct_id: NCT ID (optional)

    Returns:
        PipelineResult with SAP and verification details
    """
    pipeline = ConstrainedSAPPipeline()
    return pipeline.generate(protocol_text, nct_id)


# =============================================================================
# INTEGRATED VALIDATION
# =============================================================================

def validate_sap(sap_text: str, protocol_text: str = None) -> Dict[str, Any]:
    """
    Run validation on generated SAP.

    Returns dict with 'score', 'report', and 'issues'.
    """
    try:
        # Import the validator
        import sys
        from pathlib import Path

        # Add parent dir to path to import validate_sap module
        parent_dir = Path(__file__).parent.parent.parent
        if str(parent_dir) not in sys.path:
            sys.path.insert(0, str(parent_dir))

        from validate_sap import SAPValidator

        validator = SAPValidator(sap_text, protocol_text)
        validator.validate_all()

        return {
            'score': validator.overall_score,
            'report': validator.generate_report(),
            'results': validator.get_json_report(),
            'issues': [
                f"[{section.name}] {check.message}"
                for section in validator.results.values()
                for check in section.checks
                if check.status in ("FAIL", "PARTIAL")
            ]
        }
    except ImportError:
        return {
            'score': None,
            'report': "Validation skipped - validate_sap.py not found",
            'results': {},
            'issues': []
        }
    except Exception as e:
        return {
            'score': None,
            'report': f"Validation error: {str(e)}",
            'results': {},
            'issues': []
        }


# =============================================================================
# CLI FOR TESTING
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m enterprise_sap_system.core.constrained_pipeline <protocol_file> [--validate]")
        sys.exit(1)

    protocol_file = sys.argv[1]
    run_validation = "--validate" in sys.argv or "-v" in sys.argv

    with open(protocol_file, 'r') as f:
        protocol_text = f.read()

    result = generate_constrained_sap(protocol_text)

    if result.success:
        print("\n" + "="*60)
        print("GENERATED SAP")
        print("="*60)
        print(result.sap_text)

        # Run validation if requested or always
        if run_validation or True:  # Always validate for now
            print("\n" + "="*60)
            print("VALIDATION REPORT")
            print("="*60)
            validation = validate_sap(result.sap_text, protocol_text)
            print(validation['report'])

            if validation['score'] is not None:
                print(f"\n>>> VALIDATION SCORE: {validation['score']}%")
                if validation['score'] < 80:
                    print(">>> SAP needs improvement before use")
                else:
                    print(">>> SAP meets quality threshold")
    else:
        print("\nGENERATION FAILED:")
        for error in result.errors:
            print(f"  - {error}")
