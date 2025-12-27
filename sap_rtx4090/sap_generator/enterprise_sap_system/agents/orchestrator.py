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

        # Few-shot example selector (initialized lazily)
        self._few_shot_selector = None

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
                print("[1/6] Parsing protocol...")

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
                    print("[2/6] Retrieving knowledge context...")
                knowledge_context = self.graph_rag.retrieve_context(parsed_protocol)

            # Step 3: Design Estimands
            if verbose:
                print("[3/6] Designing estimands...")

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
                print("[4/6] Selecting statistical methods...")

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
                print("[5/6] Generating SAP sections...")

            few_shot_examples = None
            if use_few_shot and self._few_shot_selector:
                few_shot_examples = self._few_shot_selector.get_examples(parsed_protocol)

            if parallel_sections:
                sap_sections = self._generate_sections_parallel(
                    parsed_protocol, estimands, methods,
                    few_shot_examples, knowledge_context, verbose
                )
            else:
                sap_sections = self._generate_sections_sequential(
                    parsed_protocol, estimands, methods,
                    few_shot_examples, knowledge_context, verbose
                )

            # Step 6: Quality Review
            if verbose:
                print("[6/6] Reviewing quality...")

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

            # Assemble final document
            full_document = self._assemble_document(
                sap_sections, parsed_protocol, estimands
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
        estimands: Dict
    ) -> str:
        """Assemble sections into complete SAP document"""
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

        footer = """
---

## APPENDICES

### Appendix A: TLF Shell Templates
[To be added]

### Appendix B: Derivation Specifications
[To be added]

### Appendix C: Programming Specifications
[To be added]

---

**Document History**

| Version | Date | Author | Description |
|---------|------|--------|-------------|
| 1.0 | {date} | AI-Generated | Initial version |

---

*This SAP was generated using the Enterprise SAP Generation System.*
""".format(date=datetime.now().strftime('%d-%b-%Y'))

        return header + "\n\n".join(ordered_sections) + footer

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
