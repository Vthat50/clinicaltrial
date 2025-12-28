#!/usr/bin/env python3
"""
Enterprise SAP Generation System - Specialized Agents
=======================================================
TIER 3: Multi-Agent SAP Generation Workflow

Specialized agents for different SAP generation tasks:
- EstimandArchitectAgent: ICH E9(R1) compliant estimand design
- MethodsSelectorAgent: Statistical method selection
- SAPWriterAgent: SAP section generation
- QualityReviewerAgent: Quality assessment
"""

import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path

# Use relative imports for consistent module resolution
try:
    from ..core.schemas import (
        ParsedProtocol, Estimand, InterCurrentEvent, StatisticalMethod,
        EndpointType, ICEStrategy, QualityReport, GeneratedSAP
    )
    from ..core.structured_extractor import ProtocolFacts, StructuredFactExtractor
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    from core.schemas import (
        ParsedProtocol, Estimand, InterCurrentEvent, StatisticalMethod,
        EndpointType, ICEStrategy, QualityReport, GeneratedSAP
    )
    try:
        from core.structured_extractor import ProtocolFacts, StructuredFactExtractor
    except ImportError:
        ProtocolFacts = None
        StructuredFactExtractor = None

from .base_agent import BaseAgent, AgentMessage


class EstimandArchitectAgent(BaseAgent):
    """
    Agent for designing ICH E9(R1) compliant estimands.
    Constructs complete estimands with all 5 required attributes.
    """

    SYSTEM_PROMPT = """You are an expert regulatory biostatistician specializing in ICH E9(R1) estimand framework.

Your task is to construct complete, regulatory-compliant estimands for clinical trial objectives.

## ICH E9(R1) Estimand Framework

Every estimand MUST specify these 5 attributes:

1. **Population**: Target population for the clinical question
   - Example: "Adult patients with metastatic NSCLC with EGFR mutations"

2. **Treatment**: Treatment condition being evaluated
   - Example: "Drug A 200mg BID vs. Placebo"

3. **Variable (Endpoint)**: The outcome variable
   - Example: "Progression-free survival per RECIST 1.1 by blinded central review"

4. **Intercurrent Events (ICE) with Strategies**: How to handle events that affect interpretation

   Strategies per ICH E9(R1):
   - **Treatment Policy**: Outcome regardless of ICE (intention-to-treat effect)
   - **Composite**: ICE becomes part of the endpoint definition
   - **Hypothetical**: Effect if ICE had not occurred (counterfactual)
   - **Principal Stratum**: Effect in subgroup where ICE would not occur
   - **While on Treatment**: Outcome only during active treatment

5. **Summary Measure**: Population-level summary statistic
   - Example: "Hazard ratio with 95% confidence interval"

## Common Intercurrent Events by Endpoint Type

For survival endpoints (OS, PFS, DFS):
- Treatment discontinuation due to AE → Treatment Policy
- Initiation of subsequent therapy → Treatment Policy or Hypothetical
- Death before progression → Composite (included in endpoint)

For response endpoints (ORR):
- Treatment discontinuation → While on Treatment
- Missing tumor assessment → Imputation rules

For safety endpoints:
- Treatment discontinuation → While on Treatment
- Dose modification → Treatment Policy

## Output Format

Return a JSON object with this structure:
{
  "primary_estimand": {
    "objective": "string",
    "population": "string",
    "treatment": "string",
    "variable": "string",
    "variable_type": "OS|PFS|ORR|DFS|SAFETY|PK|OTHER",
    "intercurrent_events": [
      {
        "event": "string",
        "strategy": "treatment_policy|composite|hypothetical|principal_stratum|while_on_treatment",
        "rationale": "string"
      }
    ],
    "summary_measure": "string",
    "analysis_method": "string"
  },
  "secondary_estimands": [...]
}"""

    def __init__(self, llm_client=None):
        super().__init__(
            name="estimand_architect",
            description="Design ICH E9(R1) compliant estimands",
            llm_client=llm_client
        )

    def execute(
        self,
        parsed_protocol: ParsedProtocol,
        knowledge_context: str = ""
    ) -> Dict[str, Any]:
        """
        Generate complete estimands for the protocol.

        Args:
            parsed_protocol: Parsed protocol data
            knowledge_context: Additional context from knowledge base

        Returns:
            Dictionary with primary and secondary estimands
        """
        self.update_state(status="running", current_task="Designing estimands")

        # Build the prompt
        prompt = self._build_prompt(parsed_protocol, knowledge_context)

        try:
            # Call LLM
            response = self.call_llm_json(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                temperature=0.2
            )

            # Parse and validate response
            estimands = self._parse_response(response)

            self.update_state(
                status="completed",
                progress=1.0,
                result_key="estimands",
                result_value=estimands
            )

            return estimands

        except Exception as e:
            self.state.errors.append(str(e))
            self.update_state(status="error")
            raise

    def _build_prompt(
        self,
        protocol: ParsedProtocol,
        knowledge_context: str
    ) -> str:
        """Build the prompt for estimand generation"""
        prompt_parts = [
            "## Protocol Information\n",
            f"- NCT ID: {protocol.nct_id}",
            f"- Phase: {protocol.phase.value if hasattr(protocol.phase, 'value') else protocol.phase}",
            f"- Therapeutic Area: {protocol.therapeutic_area}",
            f"- Indication: {protocol.indication}",
            f"- Design: {protocol.design_type.value if hasattr(protocol.design_type, 'value') else protocol.design_type}",
            f"- Randomization: {protocol.randomization_ratio}",
        ]

        if protocol.arms:
            prompt_parts.append("\n## Treatment Arms:")
            for arm in protocol.arms:
                prompt_parts.append(f"- {arm.name}: {arm.description}")

        if protocol.primary_estimand:
            prompt_parts.append("\n## Extracted Primary Endpoint:")
            prompt_parts.append(f"- Type: {protocol.primary_estimand.variable_type.value}")
            prompt_parts.append(f"- Variable: {protocol.primary_estimand.variable}")

        if knowledge_context:
            prompt_parts.append("\n## Relevant Knowledge:")
            prompt_parts.append(knowledge_context)

        prompt_parts.append("\n## Task:")
        prompt_parts.append("Design complete ICH E9(R1) compliant estimands for this study.")
        prompt_parts.append("Include primary estimand and relevant secondary estimands.")
        prompt_parts.append("Ensure all 5 estimand attributes are fully specified.")

        return "\n".join(prompt_parts)

    def _parse_response(self, response: Dict) -> Dict[str, Any]:
        """Parse and structure the LLM response"""
        result = {
            "primary_estimand": None,
            "secondary_estimands": []
        }

        # Parse primary estimand
        if "primary_estimand" in response:
            primary = response["primary_estimand"]
            ice_list = []
            for ice in primary.get("intercurrent_events", []):
                try:
                    strategy = ICEStrategy(ice.get("strategy", "treatment_policy"))
                except ValueError:
                    strategy = ICEStrategy.TREATMENT_POLICY

                ice_list.append(InterCurrentEvent(
                    event=ice.get("event", ""),
                    strategy=strategy,
                    rationale=ice.get("rationale", "")
                ))

            try:
                endpoint_type = EndpointType(primary.get("variable_type", "OTHER"))
            except ValueError:
                endpoint_type = EndpointType.OTHER

            result["primary_estimand"] = Estimand(
                objective=primary.get("objective", ""),
                population=primary.get("population", ""),
                treatment=primary.get("treatment", ""),
                variable=primary.get("variable", ""),
                variable_type=endpoint_type,
                intercurrent_events=ice_list,
                summary_measure=primary.get("summary_measure", ""),
                analysis_method=primary.get("analysis_method", ""),
                is_primary=True
            )

        # Parse secondary estimands
        for sec in response.get("secondary_estimands", []):
            ice_list = []
            for ice in sec.get("intercurrent_events", []):
                try:
                    strategy = ICEStrategy(ice.get("strategy", "treatment_policy"))
                except ValueError:
                    strategy = ICEStrategy.TREATMENT_POLICY

                ice_list.append(InterCurrentEvent(
                    event=ice.get("event", ""),
                    strategy=strategy,
                    rationale=ice.get("rationale", "")
                ))

            try:
                endpoint_type = EndpointType(sec.get("variable_type", "OTHER"))
            except ValueError:
                endpoint_type = EndpointType.OTHER

            result["secondary_estimands"].append(Estimand(
                objective=sec.get("objective", ""),
                population=sec.get("population", ""),
                treatment=sec.get("treatment", ""),
                variable=sec.get("variable", ""),
                variable_type=endpoint_type,
                intercurrent_events=ice_list,
                summary_measure=sec.get("summary_measure", ""),
                analysis_method=sec.get("analysis_method", ""),
                is_primary=False
            ))

        return result


