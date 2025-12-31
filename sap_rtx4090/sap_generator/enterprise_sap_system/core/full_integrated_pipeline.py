#!/usr/bin/env python3
"""
FULL Integrated Production SAP Pipeline
=========================================
This integrates ALL existing components into a single production pipeline:

LAYER 1: EXTRACTION
  - StructuredFactExtractor (regex-only, no LLM)
  - ProtocolParser (LLM-based protocol understanding)
  - ProtocolIdentityExtractor (from contamination_guard)

LAYER 2: KNOWLEDGE
  - BiostatisticsKnowledgeGraph (39 nodes, 36 edges)
  - RAG Vector Store (1,198 sections from 346 SAPs)
  - Specialized Templates (oncology, Phase 1, Phase 2/3, CAR-T)

LAYER 3: GENERATION
  - ConstrainedSAPPipeline (Literal types prevent hallucination)
  - Multi-Agent System (EstimandArchitect, MethodsSelector, SAPWriter, QualityReviewer)
  - Specification Generators (SDTM, TLF, ADaM)

LAYER 4: VALIDATION
  - HardValidator (blocks output if critical facts wrong)
  - ContaminationGuard (detects and cleans contamination)
  - QualityReviewer (scores completeness)

All components are from existing files - this just wires them together.
"""

import os
import re
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime


# =============================================================================
# IMPORTS FROM EXISTING COMPONENTS
# =============================================================================

# LAYER 1: Extraction
try:
    from .structured_extractor import StructuredFactExtractor, ProtocolFacts
    STRUCTURED_EXTRACTOR_AVAILABLE = True
except ImportError:
    STRUCTURED_EXTRACTOR_AVAILABLE = False
    print("Warning: structured_extractor not available")

try:
    from .contamination_guard import ProtocolIdentityExtractor, ContaminationGuard, ContaminationReport
    CONTAMINATION_GUARD_AVAILABLE = True
except ImportError:
    CONTAMINATION_GUARD_AVAILABLE = False
    print("Warning: contamination_guard not available")

# LAYER 2: Knowledge
try:
    from ..knowledge_graph.graph_rag import BiostatisticsKnowledgeGraph, RetrievedPath
    KNOWLEDGE_GRAPH_AVAILABLE = True
except ImportError:
    KNOWLEDGE_GRAPH_AVAILABLE = False
    print("Warning: knowledge_graph not available")

try:
    from ..rag.vector_store import SAPVectorStore, RetrievalResult
    RAG_VECTOR_STORE_AVAILABLE = True
except ImportError:
    RAG_VECTOR_STORE_AVAILABLE = False
    print("Warning: RAG vector_store not available")

try:
    from .specialized_oncology import (
        HEMATOLOGIC_TEMPLATES,
        PHASE1_TEMPLATES,
        CART_TEMPLATES,
        BASKET_UMBRELLA_TEMPLATES,
        get_hematologic_template,
        get_phase1_template,
        get_cart_template
    )
    SPECIALIZED_ONCOLOGY_AVAILABLE = True
except ImportError:
    SPECIALIZED_ONCOLOGY_AVAILABLE = False

try:
    from .phase2_phase3_templates import (
        PHASE2_SINGLE_ARM_TEMPLATES,
        PHASE3_TEMPLATES,
        SEAMLESS_TEMPLATES,
        Phase23Generator
    )
    PHASE23_TEMPLATES_AVAILABLE = True
except ImportError:
    PHASE23_TEMPLATES_AVAILABLE = False

# LAYER 3: Generation
try:
    from .constrained_pipeline import ConstrainedSAPPipeline
    CONSTRAINED_PIPELINE_AVAILABLE = True
except ImportError:
    CONSTRAINED_PIPELINE_AVAILABLE = False
    print("Warning: constrained_pipeline not available")

try:
    from ..agents.specialized_agents import (
        EstimandArchitectAgent,
        MethodsSelectorAgent,
        SAPWriterAgent,
        QualityReviewerAgent
    )
    AGENTS_AVAILABLE = True
except ImportError:
    AGENTS_AVAILABLE = False
    print("Warning: specialized_agents not available")

try:
    from ..specs.sdtm_specs import SDTMSpecGenerator
    from ..specs.tlf_shells import TLFShellGenerator
    from ..specs.derivation_specs import DerivationSpecGenerator
    SPEC_GENERATORS_AVAILABLE = True
