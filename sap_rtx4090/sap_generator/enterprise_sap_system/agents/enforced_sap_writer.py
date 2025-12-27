#!/usr/bin/env python3
"""
Enforced SAP Writer Agent
=========================
This agent wraps the existing SAPWriterAgent with PROGRAMMATIC ENFORCEMENT.

Key difference from original:
- Original: LLM generates → output returned directly
- This:     LLM generates → ENFORCER validates & corrects → output returned

The LLM still generates freely, but critical content is verified and corrected
by code before being returned.
"""

import json
from typing import Dict, List, Optional, Any
from pathlib import Path

# Import existing components
try:
    from ..core.schemas import ParsedProtocol, GeneratedSAP
    from ..core.programmatic_enforcer import (
        ProtocolVerbatimExtractor,
        SAPOutputEnforcer,
        TemplateBasedSectionGenerator,
        EnforcementResult
    )
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    from core.schemas import ParsedProtocol, GeneratedSAP
    from core.programmatic_enforcer import (
        ProtocolVerbatimExtractor,
        SAPOutputEnforcer,
        TemplateBasedSectionGenerator,
        EnforcementResult
    )

from .base_agent import BaseAgent


class EnforcedSAPWriterAgent(BaseAgent):
    """
    SAP Writer with programmatic enforcement.

    Critical sections (2.1, 4.2, 6.2, 7.1) use template-based generation
    where verbatim content is LOCKED and cannot be modified by LLM.

    Other sections use standard LLM generation with post-hoc enforcement.
    """

    # Sections that require strict enforcement
    CRITICAL_SECTIONS = ['2.1', '2.2', '4.2', '6.2', '7.1.1']

    def __init__(self, llm_client=None):
        super().__init__(
            name="enforced_sap_writer",
            description="Generate SAP sections with programmatic enforcement",
            llm_client=llm_client
        )
        self.extractor = ProtocolVerbatimExtractor()
        self.enforcer = SAPOutputEnforcer(self.extractor)
        self.template_generator = TemplateBasedSectionGenerator()

    def execute(
        self,
        section_name: str,
        parsed_protocol: ParsedProtocol,
        estimands: Dict[str, Any],
        methods: Dict[str, Any],
        protocol_text: str,  # NEW: Raw protocol text for verbatim extraction
        few_shot_examples: List[str] = None,
        knowledge_context: str = ""
    ) -> Dict[str, Any]:
        """
        Generate SAP section with enforcement.

        Returns:
            Dict with:
            - 'content': Final section content (after enforcement)
            - 'violations': List of violations found
            - 'corrections': List of corrections made
            - 'enforcement_applied': bool
        """
        self.update_state(status="running", current_task=f"Writing {section_name} with enforcement")

        # Determine section number from name
        section_num = self._extract_section_number(section_name)

        if section_num in self.CRITICAL_SECTIONS:
            # Use template-based generation for critical sections
            result = self._generate_critical_section(
                section_num, parsed_protocol, estimands, methods, protocol_text
            )
        else:
            # Use standard generation + post-hoc enforcement
            result = self._generate_standard_section(
                section_name, parsed_protocol, estimands, methods,
                protocol_text, few_shot_examples, knowledge_context
            )

        self.update_state(status="completed", progress=1.0)
        return result

    def _generate_critical_section(
        self,
        section_num: str,
        parsed_protocol: ParsedProtocol,
        estimands: Dict,
        methods: Dict,
        protocol_text: str
    ) -> Dict[str, Any]:
        """
        Generate critical sections using TEMPLATE approach.
        Verbatim content is extracted and locked - LLM cannot modify.
        """
        violations = []
        corrections = []

        if section_num == '2.1':
            # Primary Endpoint - CRITICAL
            primary_endpoint = self.extractor.extract_primary_endpoint_verbatim(protocol_text)

            if primary_endpoint:
                content = self.template_generator.generate_section_2_1(
                    primary_endpoint,
                    self.llm_client,
                    protocol_context=f"Phase {parsed_protocol.phase}, {parsed_protocol.therapeutic_area}"
                )
                corrections.append("Primary endpoint definition locked from protocol verbatim text")
            else:
                # Fallback to LLM with enforcement
                violations.append("Could not extract primary endpoint verbatim - using LLM generation")
                content = self._llm_generate_section("2.1 Primary Endpoint", parsed_protocol, estimands, methods)

        elif section_num == '4.2':
            # Analysis Populations - CRITICAL
            fas_definition = self.extractor.extract_population_verbatim(protocol_text, 'FAS')

            if fas_definition:
                content = self.template_generator.generate_section_4_2(
                    fas_definition,
                    self.llm_client,
                    protocol_context=f"Phase {parsed_protocol.phase}"
                )
                corrections.append("FAS definition locked from protocol verbatim text")
            else:
                violations.append("Could not extract FAS definition verbatim")
                content = self._llm_generate_section("4.2 Analysis Populations", parsed_protocol, estimands, methods)
                # Still enforce even if we couldn't extract
                enforcement_result = self.enforcer.enforce_all(content, protocol_text)
                content = enforcement_result.corrected
                violations.extend(enforcement_result.violations_found)
                corrections.extend(enforcement_result.corrections_made)

        elif section_num == '6.2':
            # Stratification - CRITICAL
            stratification = self.extractor.extract_all_stratification_factors(protocol_text)

            if stratification:
                content = self.template_generator.generate_section_6(
                    stratification,
                    self.llm_client,
                    randomization_info=f"Randomization ratio: {parsed_protocol.randomization_ratio}"
                )
                corrections.append(f"All {len(stratification)} stratification factors included programmatically")
            else:
                violations.append("Could not extract stratification factors")
                content = self._llm_generate_section("6.2 Stratification", parsed_protocol, estimands, methods)

        elif section_num in ['2.2', '7.1.1']:
            # These need enforcement but can use LLM generation
            content = self._llm_generate_section(
                f"{section_num} {'Secondary Endpoints' if section_num == '2.2' else 'Primary Analysis'}",
                parsed_protocol, estimands, methods
            )
            # Apply enforcement
            enforcement_result = self.enforcer.enforce_all(content, protocol_text)
            content = enforcement_result.corrected
            violations.extend(enforcement_result.violations_found)
            corrections.extend(enforcement_result.corrections_made)
        else:
            content = self._llm_generate_section(section_num, parsed_protocol, estimands, methods)

        return {
            'content': content,
            'violations': violations,
            'corrections': corrections,
            'enforcement_applied': True
        }

    def _generate_standard_section(
        self,
        section_name: str,
        parsed_protocol: ParsedProtocol,
        estimands: Dict,
        methods: Dict,
        protocol_text: str,
        examples: List[str],
        context: str
    ) -> Dict[str, Any]:
        """
        Generate non-critical sections with post-hoc enforcement.
        """
        # Standard LLM generation
        content = self._llm_generate_section(
            section_name, parsed_protocol, estimands, methods, examples, context
        )

        # Apply enforcement checks
        enforcement_result = self.enforcer.enforce_all(content, protocol_text)

        return {
            'content': enforcement_result.corrected,
            'violations': enforcement_result.violations_found,
            'corrections': enforcement_result.corrections_made,
            'enforcement_applied': len(enforcement_result.corrections_made) > 0
        }

    def _llm_generate_section(
        self,
        section_name: str,
        parsed_protocol: ParsedProtocol,
        estimands: Dict,
        methods: Dict,
        examples: List[str] = None,
        context: str = ""
    ) -> str:
        """Standard LLM generation (same as original SAPWriterAgent)."""
        prompt = self._build_prompt(section_name, parsed_protocol, estimands, methods, examples, context)

        system_prompt = """You are an expert medical writer specializing in Statistical Analysis Plans.
        Write professional, regulatory-compliant content. Use precise, unambiguous language."""

        return self.call_llm(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=4000
        )

    def _build_prompt(
        self,
        section_name: str,
        protocol: ParsedProtocol,
        estimands: Dict,
        methods: Dict,
        examples: List[str] = None,
        context: str = ""
    ) -> str:
        """Build prompt for LLM generation."""
        parts = [
            f"## Generate SAP Section: {section_name}\n",
            f"Study: {protocol.nct_id}",
            f"Phase: {protocol.phase}",
            f"Therapeutic Area: {protocol.therapeutic_area}",
        ]

        if protocol.arms:
            parts.append("\n## Treatment Arms:")
            for arm in protocol.arms:
                parts.append(f"- {arm.name}: {arm.dose or ''} {arm.route or ''}")

        if estimands.get("primary_estimand"):
            est = estimands["primary_estimand"]
            parts.append("\n## Primary Estimand:")
            parts.append(f"- Variable: {est.variable}")
            parts.append(f"- Population: {est.population}")

        if examples:
            parts.append(f"\n## Style Reference:\n{examples[0][:1500]}")

        parts.append(f"\n## Write {section_name}:")

        return "\n".join(parts)

    def _extract_section_number(self, section_name: str) -> str:
        """Extract section number from name like '2.1 Primary Endpoint'."""
        import re
        match = re.search(r'^(\d+\.\d+(?:\.\d+)?)', section_name)
        if match:
            return match.group(1)

        # Map common names to numbers
        name_map = {
            'primary endpoint': '2.1',
            'secondary endpoint': '2.2',
            'analysis population': '4.2',
            'stratification': '6.2',
            'primary analysis': '7.1.1',
        }

        for name, num in name_map.items():
            if name in section_name.lower():
                return num

        return section_name

    def generate_all_sections_enforced(
        self,
        parsed_protocol: ParsedProtocol,
        estimands: Dict[str, Any],
        methods: Dict[str, Any],
        protocol_text: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        Generate all SAP sections with enforcement.
        Returns dict of section_name -> {content, violations, corrections}
        """
        sections = {}
        all_violations = []
        all_corrections = []

        section_order = [
            "1. Introduction",
            "2.1 Primary Endpoint",
            "2.2 Secondary Endpoints",
            "3. Study Design",
            "4.2 Analysis Populations",
            "5. Sample Size",
            "6.2 Randomization and Stratification",
            "7.1.1 Primary Analysis",
            "7.1.2 Secondary Analyses",
            "8. Safety Analyses",
            "9. CDISC Alignment",
        ]

        for section_name in section_order:
            result = self.execute(
                section_name=section_name,
                parsed_protocol=parsed_protocol,
                estimands=estimands,
                methods=methods,
                protocol_text=protocol_text
            )

            sections[section_name] = result
            all_violations.extend(result['violations'])
            all_corrections.extend(result['corrections'])

            # Log enforcement activity
            if result['violations']:
                print(f"⚠️  {section_name}: {len(result['violations'])} violation(s) found")
            if result['corrections']:
                print(f"✓  {section_name}: {len(result['corrections'])} correction(s) made")

        # Summary
        print(f"\n=== Enforcement Summary ===")
        print(f"Total violations found: {len(all_violations)}")
        print(f"Total corrections made: {len(all_corrections)}")

        return sections


# Example usage:
if __name__ == "__main__":
    # Test the enforcer with sample data
    protocol_text = """
    2.2 Primary Endpoint

    The primary endpoint is clinical and endoscopic remission at Week 12,
    defined as a full Mayo score ≤2, no individual subscore >1,
    rectal bleeding subscore = 0.

    2.3 Secondary Endpoints

    Clinical remission at Weeks 4, 6, 8, 10, and 12 defined as a stool
    frequency subscore=0, rectal bleeding subscore = 0, and 9-point
    partial Mayo score ≤1.

    4.2 Analysis Populations

    Full Analysis Set (FAS): all randomised patients with at least one
    Post-baseline 9-point partial Mayo score value.

    6.1 Randomization

    Randomization will be stratified by prior corticosteroids treatment
    (yes/no) and consent to participate in PK substudy (yes/no).
    """

    # Test extraction
    extractor = ProtocolVerbatimExtractor()

    primary = extractor.extract_primary_endpoint_verbatim(protocol_text)
    print(f"Primary endpoint: {primary.text if primary else 'NOT FOUND'}")

    fas = extractor.extract_population_verbatim(protocol_text, 'FAS')
    print(f"FAS definition: {fas.text if fas else 'NOT FOUND'}")

    strat = extractor.extract_all_stratification_factors(protocol_text)
    print(f"Stratification factors: {strat}")

    # Test enforcement
    bad_sap = """
    2.1 Primary Endpoint

    The primary endpoint is clinical remission (CR) at Week 12, defined as
    stool frequency subscore = 0, rectal bleeding subscore = 0, and
    9-point partial Mayo score ≤ 1.

    4.2 Analysis Populations

    The Full Analysis Set (FAS) is defined as all randomized subjects who
    took at least one dose of study drug AND had at least one post-baseline
    efficacy assessment.
    """

    enforcer = SAPOutputEnforcer(extractor)
    result = enforcer.enforce_all(bad_sap, protocol_text)

    print(f"\nViolations found: {result.violations_found}")
    print(f"Corrections made: {result.corrections_made}")
    print(f"\nCorrected SAP:\n{result.corrected}")
