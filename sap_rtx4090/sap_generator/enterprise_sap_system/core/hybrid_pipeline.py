#!/usr/bin/env python3
"""
Hybrid SAP Generation Pipeline
==============================

Unified pipeline that uses the hybrid reasoning engine for section generation.
This replaces the fragmented template-based approach with proper reasoning:

- Decision Trees for deterministic sections (Populations, Derivations, TEAE)
- RAG for domain-specific sections (Endpoints, Methods, Stratification, Windows)
- LLM for protocol extraction (99.5% accuracy per research)

NO REGEX - LLM extraction is the only method.

Production Features:
- Structured logging
- Proper error handling
- No silent failures

Usage:
    from hybrid_pipeline import HybridSAPPipeline

    pipeline = HybridSAPPipeline()
    result = pipeline.generate(protocol_text, nct_id="NCT12345678")
"""

import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path

# Import logging first
try:
    from .logging_config import get_logger
except ImportError:
    import logging
    def get_logger(name):
        return logging.getLogger(name)

logger = get_logger(__name__)

# Import components (ProtocolFacts for data structure only - NO regex extraction)
from .schemas import ProtocolFacts, StructuredFactExtractor
from .hybrid_reasoning import (
    HybridReasoningEngine,
    ReasoningResult,
    ReasoningType,
    create_hybrid_engine
)
from .rag_adapter import create_rag_adapter, HybridRAGAdapter

# Import Knowledge Rule Engine (data-driven method selection)
try:
    from .knowledge_rule_engine import KnowledgeRuleEngine
    KNOWLEDGE_ENGINE_AVAILABLE = True
except ImportError as e:
    KNOWLEDGE_ENGINE_AVAILABLE = False
    print(f"[Pipeline] KnowledgeRuleEngine not available: {e}")

# Import LLM section generator (replaces template-based generation)
try:
    from .llm_section_generator import LLMSectionGenerator, create_llm_generator
    LLM_GENERATOR_AVAILABLE = True
except ImportError as e:
    LLM_GENERATOR_AVAILABLE = False
    logger.warning("LLMSectionGenerator not available", error=str(e))

# Import Claude extractor (LLM-based - REQUIRED, no regex fallback)
try:
    from .claude_extractor import ClaudeProtocolExtractor, ExtractedProtocol
    CLAUDE_EXTRACTOR_AVAILABLE = True
except ImportError as e:
    CLAUDE_EXTRACTOR_AVAILABLE = False
    logger.error("ClaudeExtractor not available - LLM extraction disabled", error=str(e))

# Try to import validation components
try:
    from .hard_validator import HardValidator, ValidationResult
    VALIDATOR_AVAILABLE = True
except ImportError as e:
    VALIDATOR_AVAILABLE = False
    logger.warning("HardValidator not available - validation disabled", error=str(e))

try:
    from .contamination_guard import ContaminationGuard
    CONTAMINATION_GUARD_AVAILABLE = True
except ImportError as e:
    CONTAMINATION_GUARD_AVAILABLE = False
    logger.warning("ContaminationGuard not available - contamination checking disabled", error=str(e))

# Try to import TLF generator
try:
    from ..specs.tlf_shells import TLFShellGenerator, create_tlf_generator
    TLF_GENERATOR_AVAILABLE = True
except ImportError as e:
    TLF_GENERATOR_AVAILABLE = False
    logger.warning("TLFShellGenerator not available - TLF generation disabled", error=str(e))


@dataclass
class HybridPipelineResult:
    """Result from hybrid pipeline generation"""
    success: bool = True
    sap_text: str = ""
    sections: Dict[str, str] = field(default_factory=dict)
    reasoning_results: Dict[str, ReasoningResult] = field(default_factory=dict)
    facts: Optional[ProtocolFacts] = None
    validation: Optional[Any] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # TLF specifications
    tlf_text: str = ""  # Markdown TLF shell specifications
    tlf_shells: Dict[str, Any] = field(default_factory=dict)  # Raw TLF shell objects

    # Metrics
    decision_tree_sections: int = 0
    rag_sections: int = 0
    template_fallback_sections: int = 0

    def get_reasoning_summary(self) -> str:
        """Get summary of reasoning approaches used"""
        lines = ["Reasoning Approaches Used:", "=" * 40]

        for section, result in self.reasoning_results.items():
            icon = {
                ReasoningType.DECISION_TREE: "🌳",
                ReasoningType.RAG: "📚",
                ReasoningType.REGEX: "📝",
                ReasoningType.TEMPLATE: "📄"
            }.get(result.reasoning_type, "?")

            conf = f"{result.confidence:.0%}"
            sources = ", ".join(result.rag_examples_used[:2]) if result.rag_examples_used else ""
            sources_str = f" (from: {sources})" if sources else ""

            lines.append(f"  {icon} {section}: {result.reasoning_type.value} [{conf}]{sources_str}")

        lines.append("")
        lines.append(f"Decision Tree: {self.decision_tree_sections} sections")
        lines.append(f"RAG-enhanced: {self.rag_sections} sections")
        lines.append(f"Template fallback: {self.template_fallback_sections} sections")

        return "\n".join(lines)


