#!/usr/bin/env python3
"""
Enterprise SAP Generation System - Orchestrator
=================================================
TIER 3: Multi-Agent SAP Generation Workflow

Main orchestrator that coordinates all agents for end-to-end SAP generation.
"""

import os
import json
import time
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Use relative imports for consistent module resolution
try:
    from ..core.config import get_config
    from ..core.schemas import (
        ParsedProtocol, Estimand, GeneratedSAP, QualityReport
    )
    from ..core.protocol_parser import ProtocolParser
    from ..knowledge_graph.graph_rag import BiostatisticsGraphRAG
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    from core.config import get_config
    from core.schemas import (
        ParsedProtocol, Estimand, GeneratedSAP, QualityReport
    )
    from core.protocol_parser import ProtocolParser
    from knowledge_graph.graph_rag import BiostatisticsGraphRAG

from .base_agent import BaseAgent, AgentRegistry, AgentState
from .specialized_agents import (
    EstimandArchitectAgent,
    MethodsSelectorAgent,
    SAPWriterAgent,
    QualityReviewerAgent
)

# Programmatic Enforcement - CRITICAL for protocol faithfulness
try:
    from ..core.programmatic_enforcer import (
        ProtocolVerbatimExtractor,
        SAPOutputEnforcer
    )
    ENFORCER_AVAILABLE = True
except ImportError:
    ENFORCER_AVAILABLE = False
    ProtocolVerbatimExtractor = None
    SAPOutputEnforcer = None

# Clinical Trial-Specific Extraction - For domain details
try:
    from ..core.clinical_extractor import ClinicalTrialExtractor
    from ..core.sap_section_templates import SAPSectionGenerator
    CLINICAL_EXTRACTOR_AVAILABLE = True
except ImportError:
    CLINICAL_EXTRACTOR_AVAILABLE = False
    ClinicalTrialExtractor = None
    SAPSectionGenerator = None

# RAG System for few-shot examples
try:
    from ..core.rag_system import RAGSystem
except ImportError:
    RAGSystem = None

# Production-level specification generators
try:
    from ..specs import (
        DerivationSpecGenerator,
        TLFShellGenerator,
        ProgrammingSpecGenerator
    )
except ImportError:
    DerivationSpecGenerator = None
    TLFShellGenerator = None
    ProgrammingSpecGenerator = None


@dataclass
class GenerationResult:
    """Result of SAP generation pipeline"""
    success: bool
    sap_document: Optional[GeneratedSAP] = None
    parsed_protocol: Optional[ParsedProtocol] = None
    estimands: Optional[Dict[str, Any]] = None
    methods: Optional[Dict[str, Any]] = None
    quality_report: Optional[QualityReport] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    execution_time: float = 0.0
    agent_states: Dict[str, Dict] = field(default_factory=dict)
    # Production-level specifications
    derivation_specs: Optional[str] = None
    tlf_specs: Optional[str] = None
    programming_specs: Optional[str] = None


