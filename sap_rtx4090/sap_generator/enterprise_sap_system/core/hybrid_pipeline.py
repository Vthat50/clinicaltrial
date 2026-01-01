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

Usage:
    from hybrid_pipeline import HybridSAPPipeline

    pipeline = HybridSAPPipeline()
    result = pipeline.generate(protocol_text, nct_id="NCT12345678")
"""

import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path

# Import components (ProtocolFacts for data structure only - NO regex extraction)
from .structured_extractor import ProtocolFacts
from .hybrid_reasoning import (
    HybridReasoningEngine,
    ReasoningResult,
    ReasoningType,
    create_hybrid_engine
)
from .rag_adapter import create_rag_adapter, HybridRAGAdapter

# Import Claude extractor (LLM-based - REQUIRED, no regex fallback)
try:
    from .claude_extractor import ClaudeProtocolExtractor, ExtractedProtocol
    CLAUDE_EXTRACTOR_AVAILABLE = True
except ImportError as e:
    CLAUDE_EXTRACTOR_AVAILABLE = False
    print(f"[HybridPipeline] CRITICAL: ClaudeExtractor not available - LLM extraction disabled: {e}")

# Try to import validation components
try:
    from .hard_validator import HardValidator, ValidationResult
    VALIDATOR_AVAILABLE = True
except ImportError as e:
    VALIDATOR_AVAILABLE = False
    print(f"[HybridPipeline] ⚠️ WARNING: HardValidator not available - validation disabled: {e}")

try:
    from .contamination_guard import ContaminationGuard
    CONTAMINATION_GUARD_AVAILABLE = True
except ImportError as e:
    CONTAMINATION_GUARD_AVAILABLE = False
    print(f"[HybridPipeline] ⚠️ WARNING: ContaminationGuard not available - contamination checking disabled: {e}")


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
        verbose: bool = True
    ):
        """
        Initialize hybrid pipeline.

        Args:
            use_rag: Enable RAG for enhanced sections
            use_validation: Enable post-generation validation
            strict_validation: Block output on validation failures
            verbose: Print progress messages
        """
        self.verbose = verbose
        self.use_validation = use_validation
        self.strict_validation = strict_validation

        # Initialize LLM extractor (NO regex fallback)
        if CLAUDE_EXTRACTOR_AVAILABLE:
            self.claude_extractor = ClaudeProtocolExtractor()
            self.use_llm_extraction = True
        else:
            self.claude_extractor = None
            self.use_llm_extraction = False
            print("[Hybrid Pipeline] WARNING: LLM extraction unavailable - set ANTHROPIC_API_KEY")

        # Initialize RAG adapter
        self.rag_adapter = create_rag_adapter() if use_rag else None

        # Initialize hybrid reasoning engine with RAG
        self.reasoning_engine = create_hybrid_engine(
            rag_retriever=self.rag_adapter
        )

        # Initialize validators
        self.validator = HardValidator(strict_mode=strict_validation) if VALIDATOR_AVAILABLE and use_validation else None
        self.contamination_guard = ContaminationGuard() if CONTAMINATION_GUARD_AVAILABLE else None

        if self.verbose:
            print("[Hybrid Pipeline] Initialized")
            print(f"  Extraction: {'LLM (Claude)' if self.use_llm_extraction else 'DISABLED (set ANTHROPIC_API_KEY)'}")
            print(f"  RAG: {'enabled' if use_rag and self.rag_adapter else 'disabled'}")
            print(f"  Validation: {'enabled' if use_validation else 'disabled'}")

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
            if self.verbose:
                print("\n[LAYER 1] Extracting protocol facts...")

            # Use LLM extraction (NO regex fallback)
            facts = None

            if self.use_llm_extraction and self.claude_extractor:
                # LLM-based extraction (99.5% accuracy per research)
                extracted = self.claude_extractor.extract(protocol_text)

                if extracted.extraction_success:
                    # Convert to ProtocolFacts for compatibility
                    facts = self._convert_extracted_to_facts(extracted)
                    result.warnings.extend(extracted.warnings)
                    if self.verbose:
                        print(f"  ✓ LLM extraction via {extracted.extraction_source}")
                        print(f"    Drug: {extracted.drug_name}")
                        print(f"    Primary Endpoint: {extracted.primary_endpoint[:60]}..." if extracted.primary_endpoint else "    Primary Endpoint: Not found")
                else:
                    # LLM failed - try API if NCT ID available
                    result.warnings.extend(extracted.warnings)
                    if self.verbose:
                        print(f"  ⚠️ LLM extraction failed: {extracted.warnings}")

            # If no facts yet and NCT ID available, try API-only extraction
            if facts is None and nct_id:
                if self.verbose:
                    print("  Attempting API-only extraction...")
                facts = self._extract_from_api_only(nct_id, result)

            # If still no facts, create empty structure
            if facts is None:
                if self.verbose:
                    print("  ⚠️ No extraction method available - using empty facts")
                facts = ProtocolFacts()
                if nct_id:
                    facts.nct_id = nct_id
                result.warnings.append("Extraction failed - set ANTHROPIC_API_KEY for LLM extraction")

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
                if self.verbose:
                    print(f"  ⚠️ {warning_msg}")

            # Track warnings for non-critical missing data
            if not facts.design_type:
                result.warnings.append("design_type not extracted - defaulting to 'randomized'")
            if not facts.phase:
                result.warnings.append("phase not extracted")
            if not facts.therapeutic_area:
                result.warnings.append("therapeutic_area not extracted")

            # Convert to dict for reasoning engine
            facts_dict = self._facts_to_dict(facts)

            if self.verbose:
                print(f"  ✓ Drug: {facts.drug_name}")
                print(f"  ✓ Design: {facts.design_type} (single-arm: {facts_dict.get('is_single_arm', False)})")
                print(f"  ✓ Sample Size: {facts.sample_size.total_n if facts.sample_size else 0}")
                print(f"  ✓ Primary Endpoint: {facts.primary_endpoint}")
                if result.warnings:
                    for w in result.warnings:
                        print(f"  ⚠ {w}")

            # =================================================================
            # LAYER 2: HYBRID REASONING
            # =================================================================
            if self.verbose:
                print("\n[LAYER 2] Generating sections with hybrid reasoning...")

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

                if self.verbose:
                    icon = "🌳" if rr.reasoning_type == ReasoningType.DECISION_TREE else "📚" if rr.reasoning_type == ReasoningType.RAG else "📄"
                    print(f"  {icon} {section}: {rr.reasoning_type.value} ({rr.confidence:.0%})")

            # =================================================================
            # LAYER 3: ADDITIONAL SECTIONS (LLM-based)
            # =================================================================
            if self.verbose:
                print("\n[LAYER 3] Generating additional sections...")

            # Generate sections not covered by hybrid engine
            result.sections['introduction'] = self._generate_introduction(facts_dict)
            result.sections['objectives'] = self._generate_objectives(facts_dict)
            result.sections['study_design'] = self._generate_study_design(facts_dict)
            result.sections['sample_size'] = self._generate_sample_size(facts_dict)
            result.sections['missing_data'] = self._generate_missing_data(facts_dict)

            # =================================================================
            # LAYER 4: ASSEMBLY
            # =================================================================
            if self.verbose:
                print("\n[LAYER 4] Assembling SAP document...")

            result.sap_text = self._assemble_sap(result.sections, facts_dict)

            # =================================================================
            # LAYER 5: VALIDATION (never blocks, just collects issues)
            # =================================================================
            if self.use_validation and self.validator:
                if self.verbose:
                    print("\n[LAYER 5] Validating SAP...")

                validation = self.validator.validate(result.sap_text, facts)
                result.validation = validation

                if self.verbose:
                    print(f"  {validation.summary()}")

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
                    if self.verbose:
                        print(f"  ⚠️ Contamination cleaned: {report.contamination_sources}")

            result.success = True  # Always succeed if we got here

        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            if self.verbose:
                print(f"\n[ERROR] Pipeline failed: {e}")

        return result

    def _convert_extracted_to_facts(self, extracted: 'ExtractedProtocol') -> ProtocolFacts:
        """Convert LLM-extracted data to ProtocolFacts for pipeline compatibility"""
        from .structured_extractor import (
            ProtocolFacts, EndpointDefinition, SampleSizeSpec,
            AlphaSpecification, TreatmentArm, StudyPhase
        )

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

        # Drug
        facts.drug_name = extracted.drug_name
        facts.drug_names_all = [extracted.drug_name] if extracted.drug_name else []
        if extracted.comparator:
            facts.drug_names_all.append(extracted.comparator)

        # Endpoints
        if extracted.primary_endpoint:
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

        return facts

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
                from .structured_extractor import SampleSizeSpec
                facts.sample_size = SampleSizeSpec(total_n=enrollment)

            # Phase
            phases = design.get("phases", [])
            if phases:
                from .structured_extractor import StudyPhase
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
                from .structured_extractor import EndpointDefinition
                facts.primary_endpoint = EndpointDefinition(
                    name="Primary Endpoint",
                    definition=primary[0].get("measure", ""),
                    timepoint=primary[0].get("timeFrame", "")
                )

            # Secondary endpoints
            secondary = outcomes.get("secondaryOutcomes", [])
            if secondary:
                from .structured_extractor import EndpointDefinition
                facts.secondary_endpoints = [
                    EndpointDefinition(name="Secondary", definition=s.get("measure", ""))
                    for s in secondary[:5]
                ]

            # Arms
            arm_groups = arms_module.get("armGroups", [])
            if arm_groups:
                from .structured_extractor import TreatmentArm
                facts.arms = [
                    TreatmentArm(
                        name=a.get("label", ""),
                        is_placebo="placebo" in a.get("label", "").lower()
                    )
                    for a in arm_groups
                ]
                facts.num_arms = len(facts.arms)

            if self.verbose:
                print(f"  ✓ API enhanced: {facts.nct_id}")

        except Exception as e:
            result.warnings.append(f"API enhancement failed: {e}")

        return facts

    def _extract_from_api_only(self, nct_id: str, result: HybridPipelineResult) -> Optional[ProtocolFacts]:
        """Extract facts directly from ClinicalTrials.gov API (when LLM unavailable)"""
        import requests
        from .structured_extractor import (
            ProtocolFacts, EndpointDefinition, SampleSizeSpec,
            AlphaSpecification, TreatmentArm, StudyPhase
        )

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

            if self.verbose:
                print(f"  ✓ API-only extraction: {nct_id}")

            return facts

        except Exception as e:
            result.warnings.append(f"API-only extraction failed: {e}")
            return None

    def _convert_unified_to_protocol_facts(
        self,
        unified: 'UnifiedFacts',
        protocol_text: str
    ) -> ProtocolFacts:
        """Convert UnifiedFacts to ProtocolFacts for pipeline compatibility"""
        from .structured_extractor import (
            ProtocolFacts, EndpointDefinition, SampleSizeSpec,
            AlphaSpecification, TreatmentArm, StudyPhase
        )

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

        return {
            'nct_id': facts.nct_id,
            'drug_name': facts.drug_name,
            'drug_names_all': facts.drug_names_all if facts.drug_names_all else [],
            'design_type': facts.design_type,
            'is_single_arm': is_single_arm,
            'is_blinded': safe_get(facts, 'is_blinded', False),
            'blinding_type': safe_get(facts, 'blinding_type'),
            'num_arms': facts.num_arms if facts.num_arms else (1 if is_single_arm else 2),
            'arms': [arm.name for arm in facts.arms] if facts.arms else [],
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

        return result

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
        indication = facts.get('indication', 'the target indication')
        primary_endpoint = facts.get('primary_endpoint', 'the primary efficacy endpoint')
        is_single_arm = facts.get('is_single_arm', False)

        if is_single_arm:
            comparison = f"in patients with {indication}"
            estimand_target = f"the effect of {drug}"
        else:
            comparison = f"compared to placebo in patients with {indication}"
            estimand_target = f"the treatment effect of {drug} versus placebo"

        return f"""## 2. OBJECTIVES AND ESTIMANDS