class MethodsSelectorAgent(BaseAgent):
    """
    Agent for selecting appropriate statistical methods.
    Maps endpoints to appropriate analysis methods.
    FIXED: Prioritizes protocol-specified methods over defaults.
    """

    SYSTEM_PROMPT = """You are an expert biostatistician selecting statistical methods for clinical trial analysis.

Your task is to recommend appropriate statistical methods based on the study design and endpoints.

## CRITICAL: Protocol-Specified Methods Take Priority
If the protocol EXPLICITLY specifies an analysis method (e.g., "Primary Analysis: Logistic regression"),
YOU MUST USE THAT METHOD. Do NOT default to generic methods when protocol specifies something else.

## Method Selection Guidelines

### Time-to-Event Endpoints (OS, PFS, DFS, EFS)
Primary Methods:
- Kaplan-Meier: Non-parametric survival curves
- Cox Proportional Hazards: Hazard ratio estimation with covariate adjustment
- Log-Rank Test: Primary hypothesis test

Sensitivity Analyses:
- Stratified log-rank test (by randomization factors)
- Restricted mean survival time (RMST) - if PH assumption violated
- Landmark analysis
- Sensitivity to censoring assumptions

### Binary Endpoints (ORR)
Primary Methods:
- Clopper-Pearson exact CI
- CMH test (stratified)

Sensitivity Analyses:
- Fisher's exact test
- Logistic regression with covariates

### Continuous Endpoints
Primary Methods:
- ANCOVA with baseline as covariate
- MMRM for longitudinal data

Sensitivity Analyses:
- Non-parametric tests (Wilcoxon)
- Multiple imputation

### PK Endpoints
Primary Methods:
- Non-compartmental analysis (NCA)
- Linear mixed-effects model on log-transformed data

## Output Format

Return JSON with:
{
  "primary_analysis": {
    "method_name": "string",
    "description": "string",
    "assumptions": ["string"],
    "implementation": "SAS/R code reference",
    "rationale": "string"
  },
  "supportive_analyses": [...],
  "sensitivity_analyses": [...]
}"""

    def __init__(self, llm_client=None):
        super().__init__(
            name="methods_selector",
            description="Select appropriate statistical methods",
            llm_client=llm_client
        )

    def execute(
        self,
        parsed_protocol: ParsedProtocol,
        estimands: Dict[str, Any],
        knowledge_context: str = ""
    ) -> Dict[str, Any]:
        """
        Select statistical methods for the study.

        Args:
            parsed_protocol: Parsed protocol data
            estimands: Designed estimands from EstimandArchitectAgent
            knowledge_context: Additional context from knowledge base

        Returns:
            Dictionary with method recommendations
        """
        self.update_state(status="running", current_task="Selecting methods")

        prompt = self._build_prompt(parsed_protocol, estimands, knowledge_context)

        try:
            response = self.call_llm_json(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                temperature=0.2
            )

            self.update_state(
                status="completed",
                progress=1.0,
                result_key="methods",
                result_value=response
            )

            return response

        except Exception as e:
            self.state.errors.append(str(e))
            self.update_state(status="error")
            raise

    def _build_prompt(
        self,
        protocol: ParsedProtocol,
        estimands: Dict,
        knowledge_context: str
    ) -> str:
        """Build prompt for method selection"""
        parts = [
            "## Study Information\n",
            f"- Phase: {protocol.phase.value if hasattr(protocol.phase, 'value') else protocol.phase}",
            f"- Design: {protocol.design_type.value if hasattr(protocol.design_type, 'value') else protocol.design_type}",
            f"- Blinding: {protocol.blinding.value if hasattr(protocol.blinding, 'value') else protocol.blinding}",
        ]

        if estimands.get("primary_estimand"):
            est = estimands["primary_estimand"]
            parts.append("\n## Primary Estimand:")
            parts.append(f"- Endpoint Type: {est.variable_type.value if hasattr(est.variable_type, 'value') else est.variable_type}")
            parts.append(f"- Variable: {est.variable}")
            parts.append(f"- Summary Measure: {est.summary_measure}")

        if protocol.stratification_factors:
            parts.append(f"\n## Stratification Factors: {', '.join(protocol.stratification_factors)}")

        if knowledge_context:
            parts.append("\n## Relevant Knowledge:")
            parts.append(knowledge_context)

        parts.append("\n## Task:")
        parts.append("Recommend statistical methods for primary, supportive, and sensitivity analyses.")

        return "\n".join(parts)