except ImportError:
    SPEC_GENERATORS_AVAILABLE = False

# LAYER 4: Validation
try:
    from .hard_validator import HardValidator, ValidationResult
    HARD_VALIDATOR_AVAILABLE = True
except ImportError:
    HARD_VALIDATOR_AVAILABLE = False
    print("Warning: hard_validator not available")

try:
    from ..qa.issue_detector import IssueDetector, DetectionResult
    ISSUE_DETECTOR_AVAILABLE = True
except ImportError:
    ISSUE_DETECTOR_AVAILABLE = False


# =============================================================================
# RESULT DATACLASS
# =============================================================================

@dataclass
class FullPipelineResult:
    """Complete result from the full integrated pipeline"""
    success: bool = False
    sap_text: str = ""
    sections: Dict[str, str] = field(default_factory=dict)

    # Layer 1: Extracted facts
    protocol_facts: Any = None
    drug_name: str = ""
    sample_size: int = 0
    randomization_ratio: str = ""
    num_arms: int = 0
    phase: str = ""
    therapeutic_area: str = ""
    endpoint_type: str = ""
    primary_endpoint: str = ""

    # Layer 2: Knowledge augmentation
    knowledge_graph_paths: List[Dict] = field(default_factory=list)
    rag_examples: List[Dict] = field(default_factory=list)
    templates_applied: List[str] = field(default_factory=list)

    # Layer 3: Generation metadata
    generation_mode: str = ""  # "constrained", "multi_agent", "fallback"
    constrained_schema_used: bool = False
    agents_used: List[str] = field(default_factory=list)

    # Layer 4: Validation
    hard_validation: Any = None
    contamination_report: Any = None
    quality_score: float = 0.0
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Specifications (optional outputs)
    sdtm_specs: Any = None
    tlf_specs: Any = None
    adam_specs: Any = None

    # Timing
    extraction_time: float = 0.0
    knowledge_time: float = 0.0
    generation_time: float = 0.0
    validation_time: float = 0.0
    total_time: float = 0.0

    errors: List[str] = field(default_factory=list)


# =============================================================================
# FULL INTEGRATED PIPELINE
# =============================================================================