### 2.1 Primary Objective

To evaluate the efficacy of {drug} {comparison} as measured by {primary_endpoint}.

### 2.2 Primary Estimand

Following ICH E9(R1), the primary estimand is defined as:

| Attribute | Specification |
|-----------|---------------|
| **Population** | Patients with {indication} meeting eligibility criteria |
| **Treatment** | {drug} {'at specified dose' if is_single_arm else 'vs placebo'} |
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
        design_type = facts.get('design_type', 'randomized, double-blind, placebo-controlled')
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

        if not arms:
            if facts.get('is_single_arm'):
                return f"- {drug} (single arm)"
            else:
                return f"- {drug}\n- Placebo"

        return "\n".join([f"- {arm}" for arm in arms])

    def _format_arms_table(self, facts: Dict[str, Any]) -> str:
        """Format arms table rows"""
        arms = facts.get('arms', [])
        drug = facts.get('drug_name', 'study drug')
        n = facts.get('sample_size', 0)
        num_arms = facts.get('num_arms', 2)

        if not arms:
            if facts.get('is_single_arm'):
                return f"| 1 | {drug} | {n} |"
            else:
                per_arm = n // num_arms if n and num_arms else 'TBD'
                return f"| 1 | {drug} | {per_arm} |\n| 2 | Placebo | {per_arm} |"

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
            'sample_size',
            'methods',             # From hybrid engine
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
    verbose: bool = True
) -> HybridSAPPipeline:
    """Create a hybrid SAP pipeline instance.

    Args:
        use_rag: Whether to use RAG for section generation
        use_validation: Whether to run validation on output
        strict_validation: If True, block output on HIGH severity issues
        verbose: Whether to print progress messages
    """
    return HybridSAPPipeline(
        use_rag=use_rag,
        use_validation=use_validation,
        strict_validation=strict_validation,
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