class SAPWriterAgent(BaseAgent):
    """
    Agent for generating SAP document sections.
    Produces TransCelerate-aligned content.

    PRODUCTION ARCHITECTURE:
    - Uses ProtocolFacts (structured extraction) instead of raw protocol text
    - Uses sanitized RAG examples (placeholders, not values)
    - Validated by HardValidator before output
    """

    SYSTEM_PROMPT = """You are an expert medical writer specializing in Statistical Analysis Plans (SAPs).

Your task is to write professional, regulatory-compliant SAP sections aligned with TransCelerate template standards.

## CRITICAL ANTI-HALLUCINATION RULES
1. Use ONLY values explicitly provided in the protocol data below
2. DO NOT invent sample sizes, routes, stratification factors, or analysis methods
3. If a value is not provided, write "[TO BE CONFIRMED FROM PROTOCOL]"
4. NEVER use generic defaults like "disease severity" for stratification
5. The protocol values provided are EXTRACTED from the actual document - use them exactly

## SAP Section Requirements

### Section 1: Introduction
- Purpose of the SAP
- Scope and responsibilities
- Reference documents

### Section 2: Study Objectives and Estimands
- Primary objective with full estimand specification
- Secondary objectives with estimands
- ICH E9(R1) compliance demonstrated

### Section 3: Study Design
- Design overview with schema
- Randomization and stratification
- Blinding procedures

### Section 4: Analysis Populations
- ITT, mITT, PP, Safety population definitions
- Population derivation rules
- Population for each analysis

### Section 5: Statistical Methods
- Primary analysis methodology with full detail
- Handling of covariates and stratification
- Secondary and exploratory analyses
- Sensitivity analyses

### Section 6: Sample Size
- Assumptions and calculations
- Power statements
- Sample size re-estimation (if applicable)

### Section 7: Data Handling
- Missing data strategy
- Visit windows
- Derivation rules

### Section 8: CDISC Alignment
- ADaM dataset mapping
- Key variables and traceability

### Section 9: TLF Specifications
- Table shells overview
- Key figures and listings

## Writing Style

- Use precise, unambiguous language
- Include specific statistical details (e.g., two-sided, alpha=0.05)
- Reference regulatory guidance where appropriate
- Use consistent terminology
- Avoid hedging language

## Output Format

Return the section content as a markdown-formatted string."""

    def __init__(self, llm_client=None):
        super().__init__(
            name="sap_writer",
            description="Generate SAP document sections",
            llm_client=llm_client
        )

    def execute(
        self,
        section_name: str,
        parsed_protocol: ParsedProtocol,
        estimands: Dict[str, Any],
        methods: Dict[str, Any],
        few_shot_examples: List[str] = None,
        knowledge_context: str = ""
    ) -> str:
        """
        Generate a specific SAP section.

        Args:
            section_name: Name of the section to generate
            parsed_protocol: Parsed protocol data
            estimands: Designed estimands
            methods: Selected statistical methods
            few_shot_examples: Example sections from real SAPs
            knowledge_context: Additional context

        Returns:
            Generated section content as string
        """
        self.update_state(status="running", current_task=f"Writing {section_name}")

        prompt = self._build_prompt(
            section_name, parsed_protocol, estimands, methods,
            few_shot_examples, knowledge_context
        )

        try:
            response = self.call_llm(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=4000
            )

            self.update_state(
                status="completed",
                progress=1.0,
                result_key=section_name,
                result_value=response
            )

            return response

        except Exception as e:
            self.state.errors.append(str(e))
            self.update_state(status="error")
            raise

    def execute_with_facts(
        self,
        section_name: str,
        protocol_facts: 'ProtocolFacts',
        sanitized_template: str = "",
        estimands: Dict[str, Any] = None,
        methods: Dict[str, Any] = None,
    ) -> str:
        """
        Generate SAP section using structured facts (PRODUCTION METHOD).

        This is the PRODUCTION version that:
        1. Uses ProtocolFacts (structured extraction) instead of raw protocol
        2. Uses sanitized templates (placeholders) instead of raw examples
        3. Injects facts as MANDATORY values

        Args:
            section_name: Name of section to generate
            protocol_facts: ProtocolFacts from StructuredFactExtractor
            sanitized_template: Sanitized RAG template (structure only)
            estimands: Designed estimands (optional)
            methods: Selected methods (optional)

        Returns:
            Generated section content
        """
        self.update_state(status="running", current_task=f"Writing {section_name} (production)")

        prompt = self._build_prompt_from_facts(
            section_name, protocol_facts, sanitized_template, estimands, methods
        )

        try:
            response = self.call_llm(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                temperature=0.2,  # Lower temperature for more deterministic output
                max_tokens=4000
            )

            self.update_state(
                status="completed",
                progress=1.0,
                result_key=section_name,
                result_value=response
            )

            return response

        except Exception as e:
            self.state.errors.append(str(e))
            self.update_state(status="error")
            raise

    def _build_prompt_from_facts(
        self,
        section_name: str,
        facts: 'ProtocolFacts',
        sanitized_template: str,
        estimands: Dict = None,
        methods: Dict = None,
    ) -> str:
        """
        Build prompt using ProtocolFacts (PRODUCTION METHOD).

        This ensures the LLM only sees:
        1. MANDATORY FACTS (must use exactly)
        2. SANITIZED TEMPLATE (structure only, no values)
        """
        # Import the helper function
        try:
            from ..core.structured_extractor import StructuredFactExtractor
            extractor = StructuredFactExtractor()
            facts_context = extractor.to_prompt_context(facts)
        except Exception:
            # Fallback: manually build context
            facts_context = self._manual_facts_context(facts)

        parts = [
            f"## Task: Generate SAP Section - {section_name}\n",
            "=" * 60,
            "## MANDATORY PROTOCOL FACTS",
            "You MUST use these values EXACTLY. Do NOT change ANY value.",
            "=" * 60,
            "",
            facts_context,
            "",
            "=" * 60,
            "## CRITICAL RULES",
            "=" * 60,
            "",
        ]

        # Add specific mandatory rules based on facts
        if facts.drug_name:
            parts.append(f"1. Drug name MUST be: {facts.drug_name}")
        if facts.sample_size and facts.sample_size.total_n > 0:
            parts.append(f"2. Sample size MUST be: {facts.sample_size.total_n} patients")
        if facts.num_arms > 0:
            parts.append(f"3. Number of arms MUST be: {facts.num_arms}")
        if facts.randomization_ratio:
            parts.append(f"4. Randomization ratio MUST be: {facts.randomization_ratio}")
        if facts.route_of_administration and facts.route_of_administration.value != "other":
            parts.append(f"5. Route MUST be: {facts.route_of_administration.value}")
        if facts.alpha:
            parts.append(f"6. Alpha MUST be: {facts.alpha.primary_alpha} ({facts.alpha.sidedness})")

        parts.append("")
        parts.append("WARNING: NEVER use values from the template examples - they are PLACEHOLDERS")
        parts.append("WARNING: NEVER invent or estimate values - use ONLY what is provided above")
        parts.append("WARNING: If a value is not provided, write '[TO BE CONFIRMED FROM PROTOCOL]'")
        parts.append("")

        # Add estimands if available
        if estimands and estimands.get("primary_estimand"):
            est = estimands["primary_estimand"]
            parts.append("## Primary Estimand:")
            parts.append(f"- Objective: {est.objective}")
            parts.append(f"- Population: {est.population}")
            parts.append(f"- Variable: {est.variable}")
            parts.append(f"- Summary Measure: {est.summary_measure}")
            parts.append("")

        # Add methods if available
        if methods and methods.get("primary_analysis"):
            parts.append("## Selected Methods:")
            parts.append(f"- Primary: {methods['primary_analysis'].get('method_name', 'TBD')}")
            parts.append("")

        # Add sanitized template if provided
        if sanitized_template:
            parts.append("=" * 60)
            parts.append("## TEMPLATE (STRUCTURE ONLY - DO NOT COPY VALUES)")
            parts.append("The following shows SAP STRUCTURE. All values are {PLACEHOLDERS}.")
            parts.append("Use the MANDATORY FACTS above, NOT these placeholder values.")
            parts.append("=" * 60)
            parts.append("")
            parts.append(sanitized_template[:3000])  # Limit length
            parts.append("")

        parts.append(f"\n## Now generate the {section_name} section:")
        parts.append("Use ONLY the MANDATORY FACTS provided above.")

        return "\n".join(parts)

    def _manual_facts_context(self, facts: 'ProtocolFacts') -> str:
        """Fallback method to build facts context"""
        lines = []
        if facts.nct_id:
            lines.append(f"- NCT ID: {facts.nct_id}")
        if facts.drug_name:
            lines.append(f"- Drug: {facts.drug_name}")
        if facts.phase:
            lines.append(f"- Phase: {facts.phase.value}")
        if facts.therapeutic_area:
            lines.append(f"- Therapeutic Area: {facts.therapeutic_area}")
        if facts.indication:
            lines.append(f"- Indication: {facts.indication}")
        if facts.num_arms:
            lines.append(f"- Number of Arms: {facts.num_arms}")
        if facts.randomization_ratio:
            lines.append(f"- Randomization: {facts.randomization_ratio}")
        if facts.sample_size and facts.sample_size.total_n:
            lines.append(f"- Sample Size: {facts.sample_size.total_n}")
        if facts.route_of_administration:
            lines.append(f"- Route: {facts.route_of_administration.value}")
        if facts.alpha:
            lines.append(f"- Alpha: {facts.alpha.primary_alpha} ({facts.alpha.sidedness})")
        return "\n".join(lines)

    def generate_all_sections_with_facts(
        self,
        protocol_facts: 'ProtocolFacts',
        sanitized_templates: Dict[str, str] = None,
        estimands: Dict[str, Any] = None,
        methods: Dict[str, Any] = None,
    ) -> Dict[str, str]:
        """
        Generate all SAP sections using ProtocolFacts (PRODUCTION METHOD).

        Args:
            protocol_facts: Structured facts from protocol
            sanitized_templates: Sanitized RAG templates per section
            estimands: Designed estimands
            methods: Selected methods

        Returns:
            Dictionary of section_name -> content
        """
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

        sanitized_templates = sanitized_templates or {}

        for section_name in section_names:
            template = sanitized_templates.get(section_name, "")
            sections[section_name] = self.execute_with_facts(
                section_name=section_name,
                protocol_facts=protocol_facts,
                sanitized_template=template,
                estimands=estimands,
                methods=methods,
            )

        return sections

    def _build_prompt(
        self,
        section_name: str,
        protocol: ParsedProtocol,
        estimands: Dict,
        methods: Dict,
        examples: List[str],
        context: str
    ) -> str:
        """Build prompt for section generation with ALL extracted values (LEGACY)"""
        parts = [
            f"## Task: Generate SAP Section - {section_name}\n",
            "## Study Information:",
            f"- NCT ID: {protocol.nct_id}",
            f"- Title: {protocol.study_title}",
            f"- Phase: {protocol.phase.value if hasattr(protocol.phase, 'value') else protocol.phase}",
            f"- Design: {protocol.design_type.value if hasattr(protocol.design_type, 'value') else protocol.design_type}",
            f"- Therapeutic Area: {protocol.therapeutic_area}",
        ]

        # CRITICAL: Include sample size - MUST USE THESE VALUES
        if protocol.sample_size:
            ss = protocol.sample_size
            alpha_side = ss.assumptions.get('alpha_sidedness', 'two-sided')
            primary_method = ss.assumptions.get('primary_analysis_method')
            parts.append("\n## SAMPLE SIZE (USE EXACTLY - DO NOT CHANGE):")
            parts.append(f"- Total N: {ss.total_n}")
            parts.append(f"- Power: {ss.power * 100 if ss.power < 1 else ss.power}%")
            parts.append(f"- Alpha: {ss.alpha} ({alpha_side})")
            if ss.per_arm_n:
                for arm, n in ss.per_arm_n.items():
                    parts.append(f"- {arm}: {n}")

            # CRITICAL: Include primary analysis method if specified in protocol
            if primary_method:
                parts.append(f"\n## PRIMARY ANALYSIS METHOD (FROM PROTOCOL - USE THIS):")
                parts.append(f"- {primary_method}")
                parts.append("⚠️ This is the EXACT method specified in the protocol. USE IT.")

        # CRITICAL: Include treatment arms with route/dose
        if protocol.arms:
            parts.append("\n## TREATMENT ARMS (USE EXACTLY - DO NOT CHANGE):")
            for arm in protocol.arms:
                route = arm.route or "[route not specified]"
                dose = arm.dose or "[dose not specified]"
                parts.append(f"- {arm.name}: {dose}, {route}")
                if arm.is_control:
                    parts.append(f"  (Control arm)")

        # CRITICAL: Include stratification factors
        if protocol.stratification_factors:
            parts.append("\n## STRATIFICATION FACTORS (USE EXACTLY - DO NOT CHANGE):")
            for factor in protocol.stratification_factors:
                parts.append(f"- {factor}")

        if estimands.get("primary_estimand"):
            est = estimands["primary_estimand"]
            parts.append("\n## Primary Estimand:")
            parts.append(f"- Objective: {est.objective}")
            parts.append(f"- Population: {est.population}")
            parts.append(f"- Treatment: {est.treatment}")
            parts.append(f"- Variable: {est.variable}")
            parts.append(f"- Summary Measure: {est.summary_measure}")
            if est.intercurrent_events:
                parts.append("- Intercurrent Events:")
                for ice in est.intercurrent_events:
                    parts.append(f"  - {ice.event}: {ice.strategy.value}")

        if methods:
            parts.append("\n## Selected Methods:")
            if methods.get("primary_analysis"):
                parts.append(f"- Primary: {methods['primary_analysis'].get('method_name', 'TBD')}")

        # Detect therapeutic area for filtering
        ta = protocol.therapeutic_area.lower() if protocol.therapeutic_area else ""
        is_immunology = any(t in ta for t in ['immunology', 'autoimmune', 'inflammatory'])

        # Add CRITICAL instructions
        parts.append("\n## CRITICAL INSTRUCTIONS - YOU MUST FOLLOW:")
        parts.append("1. Use the EXACT values from SAMPLE SIZE, TREATMENT ARMS, and STRATIFICATION above")
        parts.append("2. DO NOT invent, modify, or substitute ANY values")
        parts.append("3. If route says 'intravenous', write 'intravenous' - NOT 'subcutaneous'")
        parts.append("4. If sample size says 90, write 90 - NOT 300 or any other number")
        parts.append("5. Copy stratification factors EXACTLY as listed above")
        parts.append("6. If PRIMARY ANALYSIS METHOD is specified above, use it as THE PRIMARY method - NOT as sensitivity")
        parts.append("7. If alpha says 'one-sided', use ONE-SIDED significance - NOT two-sided")

        # ANTI-CONTAMINATION: Explicit list of values to NEVER use
        parts.append("\n## FORBIDDEN VALUES - NEVER USE THESE (from other studies):")
        parts.append("- NEVER use: etrolizumab, vedolizumab, tocilizumab, adalimumab")
        parts.append("- NEVER use study IDs: GA29144, GA29145, PRO145223, WA25615, ML42528")
        parts.append("- NEVER use sample sizes: 1150, 769, 728, 600, 500, 400, 300")
        parts.append("- NEVER use ratios: 1:2:2, 2:1, 3:1 (unless explicitly in YOUR protocol)")
        parts.append("- If you find yourself writing any of these, STOP and use the protocol values instead")
        parts.append("8. Use the number of treatment arms shown above - do NOT invent extra arms")

        if is_immunology:
            parts.append("9. THIS IS AN IMMUNOLOGY TRIAL - NEVER use oncology terms like 'tumor', 'RECIST', 'progression-free'")
            parts.append("   For intercurrent events, use 'Missing assessment' NOT 'Missing tumor assessment'")

        if examples:
            parts.append("\n## Example from Real SAP (use as style reference only, NOT values):")
            parts.append(examples[0][:2000])

        if context:
            parts.append("\n## Relevant Knowledge:")
            parts.append(context[:1000])

        parts.append(f"\n## Generate the {section_name} section using ONLY the values provided above:")

        return "\n".join(parts)

    def generate_all_sections(
        self,
        parsed_protocol: ParsedProtocol,
        estimands: Dict[str, Any],
        methods: Dict[str, Any],
        few_shot_examples: Dict[str, List[str]] = None,
        knowledge_context: str = ""
    ) -> Dict[str, str]:
        """Generate all SAP sections"""
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

        for section_name in section_names:
            examples = (few_shot_examples or {}).get(section_name, [])
            sections[section_name] = self.execute(
                section_name=section_name,
                parsed_protocol=parsed_protocol,
                estimands=estimands,
                methods=methods,
                few_shot_examples=examples,
                knowledge_context=knowledge_context
            )

        return sections