class FullIntegratedPipeline:
    """
    The FULL production pipeline integrating ALL components.

    This uses the EXISTING implementations from:
    - structured_extractor.py
    - contamination_guard.py
    - graph_rag.py
    - vector_store.py
    - specialized_oncology.py
    - phase2_phase3_templates.py
    - constrained_pipeline.py
    - specialized_agents.py
    - hard_validator.py
    - issue_detector.py
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

        print("=" * 70)
        print("FULL INTEGRATED PRODUCTION PIPELINE")
        print("=" * 70)

        # Initialize all components
        self._init_layer1_extraction()
        self._init_layer2_knowledge()
        self._init_layer3_generation()
        self._init_layer4_validation()

        print("=" * 70)
        print()

    def _init_layer1_extraction(self):
        """Initialize Layer 1: Extraction components"""
        print("\nLAYER 1: EXTRACTION")

        # Structured Fact Extractor
        self.fact_extractor = None
        if STRUCTURED_EXTRACTOR_AVAILABLE:
            try:
                self.fact_extractor = StructuredFactExtractor()
                print("  [OK] StructuredFactExtractor (regex-only)")
            except Exception as e:
                print(f"  [FAIL] StructuredFactExtractor: {e}")

        # Protocol Identity Extractor (from contamination guard)
        self.identity_extractor = None
        if CONTAMINATION_GUARD_AVAILABLE:
            try:
                self.identity_extractor = ProtocolIdentityExtractor()
                print("  [OK] ProtocolIdentityExtractor")
            except Exception as e:
                print(f"  [FAIL] ProtocolIdentityExtractor: {e}")

    def _init_layer2_knowledge(self):
        """Initialize Layer 2: Knowledge augmentation components"""
        print("\nLAYER 2: KNOWLEDGE")

        # Knowledge Graph
        self.knowledge_graph = None
        if KNOWLEDGE_GRAPH_AVAILABLE:
            try:
                self.knowledge_graph = BiostatisticsKnowledgeGraph()
                node_count = self.knowledge_graph.graph.number_of_nodes()
                edge_count = self.knowledge_graph.graph.number_of_edges()
                print(f"  [OK] BiostatisticsKnowledgeGraph ({node_count} nodes, {edge_count} edges)")
            except Exception as e:
                print(f"  [FAIL] BiostatisticsKnowledgeGraph: {e}")

        # RAG Vector Store
        self.rag_store = None
        if RAG_VECTOR_STORE_AVAILABLE:
            try:
                self.rag_store = SAPVectorStore()
                section_count = sum(len(c.get()) for c in self.rag_store.collections.values() if c)
                print(f"  [OK] SAPVectorStore ({section_count} sections)")
            except Exception as e:
                print(f"  [FAIL] SAPVectorStore: {e}")

        # Specialized Templates
        templates_loaded = []
        if SPECIALIZED_ONCOLOGY_AVAILABLE:
            templates_loaded.append("Oncology")
        if PHASE23_TEMPLATES_AVAILABLE:
            templates_loaded.append("Phase2/3")
            self.phase23_generator = Phase23Generator()

        if templates_loaded:
            print(f"  [OK] Specialized Templates ({', '.join(templates_loaded)})")
        else:
            print("  [SKIP] No specialized templates available")

    def _init_layer3_generation(self):
        """Initialize Layer 3: Generation components"""
        print("\nLAYER 3: GENERATION")

        # Constrained Pipeline (Literal types)
        self.constrained_pipeline = None
        if CONSTRAINED_PIPELINE_AVAILABLE:
            try:
                self.constrained_pipeline = ConstrainedSAPPipeline()
                print("  [OK] ConstrainedSAPPipeline (Literal types)")
            except Exception as e:
                print(f"  [FAIL] ConstrainedSAPPipeline: {e}")

        # Multi-Agent System
        self.agents = {}
        if AGENTS_AVAILABLE:
            try:
                self.agents['estimand'] = EstimandArchitectAgent()
                self.agents['methods'] = MethodsSelectorAgent()
                self.agents['writer'] = SAPWriterAgent()
                self.agents['reviewer'] = QualityReviewerAgent()
                print(f"  [OK] Multi-Agent System ({len(self.agents)} agents)")
            except Exception as e:
                print(f"  [FAIL] Multi-Agent System: {e}")

        # Specification Generators
        self.spec_generators = {}
        if SPEC_GENERATORS_AVAILABLE:
            try:
                self.spec_generators['sdtm'] = SDTMSpecGenerator()
                self.spec_generators['tlf'] = TLFShellGenerator()
                self.spec_generators['adam'] = DerivationSpecGenerator()
                print(f"  [OK] Specification Generators (SDTM, TLF, ADaM)")
            except Exception as e:
                print(f"  [FAIL] Specification Generators: {e}")

    def _init_layer4_validation(self):
        """Initialize Layer 4: Validation components"""
        print("\nLAYER 4: VALIDATION")

        # Hard Validator
        self.hard_validator = None
        if HARD_VALIDATOR_AVAILABLE:
            try:
                self.hard_validator = HardValidator(strict_mode=True)
                print("  [OK] HardValidator (strict mode)")
            except Exception as e:
                print(f"  [FAIL] HardValidator: {e}")

        # Contamination Guard
        self.contamination_guard = None
        if CONTAMINATION_GUARD_AVAILABLE:
            try:
                self.contamination_guard = ContaminationGuard()
                print("  [OK] ContaminationGuard")
            except Exception as e:
                print(f"  [FAIL] ContaminationGuard: {e}")

        # Issue Detector (QA)
        self.issue_detector = None
        if ISSUE_DETECTOR_AVAILABLE:
            try:
                self.issue_detector = IssueDetector()
                print("  [OK] IssueDetector (QA)")
            except Exception as e:
                print(f"  [FAIL] IssueDetector: {e}")

    def generate(
        self,
        protocol_text: str,
        nct_id: str = None,
        generate_specs: bool = False,
        mode: str = "auto"  # "constrained", "multi_agent", "auto"
    ) -> FullPipelineResult:
        """
        Run the full integrated pipeline.

        Args:
            protocol_text: The protocol document text
            nct_id: Optional NCT ID override
            generate_specs: Whether to generate SDTM/TLF/ADaM specs
            mode: Generation mode - "constrained" (Literal types), "multi_agent", or "auto"

        Returns:
            FullPipelineResult with complete SAP and metadata
        """
        result = FullPipelineResult()
        start_time = time.time()

        try:
            # =================================================================
            # LAYER 1: EXTRACTION
            # =================================================================
            if self.verbose:
                print("\n" + "=" * 60)
                print("LAYER 1: EXTRACTION")
                print("=" * 60)

            t0 = time.time()

            # Extract protocol facts using structured extractor
            if self.fact_extractor:
                try:
                    result.protocol_facts = self.fact_extractor.extract_all(protocol_text)
                    result.drug_name = result.protocol_facts.drug_name or ""
                    result.sample_size = result.protocol_facts.sample_size.total_n if result.protocol_facts.sample_size else 0
                    result.randomization_ratio = result.protocol_facts.randomization.ratio if result.protocol_facts.randomization else ""
                    result.num_arms = len(result.protocol_facts.treatment_arms) if result.protocol_facts.treatment_arms else 2
                    result.phase = str(result.protocol_facts.phase) if result.protocol_facts.phase else ""
                except Exception as e:
                    if self.verbose:
                        print(f"  [WARN] StructuredFactExtractor failed: {e}")
                    result.errors.append(f"Fact extraction error: {e}")

            # Extract identity for contamination checking
            if self.identity_extractor:
                try:
                    identity = self.identity_extractor.extract_identity(protocol_text)
                    if not result.drug_name and identity.drug_name:
                        result.drug_name = identity.drug_name
                    if not result.sample_size and identity.sample_size:
                        result.sample_size = identity.sample_size
                    result.therapeutic_area = identity.therapeutic_area or ""
                except Exception as e:
                    if self.verbose:
                        print(f"  [WARN] IdentityExtractor failed: {e}")

            # Fallback extraction if structured extractor failed
            if not result.drug_name or not result.sample_size:
                self._fallback_extraction(protocol_text, result)

            if nct_id and result.protocol_facts:
                result.protocol_facts.nct_id = nct_id

            result.extraction_time = time.time() - t0

            if self.verbose:
                print(f"  Drug: {result.drug_name}")
                print(f"  Sample Size: {result.sample_size}")
                print(f"  Ratio: {result.randomization_ratio}")
                print(f"  Phase: {result.phase}")
                print(f"  Therapeutic Area: {result.therapeutic_area}")
                print(f"  Time: {result.extraction_time:.2f}s")

            # =================================================================
            # LAYER 2: KNOWLEDGE AUGMENTATION
            # =================================================================
            if self.verbose:
                print("\n" + "=" * 60)
                print("LAYER 2: KNOWLEDGE AUGMENTATION")
                print("=" * 60)

            t0 = time.time()

            # Query Knowledge Graph
            if self.knowledge_graph:
                try:
                    # Determine endpoint type
                    endpoint_type = self._detect_endpoint_type(protocol_text)
                    result.endpoint_type = endpoint_type

                    # Get subgraph for endpoint type
                    subgraph = self.knowledge_graph.get_subgraph_for_endpoint(endpoint_type.upper())
                    entities = list(subgraph.nodes())
                    result.knowledge_graph_paths = [
                        {'entities': entities[:5], 'evidence': f'Methods for {endpoint_type}'}
                    ]

                    if self.verbose and entities:
                        print(f"  [KG] Retrieved {len(entities)} entities for {endpoint_type}")
                        print(f"      → {', '.join(entities[:5])}")
                except Exception as e:
                    if self.verbose:
                        print(f"  [WARN] Knowledge graph query failed: {e}")

            # Query RAG Vector Store
            if self.rag_store:
                try:
                    rag_results = self.rag_store.query(
                        query_text=protocol_text[:2000],
                        section_type="methods",
                        n_results=3
                    )
                    result.rag_examples = [
                        {'nct_id': r.nct_id, 'section': r.section_type, 'score': r.relevance_score}
                        for r in rag_results
                    ]

                    if self.verbose and rag_results:
                        print(f"  [RAG] Retrieved {len(rag_results)} similar sections")
                        for r in rag_results[:2]:
                            print(f"      → {r.nct_id} ({r.section_type}): {r.relevance_score:.2f}")
                except Exception as e:
                    if self.verbose:
                        print(f"  [WARN] RAG retrieval failed: {e}")

            # Select Specialized Templates
            templates = self._select_templates(protocol_text, result)
            result.templates_applied = templates

            if self.verbose and templates:
                print(f"  [Templates] Applied: {', '.join(templates)}")

            result.knowledge_time = time.time() - t0

            # =================================================================
            # LAYER 3: GENERATION
            # =================================================================
            if self.verbose:
                print("\n" + "=" * 60)
                print("LAYER 3: GENERATION")
                print("=" * 60)

            t0 = time.time()

            # Determine generation mode
            if mode == "auto":
                if self.constrained_pipeline:
                    mode = "constrained"
                elif self.agents:
                    mode = "multi_agent"
                else:
                    mode = "fallback"

            result.generation_mode = mode

            if mode == "constrained" and self.constrained_pipeline:
                # Use constrained pipeline with Literal types
                if self.verbose:
                    print("  [Mode] Constrained (Literal types)")

                try:
                    constrained_result = self.constrained_pipeline.generate(
                        protocol_text=protocol_text,
                        nct_id=nct_id
                    )
                    result.sap_text = constrained_result.sap_text  # Correct attribute name
                    result.sections = constrained_result.sections
                    result.constrained_schema_used = True

                    if constrained_result.success:
                        if self.verbose:
                            print(f"  [OK] Generated {len(result.sections)} sections")
                    else:
                        if self.verbose:
                            print(f"  [PARTIAL] Generated with warnings: {constrained_result.warnings}")
                except Exception as e:
                    if self.verbose:
                        print(f"  [FAIL] Constrained generation failed: {e}")
                    result.errors.append(f"Constrained generation error: {e}")
                    mode = "fallback"  # Fall back

            if mode == "multi_agent" and self.agents:
                # Use multi-agent system
                if self.verbose:
                    print("  [Mode] Multi-Agent System")

                try:
                    # 1. EstimandArchitect
                    estimands = self.agents['estimand'].design_estimands(protocol_text)
                    result.agents_used.append("EstimandArchitect")

                    # 2. MethodsSelector
                    methods = self.agents['methods'].select_methods(result.endpoint_type)
                    result.agents_used.append("MethodsSelector")

                    # 3. SAPWriter
                    sap_result = self.agents['writer'].write_sap(
                        protocol_text, estimands, methods
                    )
                    result.sap_text = sap_result.full_document
                    result.sections = sap_result.sections
                    result.agents_used.append("SAPWriter")

                    # 4. QualityReviewer
                    review = self.agents['reviewer'].review(result.sap_text)
                    result.quality_score = review.score
                    result.agents_used.append("QualityReviewer")

                    if self.verbose:
                        print(f"  [OK] Agents used: {', '.join(result.agents_used)}")
                except Exception as e:
                    if self.verbose:
                        print(f"  [FAIL] Multi-agent generation failed: {e}")
                    result.errors.append(f"Multi-agent error: {e}")
                    mode = "fallback"

            if mode == "fallback" or not result.sap_text:
                # Fallback generation
                if self.verbose:
                    print("  [Mode] Fallback (template-based)")

                result.sap_text = self._generate_fallback_sap(result)
                result.generation_mode = "fallback"

            result.generation_time = time.time() - t0

            if self.verbose:
                print(f"  [Time] {result.generation_time:.2f}s")

            # =================================================================
            # LAYER 4: VALIDATION
            # =================================================================
            if self.verbose:
                print("\n" + "=" * 60)
                print("LAYER 4: VALIDATION")
                print("=" * 60)

            t0 = time.time()

            # Hard Validation
            if self.hard_validator and result.protocol_facts:
                try:
                    validation = self.hard_validator.validate(result.sap_text, result.protocol_facts)
                    result.hard_validation = validation

                    if validation.block_output:
                        result.issues.append("BLOCKED: Hard validation failed")
                        if self.verbose:
                            print(f"  [BLOCKED] {validation.summary()}")
                    else:
                        if self.verbose:
                            print(f"  [HardValidator] {validation.summary()}")
                except Exception as e:
                    if self.verbose:
                        print(f"  [WARN] Hard validation failed: {e}")

            # Contamination Check
            if self.contamination_guard:
                try:
                    # Use check_and_clean which handles identity extraction internally
                    cleaned_sap, contamination, changes = self.contamination_guard.check_and_clean(
                        result.sap_text, protocol_text
                    )
                    result.contamination_report = contamination

                    if contamination.is_contaminated:
                        result.sap_text = cleaned_sap  # Use cleaned version
                        result.warnings.append(f"Contamination detected and cleaned: {contamination.severity}")
                        if self.verbose:
                            print(f"  [ContaminationGuard] CONTAMINATED → CLEANED ({len(changes)} fixes)")
                            for change in changes[:3]:
                                print(f"      → {change}")
                    else:
                        if self.verbose:
                            print("  [ContaminationGuard] Clean")
                except Exception as e:
                    if self.verbose:
                        print(f"  [WARN] Contamination check failed: {e}")

            # QA Issue Detection
            if self.issue_detector and result.protocol_facts and result.sections:
                try:
                    detection = self.issue_detector.detect(result.protocol_facts, result.sections)
                    result.issues.extend([i.message for i in detection.errors])
                    result.warnings.extend([i.message for i in detection.warnings])

                    if self.verbose:
                        print(f"  [QA] {len(detection.errors)} errors, {len(detection.warnings)} warnings")
                except Exception as e:
                    if self.verbose:
                        print(f"  [WARN] QA detection failed: {e}")

            # Calculate final quality score
            if not result.quality_score:
                result.quality_score = self._calculate_quality_score(result)

            result.validation_time = time.time() - t0

            if self.verbose:
                print(f"  [Quality] {result.quality_score:.1f}/100")
                print(f"  [Time] {result.validation_time:.2f}s")

            # =================================================================
            # OPTIONAL: SPECIFICATION GENERATION
            # =================================================================
            if generate_specs and self.spec_generators:
                if self.verbose:
                    print("\n" + "=" * 60)
                    print("SPECIFICATION GENERATION")
                    print("=" * 60)

                # Generate SDTM specs
                if 'sdtm' in self.spec_generators:
                    try:
                        result.sdtm_specs = self.spec_generators['sdtm'].generate(result.sap_text)
                        if self.verbose:
                            print("  [OK] SDTM specifications generated")
                    except Exception as e:
                        if self.verbose:
                            print(f"  [FAIL] SDTM generation: {e}")

                # Generate TLF specs
                if 'tlf' in self.spec_generators:
                    try:
                        result.tlf_specs = self.spec_generators['tlf'].generate(result.sap_text)
                        if self.verbose:
                            print("  [OK] TLF specifications generated")
                    except Exception as e:
                        if self.verbose:
                            print(f"  [FAIL] TLF generation: {e}")

                # Generate ADaM specs
                if 'adam' in self.spec_generators:
                    try:
                        result.adam_specs = self.spec_generators['adam'].generate(result.sap_text)
                        if self.verbose:
                            print("  [OK] ADaM specifications generated")
                    except Exception as e:
                        if self.verbose:
                            print(f"  [FAIL] ADaM generation: {e}")

            # =================================================================
            # FINAL RESULT
            # =================================================================
            result.total_time = time.time() - start_time
            result.success = (
                len(result.sap_text) > 1000 and
                result.quality_score >= 70 and
                not any("BLOCKED" in i for i in result.issues)
            )

            if self.verbose:
                print("\n" + "=" * 60)
                print("PIPELINE COMPLETE")
                print("=" * 60)
                print(f"  Success: {result.success}")
                print(f"  Quality: {result.quality_score:.1f}/100")
                print(f"  Mode: {result.generation_mode}")
                print(f"  Total Time: {result.total_time:.2f}s")
                print("=" * 60)

        except Exception as e:
            result.errors.append(f"Pipeline error: {e}")
            result.total_time = time.time() - start_time
            if self.verbose:
                print(f"\n[FATAL ERROR] {e}")
                import traceback
                traceback.print_exc()

        return result

    def _fallback_extraction(self, protocol_text: str, result: FullPipelineResult):
        """Fallback regex extraction if structured extractor fails"""
        # Drug name
        drug_patterns = [
            r'([A-Za-z]+(?:mab|nib|simod|stat|pril|sartan))',
            r'(?:study of|trial of)\s+([A-Za-z][A-Za-z0-9-]+)',
        ]
        for pattern in drug_patterns:
            match = re.search(pattern, protocol_text, re.IGNORECASE)
            if match and not result.drug_name:
                result.drug_name = match.group(1).capitalize()
                break

        # Sample size
        size_match = re.search(r'(\d+)\s*(?:patients|subjects)', protocol_text, re.IGNORECASE)
        if size_match and not result.sample_size:
            result.sample_size = int(size_match.group(1))

        # Ratio
        ratio_match = re.search(r'(\d+:\d+)', protocol_text)
        if ratio_match and not result.randomization_ratio:
            result.randomization_ratio = ratio_match.group(1)

    def _detect_endpoint_type(self, protocol_text: str) -> str:
        """Detect primary endpoint type"""
        text_lower = protocol_text.lower()

        if any(x in text_lower for x in ['overall survival', 'progression-free', 'pfs', ' os ']):
            return "time_to_event"
        elif any(x in text_lower for x in ['change from baseline', 'mean change']):
            return "continuous"
        elif any(x in text_lower for x in ['remission', 'response', 'proportion']):
            return "binary"
        return "binary"

    def _select_templates(self, protocol_text: str, result: FullPipelineResult) -> List[str]:
        """Select appropriate specialized templates"""
        templates = []
        text_lower = protocol_text.lower()

        # Oncology templates
        if 'cancer' in text_lower or 'tumor' in text_lower:
            if 'car-t' in text_lower or 'chimeric' in text_lower:
                templates.append("CAR-T")
            elif 'basket' in text_lower or 'umbrella' in text_lower:
                templates.append("Basket/Umbrella")
            elif 'lymphoma' in text_lower or 'myeloma' in text_lower:
                templates.append("Hematologic")
            elif 'phase 1' in text_lower or 'dose escalation' in text_lower:
                templates.append("Phase1-Oncology")
            else:
                templates.append("Solid-Tumor")

        # Phase 2/3 templates
        if 'simon' in text_lower or 'two-stage' in text_lower:
            templates.append("Simon-TwoStage")
        if 'group sequential' in text_lower:
            templates.append("GroupSequential")

        # IBD templates
        if 'colitis' in text_lower or 'crohn' in text_lower:
            templates.append("IBD")

        return templates

    def _calculate_quality_score(self, result: FullPipelineResult) -> float:
        """Calculate quality score based on completeness and validation"""
        score = 100.0

        # Deduct for missing drug name
        if not result.drug_name:
            score -= 15

        # Deduct for missing sample size
        if not result.sample_size:
            score -= 15

        # Deduct for issues
        score -= len(result.issues) * 10
        score -= len(result.warnings) * 5

        # Deduct for short SAP
        if len(result.sap_text) < 2000:
            score -= 20

        # Deduct for contamination
        if result.contamination_report and result.contamination_report.is_contaminated:
            score -= 25

        return max(0, min(100, score))

    def _generate_fallback_sap(self, result: FullPipelineResult) -> str:
        """Generate fallback SAP using templates"""
        drug = result.drug_name or "study drug"
        n = result.sample_size or "TBD"
        ratio = result.randomization_ratio or "1:1"
        phase = result.phase or "Phase 3"
        ta = result.therapeutic_area or "Not specified"

        return f"""# STATISTICAL ANALYSIS PLAN