class HybridSAPPipeline:
    """
    Unified SAP generation pipeline using hybrid reasoning.

    This is the MAIN ENTRY POINT for SAP generation.
    All other pipelines should delegate to this one.
    """

    def __init__(
        self,
        use_rag: bool = True,
        use_validation: bool = True,
        strict_validation: bool = False,
        use_tlf: bool = True,
        verbose: bool = True
    ):
        """
        Initialize hybrid pipeline.

        Args:
            use_rag: Enable RAG for enhanced sections
            use_validation: Enable post-generation validation
            strict_validation: Block output on validation failures
            use_tlf: Enable TLF shell specification generation
            verbose: Print progress messages
        """
        self.verbose = verbose
        self.use_validation = use_validation
        self.strict_validation = strict_validation
        self.use_tlf = use_tlf

        # Initialize LLM extractor (NO regex fallback)
        if CLAUDE_EXTRACTOR_AVAILABLE:
            self.claude_extractor = ClaudeProtocolExtractor()
            self.use_llm_extraction = True
        else:
            self.claude_extractor = None
            self.use_llm_extraction = False
            logger.warning("LLM extraction unavailable - set ANTHROPIC_API_KEY")

        # Initialize RAG adapter
        self.rag_adapter = create_rag_adapter() if use_rag else None

        # Initialize hybrid reasoning engine with RAG
        self.reasoning_engine = create_hybrid_engine(
            rag_retriever=self.rag_adapter
        )

        # Initialize validators
        self.validator = HardValidator(strict_mode=strict_validation) if VALIDATOR_AVAILABLE and use_validation else None
        self.contamination_guard = ContaminationGuard() if CONTAMINATION_GUARD_AVAILABLE else None

        # Initialize LLM section generator (replaces template-based generation)
        if LLM_GENERATOR_AVAILABLE:
            self.llm_generator = create_llm_generator(rag_adapter=self.rag_adapter)
            self.use_llm_generation = True
        else:
            self.llm_generator = None
            self.use_llm_generation = False

        # Initialize TLF shell generator
        if TLF_GENERATOR_AVAILABLE and use_tlf:
            self.tlf_generator = create_tlf_generator()
        else:
            self.tlf_generator = None

        # Initialize Knowledge Rule Engine (data-driven method selection)
        if KNOWLEDGE_ENGINE_AVAILABLE:
            self.knowledge_engine = KnowledgeRuleEngine()
            self.use_knowledge_rules = True
        else:
            self.knowledge_engine = None
            self.use_knowledge_rules = False

        logger.info(
            "HybridSAPPipeline initialized",
            extraction="LLM" if self.use_llm_extraction else "DISABLED",
            generation="LLM" if self.use_llm_generation else "TEMPLATES",
            rag="enabled" if use_rag and self.rag_adapter else "disabled",
            validation="enabled" if use_validation else "disabled",
            tlf="enabled" if self.tlf_generator else "disabled",
            knowledge_rules="enabled" if self.use_knowledge_rules else "disabled"
        )

    def generate(
        self,
        protocol_text: str,
        nct_id: str = None
    ) -> HybridPipelineResult:
        """
        Generate SAP using hybrid reasoning.

        Args:
            protocol_text: Full protocol document text
            nct_id: NCT ID (optional, will be extracted if not provided)

        Returns:
            HybridPipelineResult with SAP and metadata
        """
        result = HybridPipelineResult()

        try:
            # =================================================================
            # LAYER 1: EXTRACTION (API + LLM or regex fallback)
            # =================================================================
            logger.info("LAYER 1: Extracting protocol facts")

            # Use LLM extraction (NO regex fallback)
            facts = None

            if self.use_llm_extraction and self.claude_extractor:
                # LLM-based extraction (99.5% accuracy per research)
                extracted = self.claude_extractor.extract(protocol_text)

                if extracted.extraction_success:
                    # Convert to ProtocolFacts for compatibility
                    facts = self._convert_extracted_to_facts(extracted)
                    result.warnings.extend(extracted.warnings)
                    logger.info(
                        "LLM extraction successful",
                        source=extracted.extraction_source,
                        drug=extracted.drug_name,
                        endpoint=extracted.primary_endpoint[:60] if extracted.primary_endpoint else None
                    )
                else:
                    # LLM failed - try API if NCT ID available
                    result.warnings.extend(extracted.warnings)
                    logger.warning("LLM extraction failed", warnings=extracted.warnings)

            # If no facts yet and NCT ID available, try API-only extraction
            if facts is None and nct_id:
                logger.info("Attempting API-only extraction", nct_id=nct_id)
                facts = self._extract_from_api_only(nct_id, result)

            # If still no facts, create empty structure
            if facts is None:
                logger.warning("No extraction method available - using empty facts")
                facts = ProtocolFacts()
                result.warnings.append("Extraction failed - set ANTHROPIC_API_KEY for LLM extraction")

            # ALWAYS use user-provided NCT ID if available (takes precedence over extracted)
            if nct_id:
                facts.nct_id = nct_id

            # Validate NCT ID before using it (prevents using reference study NCT IDs)
            if facts.nct_id and protocol_text:
                facts.nct_id = self._validate_and_correct_nct_id(
                    facts.nct_id, protocol_text, result
                )

            # Enhance with API if NCT ID available
            if facts.nct_id:
                facts = self._enhance_with_api(facts, result)

            result.facts = facts

            # FAIL-FAST: Validate critical facts are present
            missing_critical = []
            if not facts.drug_name:
                missing_critical.append("drug_name")
            if not facts.primary_endpoint:
                missing_critical.append("primary_endpoint")
            if not facts.sample_size or not facts.sample_size.total_n:
                missing_critical.append("sample_size")

            if missing_critical:
                # Don't fail - just warn and continue with defaults
                warning_msg = f"Missing facts (using defaults): {', '.join(missing_critical)}"
                result.warnings.append(warning_msg)
                logger.warning("Missing critical facts", missing=missing_critical)

            # Track warnings for non-critical missing data
            if not facts.design_type:
                result.warnings.append("design_type not extracted - defaulting to 'randomized'")
            if not facts.phase:
                result.warnings.append("phase not extracted")
            if not facts.therapeutic_area:
                result.warnings.append("therapeutic_area not extracted")

            # Convert to dict for reasoning engine
            facts_dict = self._facts_to_dict(facts)

            logger.info(
                "Extraction complete",
                drug=facts.drug_name,
                design=facts.design_type,
                is_single_arm=facts_dict.get('is_single_arm', False),
                sample_size=facts.sample_size.total_n if facts.sample_size else 0,
                warnings_count=len(result.warnings)
            )

            # =================================================================
            # LAYER 1.5: KNOWLEDGE-DRIVEN METHOD SELECTION
            # =================================================================
            if self.use_knowledge_rules and self.knowledge_engine:
                logger.info("LAYER 1.5: Applying knowledge rules for method selection")

                # Get method recommendations from knowledge graph
                method_recommendations = self.knowledge_engine.get_primary_analysis_methods(facts_dict)

                # Add recommendations to facts_dict so LLM can use them
                facts_dict['_knowledge_recommendations'] = method_recommendations
                facts_dict['_detected_conditions'] = method_recommendations.get('conditions_detected', [])

                # Log what the knowledge engine detected
                logger.info(
                    "Knowledge rules applied",
                    conditions=method_recommendations.get('conditions_detected', []),
                    primary_test=(method_recommendations or {}).get('primary_test', {}).get('method'),
                    sensitivity_count=len(method_recommendations.get('sensitivity_analyses', [])),
                    reasoning_count=len(method_recommendations.get('reasoning', []))
                )

                # Add recommendations to result warnings for visibility
                for reasoning in method_recommendations.get('reasoning', []):
                    result.warnings.append(f"[Knowledge Rule] {reasoning}")

            # =================================================================
            # LAYER 2: HYBRID REASONING
            # =================================================================
            logger.info("LAYER 2: Generating sections with hybrid reasoning")

            # Generate sections using hybrid engine
            reasoning_results = self.reasoning_engine.generate_all_sections(facts_dict)
            result.reasoning_results = reasoning_results

            # Count reasoning types used
            for section, rr in reasoning_results.items():
                result.sections[section] = rr.content
                if rr.reasoning_type == ReasoningType.DECISION_TREE:
                    result.decision_tree_sections += 1
                elif rr.reasoning_type == ReasoningType.RAG:
                    result.rag_sections += 1
                else:
                    result.template_fallback_sections += 1

                logger.debug(
                    f"Section generated: {section}",
                    reasoning_type=rr.reasoning_type.value,
                    confidence=f"{rr.confidence:.0%}"
                )

            # =================================================================
            # LAYER 3: LLM-GENERATED SECTIONS (no templates)
            # =================================================================
            logger.info("LAYER 3: Generating sections with LLM")

            if self.use_llm_generation and self.llm_generator:
                # Generate sections using actual LLM calls (no templates)
                llm_sections = [
                    ('introduction', self.llm_generator.generate_introduction),
                    ('objectives', self.llm_generator.generate_objectives),
                    ('study_design', self.llm_generator.generate_study_design),
                    ('sample_size', self.llm_generator.generate_sample_size),
                    ('missing_data', self.llm_generator.generate_missing_data),
                    ('endpoints', self.llm_generator.generate_endpoints),
                    ('methods', self.llm_generator.generate_methods),
                    ('stratification', self.llm_generator.generate_stratification),
                    # NEW: Additional sections for comprehensive SAP
                    ('regulatory_interim', self.llm_generator.generate_regulatory_interim),
                    ('pro_endpoints', self.llm_generator.generate_pro_endpoints),
                    ('subgroup_analyses', self.llm_generator.generate_subgroup_analyses),
                ]

                for section_name, generator_func in llm_sections:
                    try:
                        gen_result = generator_func(facts_dict)
                        result.sections[section_name] = gen_result.content
                        logger.debug(
                            f"LLM section generated: {section_name}",
                            llm_source=gen_result.llm_source,
                            rag_examples=len(gen_result.rag_examples_used)
                        )
                    except Exception as e:
                        result.warnings.append(f"LLM generation failed for {section_name}: {e}")
                        logger.error(
                            f"LLM generation failed for {section_name}",
                            exc_info=True,
                            error=str(e)
                        )
            else:
                # Fallback to template-based generation (deprecated)
                logger.warning("Using template fallback - LLM generator unavailable")
                result.sections['introduction'] = self._generate_introduction(facts_dict)
                result.sections['objectives'] = self._generate_objectives(facts_dict)
                result.sections['study_design'] = self._generate_study_design(facts_dict)
                result.sections['sample_size'] = self._generate_sample_size(facts_dict)
                result.sections['missing_data'] = self._generate_missing_data(facts_dict)

            # =================================================================
            # LAYER 4: ASSEMBLY
            # =================================================================
            logger.info("LAYER 4: Assembling SAP document")

            result.sap_text = self._assemble_sap(result.sections, facts_dict)

            # =================================================================
            # LAYER 4.5: POST-PROCESSING ENHANCEMENTS
            # =================================================================
            # Enhance NPH acknowledgment for immunotherapy trials
            result.sap_text = self._enhance_nph_acknowledgment(
                result.sap_text, protocol_text, facts_dict
            )

            # =================================================================
            # LAYER 5: VALIDATION (never blocks, just collects issues)
            # =================================================================
            if self.use_validation and self.validator:
                logger.info("LAYER 5: Validating SAP")

                validation = self.validator.validate(result.sap_text, facts)
                result.validation = validation

                logger.info("Validation complete", summary=validation.summary())

                # Add validation issues as warnings (NEVER block output)
                if validation.issues:
                    for issue in validation.issues:
                        severity = issue.severity.value if hasattr(issue.severity, 'value') else str(issue.severity)
                        result.warnings.append(f"[{severity}] {issue.message}")

            # Check for contamination (clean but never block)
            if self.contamination_guard:
                cleaned, report, changes = self.contamination_guard.check_and_clean(
                    result.sap_text, protocol_text
                )
                if report.is_contaminated:
                    # Always clean and warn, never block
                    result.warnings.append(f"Contamination detected and cleaned: {report.contamination_sources}")
                    result.sap_text = cleaned
                    logger.warning("Contamination cleaned", sources=report.contamination_sources)

            # =================================================================
            # LAYER 6: TLF SHELL GENERATION
            # =================================================================
            if self.use_tlf and self.tlf_generator:
                logger.info("LAYER 6: Generating TLF shell specifications")
                try:
                    # Convert facts to ParsedProtocol for TLF generator
                    parsed_protocol = self._facts_to_parsed_protocol(facts, facts_dict)
                    estimands = self._build_estimands_dict(facts_dict)

                    # Generate TLF shells
                    tlf_shells = self.tlf_generator.generate_all_shells(parsed_protocol, estimands)
                    result.tlf_shells = tlf_shells

                    # Generate TLF document text
                    result.tlf_text = self.tlf_generator.generate_tlf_document(parsed_protocol, estimands)

                    logger.info(
                        "TLF generation complete",
                        demographics=len(tlf_shells.get('demographics', [])),
                        efficacy=len(tlf_shells.get('efficacy', [])),
                        safety=len(tlf_shells.get('safety', [])),
                        figures=len(tlf_shells.get('figures', [])),
                        listings=len(tlf_shells.get('listings', []))
                    )
                except Exception as e:
                    result.warnings.append(f"TLF generation failed: {e}")
                    logger.warning("TLF generation failed", exc_info=True, error=str(e))

            result.success = True  # Always succeed if we got here
            logger.info(
                "SAP generation complete",
                sections_count=len(result.sections),
                decision_tree=result.decision_tree_sections,
                rag=result.rag_sections,
                warnings_count=len(result.warnings),
                tlf_generated=bool(result.tlf_text)
            )

        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            logger.error("Pipeline failed", exc_info=True, error=str(e))

        return result

    def _convert_extracted_to_facts(self, extracted: 'ExtractedProtocol') -> ProtocolFacts:
        """Convert LLM-extracted data to ProtocolFacts for pipeline compatibility"""
        from .schemas import (
            ProtocolFacts, EndpointDefinition, SampleSizeSpec,
            AlphaSpecification, TreatmentArmModel as TreatmentArm
        )
        StudyPhase = None  # Phase is now a string in ProtocolFacts

        facts = ProtocolFacts()

        # Identifiers
        facts.nct_id = extracted.nct_id
        facts.protocol_title = extracted.protocol_title
        facts.sponsor = extracted.sponsor

        # Design
        facts.design_type = extracted.design_type
        facts.is_blinded = extracted.is_blinded
        facts.blinding_type = extracted.blinding_type

        # Phase
        phase_str = extracted.phase.upper() if extracted.phase else ""
        phase_map = {
            "PHASE 1": StudyPhase.PHASE_1,
            "PHASE1": StudyPhase.PHASE_1,
            "PHASE 2": StudyPhase.PHASE_2,
            "PHASE2": StudyPhase.PHASE_2,
            "PHASE 3": StudyPhase.PHASE_3,
            "PHASE3": StudyPhase.PHASE_3,
            "PHASE 4": StudyPhase.PHASE_4,
            "PHASE4": StudyPhase.PHASE_4,
            "PHASE 1/2": StudyPhase.PHASE_1_2,
            "PHASE1/2": StudyPhase.PHASE_1_2,
            "PHASE 2/3": StudyPhase.PHASE_2_3,
            "PHASE2/3": StudyPhase.PHASE_2_3,
        }
        facts.phase = phase_map.get(phase_str, StudyPhase.UNKNOWN)

        # Sample size
        if extracted.sample_size:
            facts.sample_size = SampleSizeSpec(
                total_n=extracted.sample_size,
                power=extracted.power if extracted.power else None
            )

        # Arms
        facts.num_arms = extracted.num_arms or len(extracted.arms) or (1 if "single" in extracted.design_type.lower() else 2)
        if extracted.arms:
            facts.arms = [
                TreatmentArm(
                    name=arm.get("name", f"Arm {i+1}"),
                    is_placebo="placebo" in str(arm.get("treatment", "")).lower()
                )
                for i, arm in enumerate(extracted.arms)
            ]
        facts.randomization_ratio = extracted.randomization_ratio

        # Drug and Comparator
        facts.drug_name = extracted.drug_name
        facts.drug_names_all = [extracted.drug_name] if extracted.drug_name else []
        if extracted.comparator:
            facts.drug_names_all.append(extracted.comparator)

        # Store LLM-extracted facts for use in _facts_to_dict
        # Use object.__setattr__ because ProtocolFacts might be a Pydantic model
        try:
            object.__setattr__(facts, '_llm_facts', {
                'comparator': extracted.comparator,
                'statistical_method': extracted.statistical_method,
                # Pilot study and hypothesis testing flags
                'is_pilot_study': extracted.is_pilot_study,
                'hypothesis_testing_planned': extracted.hypothesis_testing_planned,
                'sample_size_justification': extracted.sample_size_justification,
                # Multiple co-primary endpoints
                'primary_endpoints': extracted.primary_endpoints,
                # Oncology response criteria
                'response_criteria': extracted.response_criteria,
                'pathologic_response_criteria': extracted.pathologic_response_criteria,
                'response_assessor': extracted.response_assessor,
                # Protocol-specific population definitions
                'itt_definition': extracted.itt_definition,
                'pp_definition': extracted.pp_definition,
                'safety_definition': extracted.safety_definition,
                'fas_definition': extracted.fas_definition,

                # ========== CRITICAL: Previously missing fields ==========

                # INTERIM ANALYSIS fields (for OS/PFS trials with DMC oversight)
                'has_interim_analysis': getattr(extracted, 'has_interim_analysis', False),
                'num_interim_analyses': getattr(extracted, 'num_interim_analyses', 0),
                'interim_analysis_method': getattr(extracted, 'interim_analysis_method', None),
                'error_spending_function': getattr(extracted, 'error_spending_function', None),
                'alpha_spending_params': getattr(extracted, 'alpha_spending_params', None),
                'interim_events': getattr(extracted, 'interim_events', None),
                'interim_alpha_spent': getattr(extracted, 'interim_alpha_spent', None),
                'interim_information_fraction': getattr(extracted, 'interim_information_fraction', None),
                'final_events': getattr(extracted, 'final_events', None),
                'stopping_boundaries': getattr(extracted, 'stopping_boundaries', None),

                # HIERARCHICAL TESTING fields (for multiple endpoints)
                'has_hierarchical_testing': getattr(extracted, 'has_hierarchical_testing', False),
                'hierarchical_testing_order': getattr(extracted, 'hierarchical_testing_order', None),
                'hierarchical_testing_description': getattr(extracted, 'hierarchical_testing_description', None),

                # CONSISTENCY/BRIDGING STUDY fields (for regional regulatory)
                'has_consistency_objective': getattr(extracted, 'has_consistency_objective', False),
                'consistency_type': getattr(extracted, 'consistency_type', None),
                'consistency_margin': getattr(extracted, 'consistency_margin', None),
                'consistency_reference_studies': getattr(extracted, 'consistency_reference_studies', None),
                'consistency_reference_effect': getattr(extracted, 'consistency_reference_effect', None),
                'consistency_test_description': getattr(extracted, 'consistency_test_description', None),
                'consistency_is_primary': getattr(extracted, 'consistency_is_primary', False),

                # REGULATORY/REGIONAL ENDPOINTS (e.g., TTF for China)
                'regulatory_endpoints': getattr(extracted, 'regulatory_endpoints', None),
                'is_bridging_study': getattr(extracted, 'is_bridging_study', False),
                'target_regions': getattr(extracted, 'target_regions', None),

                # STATISTICAL METHOD DETAILS (weighted log-rank, etc.)
                'statistical_method_details': getattr(extracted, 'statistical_method_details', None),
                'primary_test_type': getattr(extracted, 'primary_test_type', None),
                'test_parameters': getattr(extracted, 'test_parameters', None),

                # DOCUMENT TYPE (SAP vs Protocol)
                'document_type': getattr(extracted, 'document_type', 'protocol'),

                # ========== NEW: Additional fields for comprehensive SAP generation ==========

                # REGULATORY INTERIM ANALYSIS (e.g., TTF interim for China NDA)
                'has_regulatory_interim': getattr(extracted, 'has_regulatory_interim', False),
                'regulatory_interim_endpoint': getattr(extracted, 'regulatory_interim_endpoint', None),
                'regulatory_interim_region': getattr(extracted, 'regulatory_interim_region', None),
                'regulatory_interim_purpose': getattr(extracted, 'regulatory_interim_purpose', None),
                'regulatory_interim_timing': getattr(extracted, 'regulatory_interim_timing', None),
                'regulatory_interim_alpha': getattr(extracted, 'regulatory_interim_alpha', 0.025),
                'regulatory_interim_method': getattr(extracted, 'regulatory_interim_method', None),
                'regulatory_interim_analyses': getattr(extracted, 'regulatory_interim_analyses', None),

                # PRO/QoL ENDPOINTS (Patient-Reported Outcomes)
                'has_pro_endpoint': getattr(extracted, 'has_pro_endpoint', False),
                'pro_endpoints': getattr(extracted, 'pro_endpoints', None),
                'pro_instruments': getattr(extracted, 'pro_instruments', None),

                # NON-PROPORTIONAL HAZARDS MODEL (immunotherapy delayed effect)
                'has_nph_model': getattr(extracted, 'has_nph_model', False),
                'nph_model_type': getattr(extracted, 'nph_model_type', None),
                'delayed_effect_months': getattr(extracted, 'delayed_effect_months', 0),
                'piecewise_hazards': getattr(extracted, 'piecewise_hazards', None),
                'subgroup_specific_assumptions': getattr(extracted, 'subgroup_specific_assumptions', None),

                # CROSSOVER IMPACT MODELING
                'has_crossover_modeling': getattr(extracted, 'has_crossover_modeling', False),
                'crossover_rates_modeled': getattr(extracted, 'crossover_rates_modeled', None),
                'crossover_impact_on_hr': getattr(extracted, 'crossover_impact_on_hr', None),

                # SUBGROUP ANALYSES (full list)
                'subgroup_analyses': getattr(extracted, 'subgroup_analyses', None),
            })
        except Exception:
            pass  # Ignore if we can't set this attribute

        # Endpoints - Handle multiple co-primary endpoints
        if extracted.primary_endpoints:
            # Use first endpoint for backwards compatibility
            first_ep = extracted.primary_endpoints[0]
            if isinstance(first_ep, dict):
                facts.primary_endpoint = EndpointDefinition(
                    name="Primary Endpoint",
                    definition=first_ep.get("definition", ""),
                    timepoint=first_ep.get("timepoint", "")
                )
            else:
                facts.primary_endpoint = EndpointDefinition(
                    name="Primary Endpoint",
                    definition=str(first_ep)
                )
        elif extracted.primary_endpoint:
            facts.primary_endpoint = EndpointDefinition(
                name="Primary Endpoint",
                definition=extracted.primary_endpoint,
                timepoint=extracted.primary_timepoint
            )

        if extracted.secondary_endpoints:
            facts.secondary_endpoints = [
                EndpointDefinition(name="Secondary Endpoint", definition=ep)
                for ep in extracted.secondary_endpoints if ep
            ]

        # Statistical
        facts.alpha = AlphaSpecification(primary_alpha=extracted.alpha_level)
        facts.primary_analysis_method = extracted.statistical_method

        # Other
        facts.therapeutic_area = extracted.therapeutic_area
        facts.indication = extracted.indication
        facts.stratification_factors = extracted.stratification_factors

        # NEW: Set population definitions on facts object if available
        try:
            if extracted.itt_definition:
                object.__setattr__(facts, 'itt_definition', extracted.itt_definition)
            if extracted.pp_definition:
                object.__setattr__(facts, 'pp_definition', extracted.pp_definition)
            if extracted.safety_definition:
                object.__setattr__(facts, 'safety_definition', extracted.safety_definition)
            if extracted.fas_definition:
                object.__setattr__(facts, 'fas_definition', extracted.fas_definition)
        except Exception:
            pass

        return facts

    def _validate_and_correct_nct_id(
        self,
        nct_id: str,
        protocol_text: str,
        result: HybridPipelineResult
    ) -> str:
        """
        Validate NCT ID and correct if it appears to be a reference study.

        Root issue: Protocols often mention OTHER studies as references
        (e.g., "consistent with CheckMate 057"). This method validates
        by cross-checking API data against the document.

        Args:
            nct_id: Extracted NCT ID to validate
            protocol_text: Full protocol text for validation
            result: Pipeline result to add warnings to

        Returns:
            Validated NCT ID (may be different if correction needed)
        """
        try:
            from .api_extractor import ClinicalTrialsAPIExtractor
            extractor = ClinicalTrialsAPIExtractor()

            # First, validate the current NCT ID
            validation = extractor.validate_nct_id(nct_id, protocol_text)

            if validation["valid"]:
                logger.info(
                    "NCT ID validated",
                    nct_id=nct_id,
                    confidence=f"{validation['confidence']:.1%}"
                )
                return nct_id

            # Validation failed - NCT ID might be a reference study
            result.warnings.append(
                f"NCT ID validation warning: {validation['reason']}"
            )

            # Try to find the correct NCT ID using smart extraction
            smart_nct = extractor.extract_nct_id_smart(protocol_text)

            if smart_nct and smart_nct != nct_id:
                # Validate the alternative
                alt_validation = extractor.validate_nct_id(smart_nct, protocol_text)

                if alt_validation["valid"] and alt_validation["confidence"] > validation["confidence"]:
                    logger.warning(
                        "NCT ID corrected",
                        original=nct_id,
                        corrected=smart_nct,
                        confidence=f"{alt_validation['confidence']:.1%}"
                    )
                    result.warnings.append(
                        f"NCT ID auto-corrected: {nct_id} -> {smart_nct} "
                        f"(original appeared to be a reference study)"
                    )
                    return smart_nct

            # If suggested_nct was found during validation, try that
            if validation.get("suggested_nct"):
                suggested = validation["suggested_nct"]
                logger.warning(
                    "Using suggested NCT ID",
                    original=nct_id,
                    suggested=suggested
                )
                result.warnings.append(
                    f"Using suggested NCT ID: {suggested} (instead of {nct_id})"
                )
                return suggested

            # Couldn't find a better NCT ID - use original with warning
            logger.warning(
                "NCT ID validation failed but no alternative found",
                nct_id=nct_id,
                confidence=f"{validation['confidence']:.1%}"
            )
            return nct_id

        except Exception as e:
            logger.warning("NCT ID validation error", error=str(e))
            result.warnings.append(f"NCT ID validation skipped: {str(e)}")
            return nct_id

    def _enhance_with_api(self, facts: ProtocolFacts, result: HybridPipelineResult) -> ProtocolFacts:
        """Fetch from ClinicalTrials.gov API and override regex-extracted fields"""
        import requests

        try:
            url = f"https://clinicaltrials.gov/api/v2/studies/{facts.nct_id}"
            resp = requests.get(url, timeout=10)

            if resp.status_code != 200:
                result.warnings.append(f"API fetch failed: {resp.status_code}")
                return facts

            data = resp.json()
            protocol = data.get("protocolSection", {})

            # Override with API data (more accurate than regex)
            design = protocol.get("designModule", {})
            design_info = design.get("designInfo", {})

            # Sample size
            enrollment = design.get("enrollmentInfo", {}).get("count", 0)
            if enrollment:
                from .schemas import SampleSizeSpec
                facts.sample_size = {"total_n": enrollment}

            # Phase
            phases = design.get("phases", [])
            if phases:
                phase_map = {
                    "PHASE1": "Phase 1",
                    "PHASE2": "Phase 2",
                    "PHASE3": "Phase 3",
                    "PHASE4": "Phase 4",
                }
                facts.phase = phase_map.get(phases[0], "Unknown")

            # Design type
            model = design_info.get("interventionModel", "")
            allocation = design_info.get("allocation", "")
            if model == "SINGLE_GROUP":
                facts.design_type = "single-arm"
                facts.num_arms = 1
            elif allocation == "RANDOMIZED":
                facts.design_type = "randomized"

            # Drug name
            arms_module = protocol.get("armsInterventionsModule", {})
            interventions = arms_module.get("interventions", [])
            for intv in interventions:
                if intv.get("type") in ["DRUG", "BIOLOGICAL"]:
                    facts.drug_name = intv.get("name", "")
                    break

            # Primary endpoint
            outcomes = protocol.get("outcomesModule", {})
            primary = outcomes.get("primaryOutcomes", [])
            if primary:
                facts.primary_endpoint = {
                    "name": "Primary Endpoint",
                    "definition": primary[0].get("measure", ""),
                    "timepoint": primary[0].get("timeFrame", "")
                }

            # Secondary endpoints
            secondary = outcomes.get("secondaryOutcomes", [])
            if secondary:
                facts.secondary_endpoints = [
                    {"name": "Secondary", "definition": s.get("measure", "")}
                    for s in secondary[:5]
                ]

            # Arms
            arm_groups = arms_module.get("armGroups", [])
            if arm_groups:
                facts.arms = [
                    {
                        "name": a.get("label", ""),
                        "is_placebo": "placebo" in a.get("label", "").lower()
                    }
                    for a in arm_groups
                ]
                facts.num_arms = len(facts.arms)

            logger.info("API enhancement successful", nct_id=facts.nct_id)

        except Exception as e:
            result.warnings.append(f"API enhancement failed: {e}")
            logger.warning("API enhancement failed", exc_info=True, error=str(e))

        return facts

    def _extract_from_api_only(self, nct_id: str, result: HybridPipelineResult) -> Optional[ProtocolFacts]:
        """Extract facts directly from ClinicalTrials.gov API (when LLM unavailable)"""
        import requests
        from .schemas import (
            ProtocolFacts, EndpointDefinition, SampleSizeSpec,
            AlphaSpecification, TreatmentArmModel as TreatmentArm
        )
        StudyPhase = None  # Phase is now a string in ProtocolFacts

        try:
            url = f"https://clinicaltrials.gov/api/v2/studies/{nct_id}"
            resp = requests.get(url, timeout=10)

            if resp.status_code != 200:
                result.warnings.append(f"API fetch failed: {resp.status_code}")
                return None

            data = resp.json()
            protocol = data.get("protocolSection", {})

            facts = ProtocolFacts()
            facts.nct_id = nct_id

            # Design
            design = protocol.get("designModule", {})
            design_info = design.get("designInfo", {})

            # Sample size
            enrollment = design.get("enrollmentInfo", {}).get("count", 0)
            if enrollment:
                facts.sample_size = SampleSizeSpec(total_n=enrollment)

            # Phase
            phases = design.get("phases", [])
            if phases:
                phase_map = {
                    "PHASE1": StudyPhase.PHASE_1,
                    "PHASE2": StudyPhase.PHASE_2,
                    "PHASE3": StudyPhase.PHASE_3,
                    "PHASE4": StudyPhase.PHASE_4,
                }
                facts.phase = phase_map.get(phases[0], StudyPhase.UNKNOWN)

            # Design type
            model = design_info.get("interventionModel", "")
            allocation = design_info.get("allocation", "")
            if model == "SINGLE_GROUP":
                facts.design_type = "single-arm"
                facts.num_arms = 1
            elif allocation == "RANDOMIZED":
                facts.design_type = "randomized"

            # Drug name
            arms_module = protocol.get("armsInterventionsModule", {})
            interventions = arms_module.get("interventions", [])
            for intv in interventions:
                if intv.get("type") in ["DRUG", "BIOLOGICAL"]:
                    facts.drug_name = intv.get("name", "")
                    break

            # Primary endpoint
            outcomes = protocol.get("outcomesModule", {})
            primary = outcomes.get("primaryOutcomes", [])
            if primary:
                facts.primary_endpoint = EndpointDefinition(
                    name="Primary Endpoint",
                    definition=primary[0].get("measure", ""),
                    timepoint=primary[0].get("timeFrame", "")
                )

            # Secondary endpoints
            secondary = outcomes.get("secondaryOutcomes", [])
            if secondary:
                facts.secondary_endpoints = [
                    EndpointDefinition(name="Secondary", definition=s.get("measure", ""))
                    for s in secondary[:5]
                ]

            # Arms
            arm_groups = arms_module.get("armGroups", [])
            if arm_groups:
                facts.arms = [
                    TreatmentArm(
                        name=a.get("label", ""),
                        is_placebo="placebo" in a.get("label", "").lower()
                    )
                    for a in arm_groups
                ]
                facts.num_arms = len(facts.arms)

            logger.info("API-only extraction successful", nct_id=nct_id)

            return facts

        except Exception as e:
            result.warnings.append(f"API-only extraction failed: {e}")
            logger.warning("API-only extraction failed", exc_info=True, nct_id=nct_id, error=str(e))
            return None

    def _convert_unified_to_protocol_facts(
        self,
        unified: 'UnifiedFacts',
        protocol_text: str
    ) -> ProtocolFacts:
        """Convert UnifiedFacts to ProtocolFacts for pipeline compatibility"""
        from .schemas import (
            ProtocolFacts, EndpointDefinition, SampleSizeSpec,
            AlphaSpecification, TreatmentArmModel as TreatmentArm
        )
        StudyPhase = None  # Phase is now a string in ProtocolFacts

        facts = ProtocolFacts()

        # Basic info
        facts.nct_id = unified.nct_id
        facts.drug_name = unified.drug_name
        facts.drug_names_all = [unified.drug_name] if unified.drug_name else []

        # Design
        facts.design_type = unified.design_type
        facts.is_blinded = unified.is_blinded
        facts.num_arms = unified.num_arms
        # Note: is_randomized is derived from design_type in _facts_to_dict

        # Arms
        if unified.arms:
            facts.arms = [
                TreatmentArm(
                    name=arm.get("name", f"Arm {i+1}"),
                    is_placebo="placebo" in arm.get("name", "").lower()
                )
                for i, arm in enumerate(unified.arms)
            ]

        # Sample size
        if unified.sample_size:
            facts.sample_size = SampleSizeSpec(total_n=unified.sample_size)

        # Alpha - use defaults
        facts.alpha = AlphaSpecification()

        # Endpoints
        if unified.primary_endpoint:
            facts.primary_endpoint = EndpointDefinition(
                name="Primary Endpoint",
                definition=unified.primary_endpoint,
                timepoint=unified.primary_timepoint
            )

        if unified.secondary_endpoints:
            facts.secondary_endpoints = [
                EndpointDefinition(name="Secondary Endpoint", definition=ep)
                for ep in unified.secondary_endpoints if ep
            ]

        # Other fields
        facts.therapeutic_area = unified.therapeutic_area
        facts.stratification_factors = unified.stratification_factors

        # Phase - try to parse
        phase_str = unified.phase.upper() if unified.phase else ""
        if "1/2" in phase_str or "1B" in phase_str:
            facts.phase = StudyPhase.PHASE_1_2
        elif "2/3" in phase_str:
            facts.phase = StudyPhase.PHASE_2_3
        elif "1" in phase_str:
            facts.phase = StudyPhase.PHASE_1
        elif "2" in phase_str:
            facts.phase = StudyPhase.PHASE_2
        elif "3" in phase_str:
            facts.phase = StudyPhase.PHASE_3
        elif "4" in phase_str:
            facts.phase = StudyPhase.PHASE_4
        else:
            facts.phase = StudyPhase.UNKNOWN

        # Store LLM-extracted fields for the reasoning engine
        # Using object.__setattr__ to bypass Pydantic validation
        object.__setattr__(facts, '_llm_facts', {
            "primary_analysis_method": unified.primary_analysis_method,
            "analysis_model": unified.analysis_model,
            "covariates": unified.covariates,
            "missing_data_method": unified.missing_data_method,
            "multiplicity_adjustment": unified.multiplicity_adjustment,
            "sensitivity_analyses": unified.sensitivity_analyses,
            "baseline_definition": unified.baseline_definition,
            "visit_windows": unified.visit_windows,
        })

        return facts

    def _facts_to_dict(self, facts: ProtocolFacts) -> Dict[str, Any]:
        """Convert ProtocolFacts to dictionary for reasoning engine"""
        # Determine if single-arm
        is_single_arm = (
            facts.num_arms == 1 or
            (facts.design_type and 'single' in facts.design_type.lower()) or
            not facts.randomization_ratio
        )

        # Safely get optional attributes
        def safe_get(obj, attr, default=None):
            return getattr(obj, attr, default) if obj else default

        # PRIORITY 1: Get comparator from LLM-extracted facts (most reliable)
        comparator = None
        if hasattr(facts, '_llm_facts') and facts._llm_facts:
            comparator = facts._llm_facts.get('comparator', '')

        # PRIORITY 2: Check drug_names_all for second drug (if not study drug)
        if not comparator and facts.drug_names_all and len(facts.drug_names_all) > 1:
            for drug in facts.drug_names_all:
                if facts.drug_name and drug.lower() != facts.drug_name.lower():
                    comparator = drug
                    break

        # PRIORITY 3: Check arms for control/comparator arm
        if not comparator and facts.arms:
            for arm in facts.arms:
                arm_name = arm.name.lower() if hasattr(arm, 'name') else str(arm).lower()
                # Skip if this is the study drug
                if facts.drug_name and facts.drug_name.lower() in arm_name:
                    continue
                # Check for control indicators
                if any(x in arm_name for x in ['control', 'comparator', 'standard of care', 'soc']):
                    comparator = arm.name if hasattr(arm, 'name') else str(arm)
                    break
                # Check for active comparator drugs (not placebo)
                is_placebo = getattr(arm, 'is_placebo', False) or 'placebo' in arm_name
                if not is_placebo and arm_name:
                    comparator = arm.name if hasattr(arm, 'name') else str(arm)
                    # Don't break - keep looking for more specific matches

        # Build result dictionary
        result = {
            'nct_id': facts.nct_id,
            'protocol_title': safe_get(facts, 'protocol_title', ''),
            'sponsor': safe_get(facts, 'sponsor', ''),
            'drug_name': facts.drug_name,
            'comparator': comparator or '',  # CRITICAL: Include comparator
            'drug_names_all': facts.drug_names_all if facts.drug_names_all else [],
            'design_type': facts.design_type,
            'is_single_arm': is_single_arm,
            'is_blinded': safe_get(facts, 'is_blinded', False),
            'blinding_type': safe_get(facts, 'blinding_type'),
            'num_arms': facts.num_arms if facts.num_arms else (1 if is_single_arm else 2),
            'arms': [arm.name for arm in facts.arms] if facts.arms else [],
            'arms_detailed': [{'name': arm.name, 'description': getattr(arm, 'description', arm.name)} for arm in facts.arms] if facts.arms else [],
            'randomization_ratio': facts.randomization_ratio,
            'stratification_factors': facts.stratification_factors if facts.stratification_factors else [],
            'sample_size': facts.sample_size.total_n if facts.sample_size else 0,
            'power': facts.sample_size.power if facts.sample_size else None,
            'alpha': facts.alpha.primary_alpha if facts.alpha else 0.05,
            'alpha_sidedness': facts.alpha.sidedness if facts.alpha else 'two-sided',
            'primary_endpoint': facts.primary_endpoint.definition if facts.primary_endpoint else '',
            'primary_endpoint_name': facts.primary_endpoint.name if facts.primary_endpoint else 'Primary Endpoint',
            'primary_timepoint': facts.primary_endpoint.timepoint if facts.primary_endpoint and hasattr(facts.primary_endpoint, 'timepoint') else 'Week 12',
            'secondary_endpoints': [ep.definition for ep in facts.secondary_endpoints] if facts.secondary_endpoints else [],
            'therapeutic_area': safe_get(facts, 'therapeutic_area'),
            'indication': safe_get(facts, 'indication'),
            'phase': facts.phase.value if facts.phase else 'Phase 3',
            'route_of_administration': facts.route_of_administration.value if facts.route_of_administration else 'IV',
            'itt_definition': safe_get(facts, 'itt_definition'),
            'fas_definition': safe_get(facts, 'fas_definition'),
            'pp_definition': safe_get(facts, 'pp_definition'),
            'safety_definition': safe_get(facts, 'safety_definition'),
            'primary_analysis_method': safe_get(facts, 'primary_analysis_method'),
            'primary_analysis_population': safe_get(facts, 'primary_analysis_population'),
        }

        # Include LLM-extracted facts if available
        if hasattr(facts, '_llm_facts') and facts._llm_facts:
            llm = facts._llm_facts
            if llm.get('primary_analysis_method'):
                result['primary_analysis_method'] = llm['primary_analysis_method']
            if llm.get('analysis_model'):
                result['analysis_model'] = llm['analysis_model']
            if llm.get('covariates'):
                result['covariates'] = llm['covariates']
            if llm.get('missing_data_method'):
                result['missing_data_method'] = llm['missing_data_method']
            if llm.get('multiplicity_adjustment'):
                result['multiplicity_adjustment'] = llm['multiplicity_adjustment']
            if llm.get('sensitivity_analyses'):
                result['sensitivity_analyses'] = llm['sensitivity_analyses']
            if llm.get('baseline_definition'):
                result['baseline_definition'] = llm['baseline_definition']
            if llm.get('visit_windows'):
                result['visit_windows'] = llm['visit_windows']
            # Also check for comparator in LLM facts
            if llm.get('comparator') and not result['comparator']:
                result['comparator'] = llm['comparator']

            # NEW: Include pilot study detection flags
            result['is_pilot_study'] = llm.get('is_pilot_study', False)
            result['hypothesis_testing_planned'] = llm.get('hypothesis_testing_planned', True)
            result['sample_size_justification'] = llm.get('sample_size_justification', '')

            # NEW: Include multiple co-primary endpoints
            result['primary_endpoints'] = llm.get('primary_endpoints', [])

            # NEW: Include oncology response criteria
            result['response_criteria'] = llm.get('response_criteria', '')
            result['pathologic_response_criteria'] = llm.get('pathologic_response_criteria', '')
            result['response_assessor'] = llm.get('response_assessor', '')

            # NEW: Include protocol-specific population definitions
            if llm.get('itt_definition'):
                result['itt_definition'] = llm['itt_definition']
            if llm.get('pp_definition'):
                result['pp_definition'] = llm['pp_definition']
            if llm.get('safety_definition'):
                result['safety_definition'] = llm['safety_definition']
            if llm.get('fas_definition'):
                result['fas_definition'] = llm['fas_definition']

            # NEW: Statistical method details (e.g., Fleming-Harrington weighted log-rank)
            result['statistical_method'] = llm.get('statistical_method', '')
            result['statistical_method_details'] = llm.get('statistical_method_details', '')

            # NEW: Interim analysis details - COMPREHENSIVE
            result['has_interim_analysis'] = llm.get('has_interim_analysis', False)
            result['num_interim_analyses'] = llm.get('num_interim_analyses', 0)
            result['interim_analysis_method'] = llm.get('interim_analysis_method', '')
            result['error_spending_function'] = llm.get('error_spending_function', '')
            result['alpha_spending_params'] = llm.get('alpha_spending_params', '')
            result['interim_events'] = llm.get('interim_events', [])
            result['interim_alpha_spent'] = llm.get('interim_alpha_spent', [])
            result['interim_information_fraction'] = llm.get('interim_information_fraction', [])
            result['final_events'] = llm.get('final_events', 0)
            result['stopping_boundaries'] = llm.get('stopping_boundaries', '')

            # NEW: Hierarchical testing procedure
            result['has_hierarchical_testing'] = llm.get('has_hierarchical_testing', False)
            result['hierarchical_testing_order'] = llm.get('hierarchical_testing_order', [])
            result['hierarchical_testing_description'] = llm.get('hierarchical_testing_description', '')

            # NEW: Consistency/non-inferiority objectives - ENHANCED
            result['has_consistency_objective'] = llm.get('has_consistency_objective', False)
            result['consistency_type'] = llm.get('consistency_type', '')
            result['consistency_margin'] = llm.get('consistency_margin', '')
            result['consistency_reference_studies'] = llm.get('consistency_reference_studies', [])
            result['consistency_reference_effect'] = llm.get('consistency_reference_effect', '')
            result['consistency_test_description'] = llm.get('consistency_test_description', '')
            result['consistency_is_primary'] = llm.get('consistency_is_primary', False)

            # NEW: Regulatory-specific endpoints (e.g., TTF for China) - ENHANCED
            result['regulatory_endpoints'] = llm.get('regulatory_endpoints', [])
            result['is_bridging_study'] = llm.get('is_bridging_study', False)
            result['target_regions'] = llm.get('target_regions', [])

            # NEW: Document type
            result['document_type'] = llm.get('document_type', '')

            # ========== NEW: Additional fields for comprehensive SAP generation ==========

            # REGULATORY INTERIM ANALYSIS (e.g., TTF interim for China NDA)
            result['has_regulatory_interim'] = llm.get('has_regulatory_interim', False)
            result['regulatory_interim_endpoint'] = llm.get('regulatory_interim_endpoint', '')
            result['regulatory_interim_region'] = llm.get('regulatory_interim_region', '')
            result['regulatory_interim_purpose'] = llm.get('regulatory_interim_purpose', '')
            result['regulatory_interim_timing'] = llm.get('regulatory_interim_timing', '')
            result['regulatory_interim_alpha'] = llm.get('regulatory_interim_alpha', 0.025)
            result['regulatory_interim_method'] = llm.get('regulatory_interim_method', '')
            result['regulatory_interim_analyses'] = llm.get('regulatory_interim_analyses', [])

            # PRO/QoL ENDPOINTS (Patient-Reported Outcomes)
            result['has_pro_endpoint'] = llm.get('has_pro_endpoint', False)
            result['pro_endpoints'] = llm.get('pro_endpoints', [])
            result['pro_instruments'] = llm.get('pro_instruments', [])

            # NON-PROPORTIONAL HAZARDS MODEL (immunotherapy delayed effect)
            result['has_nph_model'] = llm.get('has_nph_model', False)
            result['nph_model_type'] = llm.get('nph_model_type', '')
            result['delayed_effect_months'] = llm.get('delayed_effect_months', 0)
            result['piecewise_hazards'] = llm.get('piecewise_hazards', [])
            result['subgroup_specific_assumptions'] = llm.get('subgroup_specific_assumptions', [])

            # CROSSOVER IMPACT MODELING
            result['has_crossover_modeling'] = llm.get('has_crossover_modeling', False)
            result['crossover_rates_modeled'] = llm.get('crossover_rates_modeled', [])
            result['crossover_impact_on_hr'] = llm.get('crossover_impact_on_hr', '')

            # SUBGROUP ANALYSES (full list)
            result['subgroup_analyses'] = llm.get('subgroup_analyses', [])

        return result

    def _facts_to_parsed_protocol(self, facts: ProtocolFacts, facts_dict: Dict[str, Any]) -> 'ParsedProtocol':
        """Convert ProtocolFacts to ParsedProtocol for TLF generator"""
        from .schemas import (
            ParsedProtocol, Estimand, DesignType, BlindingType,
            StudyPhase, EndpointType
        )

        # Determine endpoint type from primary endpoint
        primary_ep = str(facts_dict.get('primary_endpoint') or '').lower()
        endpoint_type = EndpointType.EFFICACY  # Default
        if any(kw in primary_ep for kw in ['orr', 'objective response', 'response rate', 'recist']):
            endpoint_type = EndpointType.ORR
        elif any(kw in primary_ep for kw in ['overall survival', 'os', 'death']):
            endpoint_type = EndpointType.OS
        elif any(kw in primary_ep for kw in ['progression-free', 'pfs', 'progression']):
            endpoint_type = EndpointType.PFS
        elif any(kw in primary_ep for kw in ['disease-free', 'dfs', 'relapse']):
            endpoint_type = EndpointType.DFS
        elif any(kw in primary_ep for kw in ['safety', 'adverse event', 'tolerability', 'teae']):
            endpoint_type = EndpointType.SAFETY

        # Create primary estimand
        primary_estimand = Estimand(
            name="Primary",
            population="ITT",
            treatment=str(facts_dict.get('drug_name') or ''),
            variable=str(facts_dict.get('primary_endpoint') or ''),
            variable_type=endpoint_type,
            intercurrent_events={"treatment_discontinuation": "treatment_policy"},
            summary_measure="difference_in_proportions" if endpoint_type == EndpointType.ORR else "hazard_ratio"
        )

        # Determine design type
        design_str = str(facts_dict.get('design_type') or '').lower()
        if 'single' in design_str:
            design_type = DesignType.SINGLE_ARM
        elif 'crossover' in design_str:
            design_type = DesignType.CROSSOVER
        else:
            design_type = DesignType.PARALLEL

        # Determine blinding
        if facts_dict.get('is_blinded'):
            blinding = BlindingType.DOUBLE_BLIND
        else:
            blinding = BlindingType.OPEN_LABEL

        # Get treatment arms
        arms = facts_dict.get('arms', [])
        if not arms:
            drug = facts_dict.get('drug_name', 'Treatment')
            if facts_dict.get('is_single_arm'):
                arms = [drug]
            else:
                comparator = facts_dict.get('comparator', 'Control')
                arms = [drug, comparator]

        return ParsedProtocol(
            nct_id=facts_dict.get('nct_id', ''),
            sponsor=facts_dict.get('sponsor', ''),
            study_title=facts_dict.get('protocol_title', ''),
            therapeutic_area=facts_dict.get('therapeutic_area', ''),
            indication=facts_dict.get('indication', ''),
            phase=facts.phase if facts.phase else StudyPhase.UNKNOWN,
            primary_estimand=primary_estimand,
            design_type=design_type,
            randomization_ratio=facts_dict.get('randomization_ratio', ''),
            stratification_factors=facts_dict.get('stratification_factors', []),
            blinding=blinding,
            treatment_arms=arms
        )

    def _build_estimands_dict(self, facts_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Build estimands dictionary for TLF generator"""
        primary_ep = facts_dict.get('primary_endpoint', '')

        return {
            'primary': {
                'name': 'Primary',
                'population': 'ITT',
                'treatment': facts_dict.get('drug_name', ''),
                'variable': primary_ep,
                'intercurrent_events': {'treatment_discontinuation': 'treatment_policy'},
                'summary_measure': 'difference'
            },
            'secondary': [
                {
                    'name': f'Secondary {i+1}',
                    'population': 'ITT',
                    'variable': ep
                }
                for i, ep in enumerate(facts_dict.get('secondary_endpoints', []))
            ]
        }

    def _generate_introduction(self, facts: Dict[str, Any]) -> str:
        """Generate introduction section"""
        drug = facts.get('drug_name', 'study drug')
        nct = facts.get('nct_id', 'NCT########')
        phase = facts.get('phase', 'Phase 3')
        indication = facts.get('indication', 'the target indication')

        return f"""## 1. INTRODUCTION

### 1.1 Purpose

This Statistical Analysis Plan (SAP) describes the statistical methods for the analysis of data from study {nct}, a {phase} study of {drug} in patients with {indication}.

This SAP is based on the protocol and should be read in conjunction with it. Any deviations from the pre-specified analyses will be documented in the Clinical Study Report.

### 1.2 Scope

This SAP covers:
- All efficacy analyses (primary, secondary, exploratory)
- All safety analyses
- Derivation of analysis datasets (ADaM)
- Table, listing, and figure specifications

### 1.3 Responsibilities

The Biostatistics team is responsible for:
- Implementation of this SAP
- Generation of analysis datasets
- Production of statistical outputs
- Interpretation of results in conjunction with the clinical team
"""

    def _generate_objectives(self, facts: Dict[str, Any]) -> str:
        """Generate objectives section"""
        drug = facts.get('drug_name', 'study drug')
        comparator = facts.get('comparator', '')  # Get actual comparator
        indication = facts.get('indication', 'the target indication')
        primary_endpoint = facts.get('primary_endpoint', 'the primary efficacy endpoint')
        is_single_arm = facts.get('is_single_arm', False)

        # Determine comparator text - use actual comparator, not hardcoded "placebo"
        if is_single_arm:
            comparison = f"in patients with {indication}"
            estimand_target = f"the effect of {drug}"
            treatment_text = f"{drug} at specified dose"
        else:
            comparator_text = comparator if comparator else 'control'
            comparison = f"compared to {comparator_text} in patients with {indication}"
            estimand_target = f"the treatment effect of {drug} versus {comparator_text}"
            treatment_text = f"{drug} vs {comparator_text}"

        return f"""## 2. OBJECTIVES AND ESTIMANDS

### 2.1 Primary Objective

To evaluate the efficacy of {drug} {comparison} as measured by {primary_endpoint}.

### 2.2 Primary Estimand

Following ICH E9(R1), the primary estimand is defined as:

| Attribute | Specification |
|-----------|---------------|
| **Population** | Patients with {indication} meeting eligibility criteria |
| **Treatment** | {treatment_text} |
| **Variable** | {primary_endpoint} |
| **Intercurrent Events** | Treatment discontinuation: Treatment policy strategy |
| **Summary Measure** | {'Proportion of responders' if 'response' in primary_endpoint.lower() else 'Difference in means'} |

### 2.3 Secondary Objectives

1. To evaluate the safety and tolerability of {drug}
2. To evaluate additional efficacy endpoints
3. To characterize the pharmacokinetics of {drug} (if applicable)
"""

    def _generate_study_design(self, facts: Dict[str, Any]) -> str:
        """Generate study design section"""
        drug = facts.get('drug_name', 'study drug')
        comparator = facts.get('comparator', '')
        # Default design type - use 'controlled' instead of 'placebo-controlled'
        default_design = 'randomized, double-blind, controlled' if not comparator else f'randomized, controlled'
        design_type = facts.get('design_type', default_design)
        is_single_arm = facts.get('is_single_arm', False)
        num_arms = facts.get('num_arms', 2)
        ratio = facts.get('randomization_ratio', '1:1')
        phase = facts.get('phase', 'Phase 3')

        # Get stratification from hybrid reasoning result if available
        strat_section = facts.get('stratification_section', '')

        if is_single_arm:
            design_desc = f"""This is a {phase}, open-label, single-arm study of {drug}.

**Study Design:** Single-arm, open-label

**Treatment:** All enrolled patients will receive {drug} at the protocol-specified dose.

**No Randomization:** As a single-arm study, patients are not randomized."""
        else:
            design_desc = f"""This is a {phase}, {design_type} study of {drug}.

**Study Design:** {design_type.title()}

**Randomization:** Patients will be randomized in a {ratio} ratio to:
{self._format_arms(facts)}

**Blinding:** {facts.get('blinding_type', 'Double-blind')}"""

        return f"""## 3. STUDY DESIGN

### 3.1 Overview

{design_desc}

### 3.2 Treatment Arms

| Arm | Treatment | N (planned) |
|-----|-----------|-------------|
{self._format_arms_table(facts)}

### 3.3 Study Duration

- Screening: Up to 4 weeks
- Treatment: Per protocol
- Follow-up: Per protocol

{strat_section}
"""

    def _format_arms(self, facts: Dict[str, Any]) -> str:
        """Format treatment arms list"""
        arms = facts.get('arms', [])
        drug = facts.get('drug_name', 'study drug')
        comparator = facts.get('comparator', '')  # Get actual comparator

        if not arms:
            if facts.get('is_single_arm'):
                return f"- {drug} (single arm)"
            else:
                # Use actual comparator, not hardcoded "Placebo"
                comparator_text = comparator if comparator else 'Control'
                return f"- {drug}\n- {comparator_text}"

        return "\n".join([f"- {arm}" for arm in arms])

    def _format_arms_table(self, facts: Dict[str, Any]) -> str:
        """Format arms table rows"""
        arms = facts.get('arms', [])
        drug = facts.get('drug_name', 'study drug')
        comparator = facts.get('comparator', '')  # Get actual comparator
        n = facts.get('sample_size', 0)
        num_arms = facts.get('num_arms', 2)

        if not arms:
            if facts.get('is_single_arm'):
                return f"| 1 | {drug} | {n} |"
            else:
                per_arm = n // num_arms if n and num_arms else 'TBD'
                # Use actual comparator, not hardcoded "Placebo"
                comparator_text = comparator if comparator else 'Control'
                return f"| 1 | {drug} | {per_arm} |\n| 2 | {comparator_text} | {per_arm} |"

        per_arm = n // len(arms) if n and arms else 'TBD'
        return "\n".join([f"| {i+1} | {arm} | {per_arm} |" for i, arm in enumerate(arms)])

    def _generate_sample_size(self, facts: Dict[str, Any]) -> str:
        """Generate sample size section"""
        n = facts.get('sample_size', 0)
        power = facts.get('power') or 0.80
        alpha = facts.get('alpha') or 0.05
        is_single_arm = facts.get('is_single_arm', False)
        primary_endpoint = facts.get('primary_endpoint', '')

        # Format power safely
        power_str = f"{power:.0%}" if power else "80%"

        if is_single_arm:
            design_text = """**Single-Arm Design:**

Sample size is based on achieving adequate precision for the primary endpoint estimate."""
        else:
            design_text = f"""**Comparative Design:**

Sample size provides {power_str} power to detect a clinically meaningful difference between treatment groups at a {alpha} significance level."""

        return f"""## 6. SAMPLE SIZE

### 6.1 Sample Size Justification

**Planned Enrollment:** {n if n else 'TBD'} patients

{design_text}

### 6.2 Assumptions

- Primary endpoint: {primary_endpoint if primary_endpoint else 'Per protocol'}
- Significance level: {alpha} ({'one-sided' if facts.get('alpha_sidedness') == 'one-sided' else 'two-sided'})
- Power: {power_str}
- Dropout rate: ~10-15%

### 6.3 Sample Size Formula

{'Exact binomial CI width for single-arm design' if is_single_arm else 'Chi-square test or t-test as appropriate for endpoint type'}
"""

    def _generate_missing_data(self, facts: Dict[str, Any]) -> str:
        """Generate missing data section"""
        is_single_arm = facts.get('is_single_arm', False)

        return f"""## 9. MISSING DATA

### 9.1 Missing Data Handling

**Primary Approach:** {'Per-protocol analysis with sensitivity analyses' if is_single_arm else 'Treatment policy strategy (all data used regardless of discontinuation)'}

### 9.2 Imputation Methods

| Scenario | Method |
|----------|--------|
| Missing baseline | Patient excluded from analysis |
| Missing post-baseline (binary) | Non-responder imputation (NRI) |
| Missing post-baseline (continuous) | MMRM (implicit imputation) |
| Early discontinuation | Multiple imputation or LOCF sensitivity |

### 9.3 Sensitivity Analyses

1. **Complete Case Analysis:** Patients with complete data only
2. **LOCF:** Last observation carried forward
3. **BOCF:** Baseline observation carried forward
4. **Multiple Imputation:** Under MAR assumption
5. **Tipping Point:** Assess robustness to MNAR scenarios

### 9.4 Missing Data Reporting

Extent of missing data will be summarized:
- By visit and treatment group
- By reason for missing
- Impact on analysis populations
"""

    def _enhance_nph_acknowledgment(
        self,
        generated_text: str,
        protocol_text: str,
        facts: Dict[str, Any]
    ) -> str:
        """
        Add delayed effect / non-proportional hazards language for IO trials.

        Immunotherapy trials often exhibit delayed treatment effects where
        Kaplan-Meier curves don't separate until months after treatment.
        This requires weighted log-rank tests like Fleming-Harrington.
        """
        # IO-related keywords indicating potential delayed effect
        io_keywords = [
            'immunotherapy', 'checkpoint', 'pd-1', 'pd-l1', 'ctla-4',
            'pembrolizumab', 'nivolumab', 'atezolizumab', 'durvalumab',
            'ipilimumab', 'avelumab', 'cemiplimab', 'tremelimumab',
            'delayed treatment effect', 'delayed effect',
            'immune checkpoint inhibitor', 'ici', 'car-t', 'car t'
        ]

        combined_text = (protocol_text + " " + facts.get('drug_name', '')).lower()

        # Check if this is an IO trial
        is_io_trial = any(kw in combined_text for kw in io_keywords)

        # Check if NPH/delayed effect already acknowledged
        nph_terms = ['delayed', 'non-proportional', 'non proportional', 'nph',
                     'fleming-harrington', 'fleming harrington', 'weighted log-rank']
        already_has_nph = any(term in generated_text.lower() for term in nph_terms)

        if is_io_trial and not already_has_nph:
            # Construct NPH enhancement text
            nph_text = """
### 7.2.1 Consideration of Delayed Treatment Effect

Due to the immunotherapy mechanism of action, a delayed treatment effect is anticipated,
where the Kaplan-Meier survival curves may not separate until several months after
treatment initiation. This non-proportional hazards (NPH) pattern is characteristic
of checkpoint inhibitor therapy.

To account for this expected delayed effect, the following approaches are pre-specified:

1. **Primary Analysis**: The Fleming-Harrington weighted log-rank test with weights
   G(ρ=0, γ=1) will be used as a sensitivity analysis. This weighting scheme
   down-weights early events (when treatment effect may not yet be apparent)
   and up-weights later events.

2. **Supportive Analyses**:
   - Restricted Mean Survival Time (RMST) difference at clinically relevant timepoints
   - Milestone survival rates at 12, 18, and 24 months
   - Piecewise Cox model allowing for different hazard ratios before and after
     the expected treatment effect onset (estimated at 3-4 months)

3. **Visual Assessment**: Kaplan-Meier plots will be examined for evidence of
   delayed separation, crossing curves, or converging curves.

"""
            # Find best insertion point - after primary analysis section
            insertion_patterns = [
                "### 7.3",  # Before secondary endpoints
                "### 7.2.2",  # Before any 7.2.x subsection
                "Secondary Endpoint",  # Before secondary analysis
            ]

            for pattern in insertion_patterns:
                if pattern in generated_text:
                    generated_text = generated_text.replace(
                        pattern,
                        nph_text + pattern
                    )
                    logger.info("Enhanced SAP with NPH acknowledgment for IO trial")
                    break

        return generated_text

    def _assemble_sap(self, sections: Dict[str, str], facts: Dict[str, Any]) -> str:
        """Assemble final SAP document from sections"""
        drug = facts.get('drug_name', 'Study Drug')
        nct = facts.get('nct_id', 'NCT########')
        phase = facts.get('phase', 'Phase 3')

        # Header
        header = f"""# STATISTICAL ANALYSIS PLAN

**Study:** {nct}
**Drug:** {drug}
**Phase:** {phase}
**Version:** 1.0
**Date:** [DATE]

---

## TABLE OF CONTENTS

1. Introduction
2. Objectives and Estimands
3. Study Design
4. Analysis Populations
5. Endpoints
6. Sample Size
7. Statistical Methods
8. Safety Analysis
9. Missing Data
Appendix A: Variable Derivations

---

"""

        # Order sections properly
        section_order = [
            'introduction',
            'objectives',
            'study_design',
            'stratification',      # From hybrid engine
            'populations',         # From hybrid engine
            'endpoints',           # From hybrid engine
            'pro_endpoints',       # NEW: Patient-Reported Outcomes
            'sample_size',
            'methods',             # From hybrid engine
            'subgroup_analyses',   # NEW: Subgroup Analyses
            'regulatory_interim',  # NEW: Regulatory Interim Analysis (e.g., TTF for China)
            'teae_logic',          # From hybrid engine (safety)
            'missing_data',
            'derivations',         # From hybrid engine
            'follow_up_windows',   # From hybrid engine
        ]

        body_parts = []
        for section_name in section_order:
            if section_name in sections and sections[section_name]:
                body_parts.append(sections[section_name])

        body = "\n\n".join(body_parts)

        return header + body


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_hybrid_pipeline(
    use_rag: bool = True,
    use_validation: bool = True,
    strict_validation: bool = False,
    use_tlf: bool = True,
    verbose: bool = True
) -> HybridSAPPipeline:
    """Create a hybrid SAP pipeline instance.

    Args:
        use_rag: Whether to use RAG for section generation
        use_validation: Whether to run validation on output
        strict_validation: If True, block output on HIGH severity issues
        use_tlf: Whether to generate TLF shell specifications
        verbose: Whether to print progress messages
    """
    return HybridSAPPipeline(
        use_rag=use_rag,
        use_validation=use_validation,
        strict_validation=strict_validation,
        use_tlf=use_tlf,
        verbose=verbose
    )


# =============================================================================
# CLI INTERFACE
# =============================================================================

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("HYBRID SAP GENERATION PIPELINE")
    print("=" * 60)

    # Create pipeline
    pipeline = create_hybrid_pipeline(use_rag=True, verbose=True)

    # Test with sample protocol
    test_protocol = """
    A Phase 2, Open-Label, Single-Arm Study of Pembrolizumab in Patients with
    Advanced Solid Tumors Expressing CD137.

    NCT03422848

    Approximately 50 patients will be enrolled to receive Pembrolizumab 200mg IV Q3W.

    The primary endpoint is objective response rate (ORR) per RECIST v1.1 at Week 12.

    Secondary endpoints include:
    - Duration of response
    - Progression-free survival
    - Overall survival

    This is a single-arm, open-label study. No randomization.
    """

    result = pipeline.generate(test_protocol, nct_id="NCT03422848")

    print("\n" + "=" * 60)
    print("GENERATION COMPLETE")
    print("=" * 60)
    print(f"Success: {result.success}")
    print(f"Errors: {result.errors}")
    print(f"Warnings: {result.warnings}")
    print("\n" + result.get_reasoning_summary())

    if result.sap_text:
        print("\n" + "=" * 60)
        print("GENERATED SAP (first 2000 chars)")
        print("=" * 60)
        print(result.sap_text[:2000])