class SAPGenerationOrchestrator:
    """
    Main orchestrator for multi-agent SAP generation.
    Coordinates protocol parsing, estimand design, method selection,
    and document generation.
    """

    def __init__(self, llm_client=None, use_rag: bool = True):
        """
        Initialize the orchestrator.

        Args:
            llm_client: Optional LLM client (will be created if not provided)
            use_rag: Whether to use GraphRAG for context augmentation
        """
        self.config = get_config()
        self.llm_client = llm_client
        self._init_llm_client()

        # Initialize components
        self.parser = ProtocolParser(llm_client=self.llm_client)

        # Initialize GraphRAG if enabled
        self.graph_rag = None
        if use_rag:
            try:
                self.graph_rag = BiostatisticsGraphRAG()
            except Exception as e:
                print(f"WARNING: GraphRAG initialization failed: {e}")

        # Initialize agents
        self.agent_registry = AgentRegistry()
        self._init_agents()

        # Initialize RAG System for few-shot examples (optional enhancement)
        self.rag_system = None
        if RAGSystem is not None:
            try:
                self.rag_system = RAGSystem()
                num_pairs = self.rag_system.load_and_filter_pairs()
                if num_pairs > 0:
                    self.rag_system.create_embeddings()
                    print(f"RAG system ready with {num_pairs} protocol-SAP pairs")
                else:
                    self.rag_system = None
            except Exception as e:
                # RAG is optional - proceed without it
                self.rag_system = None

        # Initialize production-level specification generators
        self.derivation_generator = None
        self.tlf_generator = None
        self.programming_generator = None

        if DerivationSpecGenerator is not None:
            self.derivation_generator = DerivationSpecGenerator(llm_client=self.llm_client)
        if TLFShellGenerator is not None:
            self.tlf_generator = TLFShellGenerator(llm_client=self.llm_client)
        if ProgrammingSpecGenerator is not None:
            self.programming_generator = ProgrammingSpecGenerator(llm_client=self.llm_client)

        # Initialize Programmatic Enforcer - CRITICAL for protocol faithfulness
        self.enforcer = None
        self.extractor = None
        if ENFORCER_AVAILABLE:
            self.extractor = ProtocolVerbatimExtractor()
            self.enforcer = SAPOutputEnforcer(self.extractor)
            print("Programmatic enforcer initialized - will validate SAP against protocol")

        # Initialize Clinical Extractor - For domain-specific details
        self.clinical_extractor = None
        self.section_generator = None
        if CLINICAL_EXTRACTOR_AVAILABLE:
            self.clinical_extractor = ClinicalTrialExtractor()
            self.section_generator = SAPSectionGenerator()
            print("Clinical extractor initialized - will extract domain-specific details")

    def _init_llm_client(self):
        """Initialize LLM client if not provided"""
        if self.llm_client is None:
            api_key = os.getenv("GROQ_API_KEY")
            if api_key:
                try:
                    from groq import Groq
                    self.llm_client = Groq(api_key=api_key)
                except ImportError:
                    print("ERROR: groq not installed. Run: pip install groq")
            else:
                print("ERROR: GROQ_API_KEY not set")

    def _init_agents(self):
        """Initialize all specialized agents"""
        self.estimand_agent = EstimandArchitectAgent(llm_client=self.llm_client)
        self.methods_agent = MethodsSelectorAgent(llm_client=self.llm_client)
        self.writer_agent = SAPWriterAgent(llm_client=self.llm_client)
        self.reviewer_agent = QualityReviewerAgent(llm_client=self.llm_client)

        self.agent_registry.register(self.estimand_agent)
        self.agent_registry.register(self.methods_agent)
        self.agent_registry.register(self.writer_agent)
        self.agent_registry.register(self.reviewer_agent)

    def generate_sap(
        self,
        protocol_text: str,
        nct_id: str = "",
        use_few_shot: bool = True,
        parallel_sections: bool = False,
        verbose: bool = True
    ) -> GenerationResult:
        """
        Generate a complete SAP from protocol text.

        Args:
            protocol_text: Full text of the clinical trial protocol
            nct_id: NCT identifier (will be extracted if not provided)
            use_few_shot: Whether to use few-shot examples
            parallel_sections: Whether to generate sections in parallel
            verbose: Print progress updates

        Returns:
            GenerationResult with generated SAP and metadata
        """
        start_time = time.time()
        result = GenerationResult(success=False)

        try:
            # Step 1: Parse Protocol
            if verbose:
                print("[1/7] Parsing protocol...")

            parsed_protocol = self.parser.parse(protocol_text, nct_id)
            result.parsed_protocol = parsed_protocol

            if verbose:
                print(f"      Phase: {parsed_protocol.phase.value if hasattr(parsed_protocol.phase, 'value') else parsed_protocol.phase}")
                print(f"      Endpoint: {parsed_protocol.primary_estimand.variable_type.value if parsed_protocol.primary_estimand else 'Unknown'}")
                print(f"      Therapeutic Area: {parsed_protocol.therapeutic_area}")

            # Step 2: Retrieve Knowledge Context
            knowledge_context = ""
            if self.graph_rag:
                if verbose:
                    print("[2/7] Retrieving knowledge context...")
                knowledge_context = self.graph_rag.retrieve_context(parsed_protocol)

            # Step 3: Design Estimands
            if verbose:
                print("[3/7] Designing estimands...")

            estimands = self.estimand_agent.execute(
                parsed_protocol=parsed_protocol,
                knowledge_context=knowledge_context
            )
            result.estimands = estimands

            if verbose:
                if estimands.get("primary_estimand"):
                    print(f"      Primary: {estimands['primary_estimand'].objective[:80]}...")
                print(f"      Secondary: {len(estimands.get('secondary_estimands', []))} estimands")

            # Step 4: Select Methods
            if verbose:
                print("[4/7] Selecting statistical methods...")

            methods = self.methods_agent.execute(
                parsed_protocol=parsed_protocol,
                estimands=estimands,
                knowledge_context=knowledge_context
            )
            result.methods = methods

            if verbose:
                if methods.get("primary_analysis"):
                    print(f"      Primary method: {methods['primary_analysis'].get('method_name', 'TBD')}")

            # Step 5: Generate SAP Sections
            if verbose:
                print("[5/7] Generating SAP sections...")

            # Get few-shot examples from RAG system
            few_shot_examples = None
            if use_few_shot and self.rag_system:
                try:
                    if verbose:
                        print("      Retrieving similar SAPs as examples...")

                    # Get therapeutic area and phase for filtering
                    ta = parsed_protocol.therapeutic_area or "OTHER"
                    phase = str(parsed_protocol.phase.value) if hasattr(parsed_protocol.phase, 'value') else str(parsed_protocol.phase)

                    # Retrieve similar protocols
                    similar_pairs = self.rag_system.retrieve_similar(
                        query_protocol=protocol_text[:10000],
                        k=2,  # Get top 2 similar examples
                        therapeutic_area=ta,
                        phase=phase
                    )

                    if similar_pairs:
                        # Format as few-shot context string
                        few_shot_examples = self.rag_system.format_few_shot_examples(
                            similar_pairs,
                            max_protocol_chars=2000,
                            max_sap_chars=6000
                        )
                        if verbose:
                            print(f"      Found {len(similar_pairs)} similar SAPs: {[p.nct_id for p in similar_pairs]}")
                except Exception as e:
                    if verbose:
                        print(f"      WARNING: RAG retrieval failed: {e}")

            # Combine RAG few-shot examples with knowledge context
            combined_context = knowledge_context or ""
            if few_shot_examples:
                combined_context = f"""## Similar Real SAPs (Use as Reference)

{few_shot_examples}

## Additional Context
{combined_context}
"""

            if parallel_sections:
                sap_sections = self._generate_sections_parallel(
                    parsed_protocol, estimands, methods,
                    None, combined_context, verbose  # Pass as context, not examples
                )
            else:
                sap_sections = self._generate_sections_sequential(
                    parsed_protocol, estimands, methods,
                    None, combined_context, verbose  # Pass as context, not examples
                )

            # Step 5b: PROGRAMMATIC ENFORCEMENT - Validate and correct SAP
            if self.enforcer and self.extractor:
                if verbose:
                    print("[5b/7] Applying programmatic enforcement...")

                # Extract ground truth from protocol
                protocol_extractions = self.extractor.extract_all(protocol_text)

                # Report extracted values
                if verbose:
                    ratio = protocol_extractions.get('randomization', {})
                    arms = protocol_extractions.get('treatment_arms', [])
                    alpha = protocol_extractions.get('alpha', {})
                    method = protocol_extractions.get('primary_analysis_method', {})

                    print(f"      Randomization: {ratio.get('ratio')} ({ratio.get('num_arms')} arms)")
                    print(f"      Treatment arms: {len(arms)} found")
                    for arm in arms:
                        print(f"        - {arm.get('name')}")
                    print(f"      Alpha: {alpha.get('sidedness')} {alpha.get('primary_alpha')}")
                    if alpha.get('additional_levels'):
                        print(f"        Additional levels: {alpha.get('additional_levels')}")
                    print(f"      Primary method: {method.get('method', 'Not specified')}")

                # Apply enforcement to each section
                total_violations = []
                total_corrections = []

                for section_name, section_content in sap_sections.items():
                    enforcement_result = self.enforcer.enforce_all(section_content, protocol_text)
                    sap_sections[section_name] = enforcement_result.corrected
                    total_violations.extend(enforcement_result.violations_found)
                    total_corrections.extend(enforcement_result.corrections_made)

                if verbose:
                    print(f"      Violations found: {len(total_violations)}")
                    print(f"      Corrections made: {len(total_corrections)}")
                    for corr in total_corrections[:5]:  # Show first 5
                        print(f"        ✓ {corr[:60]}...")

                # Store enforcement results in result
                result.warnings.extend([f"ENFORCEMENT: {v}" for v in total_violations])

            # Step 5c: CLINICAL EXTRACTION - Extract domain-specific details
            if self.clinical_extractor and self.section_generator:
                if verbose:
                    print("[5c/7] Extracting clinical trial-specific details...")

                # Extract all clinical details from protocol
                clinical_details = self.clinical_extractor.extract_all_clinical_details(protocol_text)

                if verbose:
                    # Report what was extracted
                    diary = clinical_details.get('diary_data_rules')
                    pk = clinical_details.get('pk_analysis_spec')
                    mods = clinical_details.get('scoring_modifications', [])
                    alpha = clinical_details.get('alpha_assignments', {})

                    if diary and diary.exclusion_rules:
                        print(f"      Diary exclusions: {len(diary.exclusion_rules)} rules")
                    if pk and pk.parameters:
                        print(f"      PK parameters: {len(pk.parameters)} found")
                    if mods:
                        print(f"      Scoring modifications: {len(mods)} found")
                    if alpha:
                        print(f"      Alpha levels: {alpha.get('sidedness')} at {alpha.get('primary_alpha')}")
                        if alpha.get('exploratory_alpha'):
                            print(f"        Exploratory: {alpha.get('exploratory_alpha')}")

                # Generate missing sections from templates
                additional_sections = self.section_generator.generate_all_missing_sections(clinical_details)

                if verbose:
                    print(f"      Generated {len(additional_sections)} additional sections:")
                    for section_name in additional_sections.keys():
                        print(f"        + {section_name}")

                # Append additional sections to SAP
                for section_name, section_content in additional_sections.items():
                    if section_content:  # Only add non-empty sections
                        # Add to appropriate location in SAP
                        sap_sections[f"additional_{section_name}"] = section_content

            # Step 6: Quality Review
            if verbose:
                print("[6/7] Reviewing quality...")

            quality_report = self.reviewer_agent.execute(
                generated_sap=sap_sections,
                parsed_protocol=parsed_protocol,
                estimands=estimands
            )
            result.quality_report = quality_report

            if verbose:
                print(f"      Overall Score: {quality_report.overall_score:.1f}/100")
                if quality_report.issues:
                    print(f"      Issues: {len(quality_report.issues)}")

            # Step 7: Generate Production-Level Specifications
            if verbose:
                print("[7/7] Generating production specifications...")

            # Generate derivation specs
            if self.derivation_generator:
                try:
                    result.derivation_specs = self.derivation_generator.generate_derivation_document(
                        parsed_protocol, estimands
                    )
                    if verbose:
                        print("      Generated ADaM derivation specifications")
                except Exception as e:
                    if verbose:
                        print(f"      WARNING: Derivation specs failed: {e}")

            # Generate TLF shells
            if self.tlf_generator:
                try:
                    result.tlf_specs = self.tlf_generator.generate_tlf_document(
                        parsed_protocol, estimands
                    )
                    if verbose:
                        print("      Generated TLF shell specifications")
                except Exception as e:
                    if verbose:
                        print(f"      WARNING: TLF specs failed: {e}")

            # Generate programming specs
            if self.programming_generator:
                try:
                    result.programming_specs = self.programming_generator.generate_programming_document(
                        parsed_protocol, estimands
                    )
                    if verbose:
                        print("      Generated SAS programming specifications")
                except Exception as e:
                    if verbose:
                        print(f"      WARNING: Programming specs failed: {e}")

            # Assemble final document with production appendices
            full_document = self._assemble_document(
                sap_sections, parsed_protocol, estimands,
                result.derivation_specs, result.tlf_specs, result.programming_specs
            )

            result.sap_document = GeneratedSAP(
                sections=sap_sections,
                full_document=full_document,
                protocol_id=parsed_protocol.nct_id,
                parsed_protocol=parsed_protocol,
                estimands=[estimands.get("primary_estimand")] + estimands.get("secondary_estimands", []),
                quality_report=quality_report,
                model_used=self.config.model.primary_model,
                rag_context_used=self.graph_rag is not None
            )

            result.success = True
            result.warnings = quality_report.warnings

        except Exception as e:
            result.errors.append(str(e))
            import traceback
            result.errors.append(traceback.format_exc())

        result.execution_time = time.time() - start_time
        result.agent_states = self.agent_registry.get_all_states()

        if verbose:
            print(f"\nCompleted in {result.execution_time:.1f}s")
            if result.success:
                print(f"SAP generated successfully!")
            else:
                print(f"Generation failed: {result.errors}")

        return result

    def _generate_sections_sequential(
        self,
        parsed_protocol: ParsedProtocol,
        estimands: Dict,
        methods: Dict,
        few_shot_examples: Dict,
        knowledge_context: str,
        verbose: bool
    ) -> Dict[str, str]:
        """Generate sections sequentially"""
        sections = {}
        section_names = [
            "1_introduction",
            "2_objectives_estimands",
            "3_study_design",
            "4_analysis_populations",
            "5_statistical_methods",
            "6_sample_size",
            "7_data_handling",
            "8_cdisc_alignment",
            "9_tlf_specifications"
        ]

        for i, section_name in enumerate(section_names):
            if verbose:
                print(f"      [{i+1}/{len(section_names)}] {section_name}")

            examples = (few_shot_examples or {}).get(section_name, [])
            sections[section_name] = self.writer_agent.execute(
                section_name=section_name,
                parsed_protocol=parsed_protocol,
                estimands=estimands,
                methods=methods,
                few_shot_examples=examples,
                knowledge_context=knowledge_context
            )

        return sections

    def _generate_sections_parallel(
        self,
        parsed_protocol: ParsedProtocol,
        estimands: Dict,
        methods: Dict,
        few_shot_examples: Dict,
        knowledge_context: str,
        verbose: bool
    ) -> Dict[str, str]:
        """Generate sections in parallel using thread pool"""
        sections = {}
        section_names = [
            "1_introduction",
            "2_objectives_estimands",
            "3_study_design",
            "4_analysis_populations",
            "5_statistical_methods",
            "6_sample_size",
            "7_data_handling",
            "8_cdisc_alignment",
            "9_tlf_specifications"
        ]

        def generate_section(section_name):
            examples = (few_shot_examples or {}).get(section_name, [])
            # Create a new writer agent for thread safety
            writer = SAPWriterAgent(llm_client=self.llm_client)
            return section_name, writer.execute(
                section_name=section_name,
                parsed_protocol=parsed_protocol,
                estimands=estimands,
                methods=methods,
                few_shot_examples=examples,
                knowledge_context=knowledge_context
            )

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(generate_section, name): name
                for name in section_names
            }

            for future in as_completed(futures):
                section_name, content = future.result()
                sections[section_name] = content
                if verbose:
                    print(f"      Completed: {section_name}")

        return sections

    def _assemble_document(
        self,
        sections: Dict[str, str],
        protocol: ParsedProtocol,
        estimands: Dict,
        derivation_specs: Optional[str] = None,
        tlf_specs: Optional[str] = None,
        programming_specs: Optional[str] = None
    ) -> str:
        """Assemble sections into complete SAP document with production appendices"""
        header = f"""# STATISTICAL ANALYSIS PLAN

**Study:** {protocol.nct_id}
**Title:** {protocol.study_title or 'TBD'}
**Phase:** {protocol.phase.value if hasattr(protocol.phase, 'value') else protocol.phase}
**Version:** 1.0
**Date:** {datetime.now().strftime('%d-%b-%Y')}

---

"""
        # Order sections properly
        ordered_sections = []
        for key in sorted(sections.keys()):
            ordered_sections.append(sections[key])

        # Build appendices with real specifications (not placeholders)
        appendix_parts = []

        # Appendix A: TLF Shells
        if tlf_specs:
            appendix_parts.append(f"""
---

## APPENDIX A: TLF SHELL SPECIFICATIONS

{tlf_specs}
""")
        else:
            appendix_parts.append("""
---

## APPENDIX A: TLF Shell Templates

*TLF shell specifications to be provided in separate document.*
""")

        # Appendix B: Derivation Specifications
        if derivation_specs:
            appendix_parts.append(f"""
---

## APPENDIX B: ADaM DERIVATION SPECIFICATIONS

{derivation_specs}
""")
        else:
            appendix_parts.append("""
---

## APPENDIX B: Derivation Specifications

*ADaM derivation specifications to be provided in separate document.*
""")

        # Appendix C: Programming Specifications
        if programming_specs:
            appendix_parts.append(f"""
---

## APPENDIX C: SAS PROGRAMMING SPECIFICATIONS

{programming_specs}
""")
        else:
            appendix_parts.append("""
---

## APPENDIX C: Programming Specifications

*SAS programming specifications to be provided in separate document.*
""")

        footer = """
---

**Document History**

| Version | Date | Author | Description |
|---------|------|--------|-------------|
| 1.0 | {date} | AI-Generated | Initial version |

---

*This SAP was generated using the Enterprise SAP Generation System with production-level specifications.*
""".format(date=datetime.now().strftime('%d-%b-%Y'))

        return header + "\n\n".join(ordered_sections) + "\n".join(appendix_parts) + footer

    def generate_from_file(
        self,
        protocol_path: str,
        output_path: str = None,
        **kwargs
    ) -> GenerationResult:
        """
        Generate SAP from protocol file.

        Args:
            protocol_path: Path to protocol file (txt or pdf)
            output_path: Path to save generated SAP
            **kwargs: Additional arguments passed to generate_sap

        Returns:
            GenerationResult
        """
        protocol_path = Path(protocol_path)

        if not protocol_path.exists():
            return GenerationResult(
                success=False,
                errors=[f"Protocol file not found: {protocol_path}"]
            )

        # Read protocol text
        protocol_text = protocol_path.read_text(encoding='utf-8', errors='ignore')

        # Extract NCT ID from filename if present
        nct_id = ""
        if "NCT" in protocol_path.stem.upper():
            import re
            match = re.search(r'(NCT\d{8})', protocol_path.stem.upper())
            if match:
                nct_id = match.group(1)

        # Generate SAP
        result = self.generate_sap(protocol_text, nct_id=nct_id, **kwargs)

        # Save if output path provided
        if output_path and result.success:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result.sap_document.full_document, encoding='utf-8')
            print(f"SAP saved to: {output_path}")

        return result


# Factory function
def create_orchestrator(use_rag: bool = True) -> SAPGenerationOrchestrator:
    """Create an orchestrator instance"""
    return SAPGenerationOrchestrator(use_rag=use_rag)