**Protocol:** {result.protocol_facts.nct_id if result.protocol_facts else 'TBD'}
**Drug:** {drug}
**Phase:** {phase}
**Date:** {datetime.now().strftime('%d-%b-%Y')}

---

## 1. Introduction

This Statistical Analysis Plan describes the statistical methods for the {phase} study of {drug}.

## 2. Study Design

- **Sample Size:** {n} patients
- **Randomization:** {ratio}
- **Therapeutic Area:** {ta}

## 3. Analysis Populations

- **Full Analysis Set (FAS):** All randomized subjects
- **Safety Population:** All subjects receiving ≥1 dose
- **Per-Protocol:** FAS without major protocol deviations

## 4. Statistical Methods

Primary analysis will use appropriate methods based on endpoint type.

## 5. Sample Size Justification

Sample size of {n} provides adequate power for the primary analysis.

## 6. Missing Data

Missing data handled using multiple imputation or MMRM as appropriate.

---

*Generated using Full Integrated Pipeline (Fallback Mode)*
"""


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_full_pipeline(verbose: bool = True) -> FullIntegratedPipeline:
    """Create a full integrated pipeline instance"""
    return FullIntegratedPipeline(verbose=verbose)


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    pipeline = create_full_pipeline()

    test_protocol = """
    Protocol: NCT03422848

    A Phase 3, Randomized, Double-Blind, Placebo-Controlled Study of
    Etrasimod in Patients with Moderately to Severely Active Ulcerative Colitis

    Approximately 400 patients will be randomized in a 2:1 ratio.

    Primary Endpoint: Clinical remission at Week 12.
    """

    result = pipeline.generate(test_protocol, nct_id="NCT03422848")

    print("\n\nRESULT SUMMARY:")
    print(f"Success: {result.success}")
    print(f"Drug: {result.drug_name}")
    print(f"Mode: {result.generation_mode}")
    print(f"Quality: {result.quality_score:.1f}/100")