class QualityReviewerAgent(BaseAgent):
    """
    Agent for reviewing and scoring generated SAP quality.
    Checks ICH compliance, consistency, and completeness.
    """

    SYSTEM_PROMPT = """You are a senior regulatory biostatistician reviewing Statistical Analysis Plans for quality.

Your task is to assess SAP quality against regulatory requirements and industry standards.

## Quality Dimensions

1. **ICH E9(R1) Compliance** (0-100)
   - Are all 5 estimand attributes fully specified?
   - Are ICE strategies appropriate and justified?
   - Is the estimand-aligned sensitivity analysis adequate?

2. **Estimand Completeness** (0-100)
   - Is the population well-defined?
   - Is the treatment clearly specified?
   - Is the variable unambiguous?
   - Are all relevant ICEs addressed?
   - Is the summary measure appropriate?

3. **CDISC Alignment** (0-100)
   - Are ADaM datasets correctly identified?
   - Is traceability documented?
   - Are key variables specified?

4. **Statistical Soundness** (0-100)
   - Are methods appropriate for endpoint type?
   - Are assumptions stated?
   - Are sensitivity analyses adequate?
   - Is multiplicity addressed?

5. **Internal Consistency** (0-100)
   - Is terminology consistent throughout?
   - Do populations align across sections?
   - Are endpoint definitions consistent?

## Output Format

Return JSON:
{
  "overall_score": float,  // 0-100
  "ich_e9r1_compliance": float,
  "estimand_completeness": float,
  "cdisc_alignment": float,
  "statistical_soundness": float,
  "consistency_score": float,
  "issues": ["critical issue 1", ...],
  "warnings": ["warning 1", ...],
  "suggestions": ["improvement suggestion 1", ...],
  "section_scores": {"section_name": score, ...}
}"""

    def __init__(self, llm_client=None):
        super().__init__(
            name="quality_reviewer",
            description="Review and score SAP quality",
            llm_client=llm_client
        )

    def execute(
        self,
        generated_sap: Dict[str, str],
        parsed_protocol: ParsedProtocol,
        estimands: Dict[str, Any]
    ) -> QualityReport:
        """
        Review generated SAP and produce quality report.

        Args:
            generated_sap: Dictionary of generated sections
            parsed_protocol: Original parsed protocol
            estimands: Designed estimands

        Returns:
            QualityReport with scores and issues
        """
        self.update_state(status="running", current_task="Reviewing SAP quality")

        prompt = self._build_prompt(generated_sap, parsed_protocol, estimands)

        try:
            response = self.call_llm_json(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                temperature=0.1
            )

            report = self._parse_response(response)

            self.update_state(
                status="completed",
                progress=1.0,
                result_key="quality_report",
                result_value=report
            )

            return report

        except Exception as e:
            self.state.errors.append(str(e))
            self.update_state(status="error")
            # Return default report on error
            return QualityReport(
                overall_score=0.0,
                ich_e9r1_compliance=0.0,
                estimand_completeness=0.0,
                cdisc_alignment=0.0,
                statistical_soundness=0.0,
                consistency_score=0.0,
                issues=[f"Review failed: {str(e)}"]
            )

    def _build_prompt(
        self,
        sap_sections: Dict[str, str],
        protocol: ParsedProtocol,
        estimands: Dict
    ) -> str:
        """Build prompt for quality review"""
        parts = [
            "## SAP Quality Review\n",
            "## Study Context:",
            f"- Phase: {protocol.phase.value if hasattr(protocol.phase, 'value') else protocol.phase}",
            f"- Endpoint Type: {estimands.get('primary_estimand', {}).variable_type.value if estimands.get('primary_estimand') and hasattr(estimands.get('primary_estimand').variable_type, 'value') else 'Unknown'}",
            "\n## Generated SAP Sections:\n"
        ]

        for section_name, content in sap_sections.items():
            parts.append(f"### {section_name}")
            # Truncate long sections
            parts.append(content[:3000] if len(content) > 3000 else content)
            parts.append("")

        parts.append("\n## Review this SAP for quality against all dimensions.")
        parts.append("Identify issues, warnings, and suggestions for improvement.")

        return "\n".join(parts)

    def _parse_response(self, response: Dict) -> QualityReport:
        """Parse review response into QualityReport"""
        return QualityReport(
            overall_score=response.get("overall_score", 0.0),
            ich_e9r1_compliance=response.get("ich_e9r1_compliance", 0.0),
            estimand_completeness=response.get("estimand_completeness", 0.0),
            cdisc_alignment=response.get("cdisc_alignment", 0.0),
            statistical_soundness=response.get("statistical_soundness", 0.0),
            consistency_score=response.get("consistency_score", 0.0),
            issues=response.get("issues", []),
            warnings=response.get("warnings", []),
            suggestions=response.get("suggestions", []),
            section_scores=response.get("section_scores", {})
        )
