#!/usr/bin/env python3
"""
Production SAP Pipeline - Separation of Concerns Architecture
==============================================================

Based on 2024-2025 RAG best practices:

1. EXTRACTION (Ground Truth) - Single source for all numerical values
2. KNOWLEDGE GRAPH (Method Selection) - Rules for statistical methods
3. RAG (Prose Style Only) - Sanitized examples with numbers stripped
4. CONSTRAINED GENERATION - Explicit source attribution in prompts
5. SELF-RAG VERIFICATION - Verify and correct if needed

References:
- SELF-RAG (ICLR 2024 Oral): Reflection tokens for factuality
- AI21 Labs: "Centralizing through single trusted data source"
- Graph RAG (2025): Knowledge graphs as factual constraints
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

# Import components
try:
    from .claude_extractor import ClaudeProtocolExtractor, ExtractedProtocol
except ImportError:
    ClaudeProtocolExtractor = None
    ExtractedProtocol = None

try:
    from .knowledge_rule_engine import KnowledgeRuleEngine
except ImportError:
    KnowledgeRuleEngine = None

try:
    from .rag_sanitizer import RAGSanitizer
except ImportError:
    RAGSanitizer = None

try:
    from .fact_verifier import FactVerifier, VerificationResult
except ImportError:
    FactVerifier = None
    VerificationResult = None

try:
    from ..rag.vector_store import create_vector_store
except ImportError:
    try:
        from enterprise_sap_system.rag.vector_store import create_vector_store
    except ImportError:
        create_vector_store = None

try:
    from .tiered_llm import TieredLLMClient
except ImportError:
    TieredLLMClient = None


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class MethodConstraints:
    """Method constraints from Knowledge Graph."""
    primary_test: str = ""
    primary_test_params: Dict[str, Any] = field(default_factory=dict)
    forbidden_primary: str = ""  # Method NOT to use as primary
    sensitivity_methods: List[str] = field(default_factory=list)
    interim_method: str = ""
    alpha_spending: str = ""
    nph_methods: List[str] = field(default_factory=list)
    conditions_detected: List[str] = field(default_factory=list)


@dataclass
class GenerationResult:
    """Final SAP generation result."""
    success: bool
    sap_text: str = ""
    sections: Dict[str, str] = field(default_factory=dict)
    facts: Dict[str, Any] = field(default_factory=dict)
    constraints: Optional[MethodConstraints] = None
    verification: Optional[VerificationResult] = None
    regeneration_count: int = 0
    warnings: List[str] = field(default_factory=list)
    error: str = ""


# =============================================================================
# PRODUCTION PIPELINE
# =============================================================================

class ProductionSAPPipeline:
    """
    Production-grade SAP generation with explicit source priority.

    Architecture:
    1. EXTRACTION → Structured facts (GROUND TRUTH for all numbers)
    2. KNOWLEDGE GRAPH → Method constraints (what methods to use)
    3. RAG → Sanitized examples (prose style only, numbers stripped)
    4. GENERATION → Constrained prompts with explicit source attribution
    5. VERIFICATION → SELF-RAG pattern with correction loop
    """

    # SAP sections to generate
    SECTIONS = [
        ('introduction', 'Introduction'),
        ('objectives', 'Study Objectives and Endpoints'),
        ('study_design', 'Study Design'),
        ('sample_size', 'Sample Size Determination'),
        ('analysis_populations', 'Analysis Populations'),
        ('statistical_methods', 'Statistical Methods'),
        ('interim_analysis', 'Interim Analysis'),
        ('sensitivity_analysis', 'Sensitivity Analyses'),
        ('missing_data', 'Missing Data Handling'),
        ('multiplicity', 'Multiplicity Adjustment'),
        ('safety', 'Safety Analyses'),
    ]

    def __init__(self, max_regenerations: int = 2):
        """
        Initialize production pipeline.

        Args:
            max_regenerations: Max times to regenerate on verification failure
        """
        self.max_regenerations = max_regenerations

        # Initialize components
        print("[ProductionPipeline] Initializing components...")

        # 1. Extractor (Ground Truth)
        self.extractor = None
        if ClaudeProtocolExtractor:
            try:
                self.extractor = ClaudeProtocolExtractor()
                print("[ProductionPipeline] ✓ ClaudeProtocolExtractor initialized")
            except Exception as e:
                print(f"[ProductionPipeline] ✗ Extractor failed: {e}")

        # 2. Knowledge Graph (Method Selection)
        self.knowledge_graph = None
        if KnowledgeRuleEngine:
            try:
                self.knowledge_graph = KnowledgeRuleEngine()
                print(f"[ProductionPipeline] ✓ KnowledgeRuleEngine loaded ({len(self.knowledge_graph.rules)} rules)")
            except Exception as e:
                print(f"[ProductionPipeline] ✗ Knowledge graph failed: {e}")

        # 3. RAG (Prose Style)
        self.rag = None
        if create_vector_store:
            try:
                self.rag = create_vector_store()
                print("[ProductionPipeline] ✓ ChromaDB RAG connected")
            except Exception as e:
                print(f"[ProductionPipeline] ✗ RAG failed: {e}")

        # 4. RAG Sanitizer
        self.sanitizer = None
        if RAGSanitizer:
            self.sanitizer = RAGSanitizer(aggressive=True)
            print("[ProductionPipeline] ✓ RAG Sanitizer initialized")

        # 5. Fact Verifier (SELF-RAG)
        self.verifier = None
        if FactVerifier:
            self.verifier = FactVerifier()
            print("[ProductionPipeline] ✓ Fact Verifier initialized")

        # 6. LLM Client
        self.llm = None
        if TieredLLMClient:
            try:
                self.llm = TieredLLMClient()
                print("[ProductionPipeline] ✓ LLM client initialized")
            except Exception as e:
                print(f"[ProductionPipeline] ✗ LLM failed: {e}")

    def generate(self, protocol_text: str) -> GenerationResult:
        """
        Generate SAP using production pipeline.

        Steps:
        1. Extract structured facts (GROUND TRUTH)
        2. Get method constraints from knowledge graph
        3. Get sanitized RAG examples (numbers stripped)
        4. Generate with constrained prompts
        5. Verify and regenerate if needed (SELF-RAG)
        """
        try:
            # STEP 1: Extract facts (GROUND TRUTH)
            print("\n[Step 1] Extracting facts (GROUND TRUTH)...")
            facts = self._extract_facts(protocol_text)
            print(f"[Step 1] Extracted: {facts.get('nct_id')}, {facts.get('sample_size')} patients, {facts.get('final_events')} events")

            # STEP 2: Get method constraints
            print("\n[Step 2] Getting method constraints from Knowledge Graph...")
            conditions = self._detect_conditions(facts, protocol_text)
            constraints = self._get_constraints(facts, conditions)
            print(f"[Step 2] Primary test: {constraints.primary_test}")
            print(f"[Step 2] Conditions: {conditions}")

            # STEP 3: Get sanitized RAG examples
            print("\n[Step 3] Getting sanitized RAG examples (numbers stripped)...")
            sanitized_examples = self._get_sanitized_examples(facts)
            print(f"[Step 3] Retrieved {sum(len(v) for v in sanitized_examples.values())} sanitized examples")

            # STEP 4: Generate sections
            print("\n[Step 4] Generating SAP sections with constrained prompts...")
            sections = self._generate_all_sections(facts, constraints, sanitized_examples)

            # Assemble full SAP
            sap_text = self._assemble_sap(sections, facts)

            # STEP 5: Verify and regenerate if needed (SELF-RAG)
            print("\n[Step 5] Verifying against extracted facts (SELF-RAG)...")
            verification, sap_text, regeneration_count = self._verify_and_correct(
                sap_text, facts, constraints
            )

            if verification and verification.passed:
                print(f"[Step 5] ✓ Verification PASSED (score: {verification.score:.2f})")
            else:
                print(f"[Step 5] ⚠ Verification completed with issues after {regeneration_count} regenerations")

            return GenerationResult(
                success=True,
                sap_text=sap_text,
                sections=sections,
                facts=facts,
                constraints=constraints,
                verification=verification,
                regeneration_count=regeneration_count
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            return GenerationResult(
                success=False,
                error=str(e)
            )

    def _extract_facts(self, protocol_text: str) -> Dict[str, Any]:
        """
        Step 1: Extract structured facts using Claude LLM.
        These are the GROUND TRUTH - single source for all numerical values.
        """
        if self.extractor:
            try:
                extracted = self.extractor.extract(protocol_text)
                if extracted:
                    # Convert to dict
                    if hasattr(extracted, 'dict'):
                        facts = extracted.dict()
                    elif hasattr(extracted, '__dict__'):
                        facts = {k: v for k, v in extracted.__dict__.items() if not k.startswith('_')}
                    else:
                        facts = dict(extracted)

                    # Normalize field names for consistency
                    facts = self._normalize_facts(facts)
                    return facts
            except Exception as e:
                print(f"[Extraction] Error: {e}")

        # Fallback to basic extraction
        return self._basic_extraction(protocol_text)

    def _normalize_facts(self, facts: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize field names for consistency."""
        normalized = dict(facts)

        # Event counts
        if 'final_analysis_events' not in normalized and 'final_events' in normalized:
            normalized['final_analysis_events'] = normalized['final_events']
        if 'interim_analysis_events' not in normalized and 'interim_events' in normalized:
            normalized['interim_analysis_events'] = normalized['interim_events']

        # Alpha values
        if 'alpha_at_interim' not in normalized:
            if 'interim_alpha_spent' in normalized and normalized['interim_alpha_spent']:
                if isinstance(normalized['interim_alpha_spent'], list):
                    normalized['alpha_at_interim'] = normalized['interim_alpha_spent'][0] if normalized['interim_alpha_spent'] else None
                else:
                    normalized['alpha_at_interim'] = normalized['interim_alpha_spent']

        if 'alpha_at_final' not in normalized and 'alpha_level' in normalized:
            normalized['alpha_at_final'] = normalized.get('alpha_level')

        # Interim count
        if 'num_interim' not in normalized and 'num_interim_analyses' in normalized:
            normalized['num_interim'] = normalized['num_interim_analyses']

        return normalized

    def _basic_extraction(self, text: str) -> Dict[str, Any]:
        """Fallback basic extraction."""
        facts = {'raw_text': text.lower()}

        # NCT ID
        nct_match = re.search(r'NCT\d{8}', text, re.IGNORECASE)
        if nct_match:
            facts['nct_id'] = nct_match.group()

        # Sample size
        size_match = re.search(r'(\d+)\s*(?:patients|subjects|participants)', text, re.IGNORECASE)
        if size_match:
            facts['sample_size'] = int(size_match.group(1))

        # Events
        events_match = re.search(r'(\d+)\s*(?:deaths?|events?|os events?)', text, re.IGNORECASE)
        if events_match:
            facts['final_events'] = int(events_match.group(1))

        return facts

    def _detect_conditions(self, facts: Dict[str, Any], protocol_text: str) -> List[str]:
        """Step 2a: Detect conditions for method selection."""
        if self.knowledge_graph:
            facts_with_text = {**facts, 'raw_text': protocol_text.lower()}
            conditions = self.knowledge_graph.detect_conditions(facts_with_text)
            return list(conditions)

        # Fallback
        conditions = []
        text_lower = protocol_text.lower()

        if any(x in text_lower for x in ['nivolumab', 'pembrolizumab', 'pd-1', 'pd-l1', 'checkpoint', 'immunotherapy']):
            conditions.extend(['immunotherapy', 'delayed_effect'])
        if any(x in text_lower for x in ['survival', 'os', 'pfs', 'time to']):
            conditions.append('time_to_event')
        if 'crossover' in text_lower or 'cross-over' in text_lower:
            conditions.extend(['crossover', 'treatment_switching'])
        if 'interim' in text_lower:
            conditions.append('interim_analysis')
        if 'stratif' in text_lower:
            conditions.append('stratified')

        return conditions

    def _get_constraints(self, facts: Dict[str, Any], conditions: List[str]) -> MethodConstraints:
        """Step 2b: Get method constraints from knowledge graph."""
        constraints = MethodConstraints(conditions_detected=conditions)

        if self.knowledge_graph:
            methods = self.knowledge_graph.get_primary_analysis_methods(facts)

            if methods:
                primary = methods.get('primary_test', {})
                if primary:
                    constraints.primary_test = primary.get('description', primary.get('method', ''))

                # NPH methods
                nph = methods.get('nph_methods', [])
                constraints.nph_methods = [m.get('method', m) if isinstance(m, dict) else m for m in nph]

                # Interim
                interim = methods.get('interim_analysis_method', {})
                if interim:
                    constraints.interim_method = interim.get('method', '')
                    constraints.alpha_spending = "O'Brien-Fleming"

        # Apply immunotherapy-specific constraints
        if 'immunotherapy' in conditions and 'time_to_event' in conditions:
            constraints.primary_test = "Fleming-Harrington weighted log-rank test G(ρ=0, γ=1)"
            constraints.forbidden_primary = "stratified log-rank"
            constraints.nph_methods = ['Fleming-Harrington', 'RMST', 'landmark_analysis']
            constraints.sensitivity_methods = ['stratified log-rank (unweighted)']

        if 'interim_analysis' in conditions and not constraints.interim_method:
            constraints.interim_method = "Lan-DeMets"
            constraints.alpha_spending = "O'Brien-Fleming"

        return constraints

    def _get_sanitized_examples(self, facts: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Step 3: Get RAG examples with numbers stripped.
        RAG is for PROSE STYLE only, not for facts.
        """
        examples = {}

        if not self.rag:
            return examples

        # Build query from facts
        query_parts = []
        for key in ['primary_endpoint', 'indication', 'drug_name']:
            value = facts.get(key)
            if value and isinstance(value, str):
                query_parts.append(value)

        query = ' '.join(query_parts) if query_parts else 'oncology phase 3 survival'

        # Query and sanitize each section type
        section_types = ['methods', 'interim_analysis', 'sensitivity_analysis', 'sample_size']

        for section_type in section_types:
            try:
                results = self.rag.query(section_type, query, n_results=2)
                if results:
                    sanitized = []
                    for r in results:
                        if isinstance(r, dict):
                            content = r.get('content', str(r))
                        elif hasattr(r, 'content'):
                            content = r.content
                        else:
                            content = str(r)

                        # SANITIZE: Strip all numerical values
                        if self.sanitizer:
                            content = self.sanitizer.sanitize(content)

                        sanitized.append(content)

                    examples[section_type] = sanitized
            except Exception as e:
                print(f"[RAG] Error querying {section_type}: {e}")

        return examples

    def _generate_all_sections(
        self,
        facts: Dict[str, Any],
        constraints: MethodConstraints,
        sanitized_examples: Dict[str, List[str]]
    ) -> Dict[str, str]:
        """Step 4: Generate all SAP sections with constrained prompts."""
        sections = {}

        for section_key, section_title in self.SECTIONS:
            # Get relevant examples
            examples = sanitized_examples.get(section_key, [])
            if not examples and section_key == 'statistical_methods':
                examples = sanitized_examples.get('methods', [])

            # Generate section
            section_text = self._generate_section(
                section_key, section_title, facts, constraints, examples
            )
            sections[section_key] = section_text

        return sections

    def _generate_section(
        self,
        section_key: str,
        section_title: str,
        facts: Dict[str, Any],
        constraints: MethodConstraints,
        examples: List[str]
    ) -> str:
        """Generate a single section with constrained prompt."""

        # Build the constrained prompt
        prompt = self._build_constrained_prompt(
            section_key, section_title, facts, constraints, examples
        )

        # Generate with LLM
        if self.llm:
            try:
                response = self.llm.chat(prompt, max_tokens=2000)
                if hasattr(response, 'success') and response.success and hasattr(response, 'content'):
                    return response.content
                elif isinstance(response, str) and response:
                    return response
            except Exception as e:
                print(f"[Generation] LLM error for {section_key}: {e}")

        # Fallback to template
        return self._generate_fallback(section_key, section_title, facts, constraints)

    def _build_constrained_prompt(
        self,
        section_key: str,
        section_title: str,
        facts: Dict[str, Any],
        constraints: MethodConstraints,
        examples: List[str]
    ) -> str:
        """
        Build prompt with explicit source attribution and priority.
        This is the key to preventing RAG contamination.
        """

        # Format numerical facts (GROUND TRUTH)
        facts_section = self._format_numerical_facts(facts, section_key)

        # Format method constraints
        constraints_section = self._format_constraints(constraints, section_key)

        # Format sanitized examples
        examples_section = "\n\n---\n\n".join(examples[:2]) if examples else "No examples available."

        return f"""You are an expert biostatistician writing a Statistical Analysis Plan section.

## CRITICAL INSTRUCTIONS:
1. Use ONLY the numerical values from "PROTOCOL FACTS" below - these are GROUND TRUTH
2. Use ONLY the methods from "METHOD CONSTRAINTS" below
3. Use the "EXAMPLE" for prose style ONLY - it has placeholders, not actual numbers
4. If a value is not in PROTOCOL FACTS, write "[To be specified]"
5. NEVER invent or assume numerical values

## PROTOCOL FACTS (Source: Protocol Extraction - USE THESE EXACTLY):
{facts_section}

## METHOD CONSTRAINTS (Source: Knowledge Graph - USE THESE METHODS):
{constraints_section}

## EXAMPLE PROSE STYLE (for structure only - numbers are placeholders):
{examples_section}

## SECTION TO WRITE: {section_title}

Write the {section_title} section now.
- Use EXACT numbers from PROTOCOL FACTS
- Use EXACT methods from METHOD CONSTRAINTS
- Match prose style of EXAMPLE but with YOUR numbers and methods
- Start with "## {section_title}" as header
"""

    def _format_numerical_facts(self, facts: Dict[str, Any], section_key: str) -> str:
        """Format numerical facts for the prompt."""
        lines = []

        # Always include these
        if facts.get('nct_id'):
            lines.append(f"- NCT ID: {facts['nct_id']}")
        if facts.get('sample_size'):
            lines.append(f"- Sample Size: {facts['sample_size']} patients")
        if facts.get('drug_name'):
            lines.append(f"- Study Drug: {facts['drug_name']}")
        if facts.get('comparator'):
            lines.append(f"- Comparator: {facts['comparator']}")

        # Section-specific facts
        if section_key in ['statistical_methods', 'interim_analysis']:
            if facts.get('final_events') or facts.get('final_analysis_events'):
                events = facts.get('final_events') or facts.get('final_analysis_events')
                lines.append(f"- Events at Final Analysis: {events} deaths")
            if facts.get('interim_events') or facts.get('interim_analysis_events'):
                events = facts.get('interim_events') or facts.get('interim_analysis_events')
                lines.append(f"- Events at Interim Analysis: {events} deaths")
            if facts.get('num_interim_analyses') or facts.get('num_interim'):
                num = facts.get('num_interim_analyses') or facts.get('num_interim')
                lines.append(f"- Number of Interim Analyses: {num}")
            if facts.get('alpha_at_interim') or facts.get('interim_alpha_spent'):
                alpha = facts.get('alpha_at_interim')
                if not alpha and facts.get('interim_alpha_spent'):
                    alpha = facts['interim_alpha_spent'][0] if isinstance(facts['interim_alpha_spent'], list) else facts['interim_alpha_spent']
                if alpha:
                    lines.append(f"- Alpha at Interim: {alpha}")
            if facts.get('alpha_at_final') or facts.get('alpha_level'):
                alpha = facts.get('alpha_at_final') or facts.get('alpha_level')
                lines.append(f"- Alpha at Final: {alpha}")
            if facts.get('error_spending_function'):
                lines.append(f"- Error Spending Function: {facts['error_spending_function']}")
            if facts.get('stopping_boundaries'):
                lines.append(f"- Stopping Boundaries: {facts['stopping_boundaries']}")

        if section_key == 'sample_size':
            if facts.get('power'):
                power = facts['power']
                if power < 1:
                    power = power * 100
                lines.append(f"- Statistical Power: {int(power)}%")
            if facts.get('expected_hazard_ratio') or facts.get('hazard_ratio'):
                hr = facts.get('expected_hazard_ratio') or facts.get('hazard_ratio')
                lines.append(f"- Expected Hazard Ratio: {hr}")

        if section_key == 'objectives':
            if facts.get('primary_endpoint'):
                lines.append(f"- Primary Endpoint: {facts['primary_endpoint']}")
            if facts.get('secondary_endpoints'):
                endpoints = facts['secondary_endpoints']
                if isinstance(endpoints, list):
                    endpoints = ', '.join(str(e) for e in endpoints[:3])
                lines.append(f"- Secondary Endpoints: {endpoints}")

        return '\n'.join(lines) if lines else "No specific numerical facts for this section."

    def _format_constraints(self, constraints: MethodConstraints, section_key: str) -> str:
        """Format method constraints for the prompt."""
        lines = []

        if section_key == 'statistical_methods':
            if constraints.primary_test:
                lines.append(f"- PRIMARY TEST: {constraints.primary_test}")
            if constraints.forbidden_primary:
                lines.append(f"- DO NOT use as primary: {constraints.forbidden_primary}")
            if constraints.nph_methods:
                lines.append(f"- NPH Methods: {', '.join(constraints.nph_methods)}")
            if constraints.sensitivity_methods:
                lines.append(f"- Sensitivity Methods: {', '.join(constraints.sensitivity_methods)}")
            lines.append("- Include: estimands (ICH E9 R1), censoring rules, stratification factors")

        elif section_key == 'interim_analysis':
            if constraints.interim_method:
                lines.append(f"- Interim Method: {constraints.interim_method}")
            if constraints.alpha_spending:
                lines.append(f"- Alpha Spending: {constraints.alpha_spending}")
            lines.append("- Include: information fractions, stopping boundaries, alpha allocation")

        elif section_key == 'sensitivity_analysis':
            if constraints.sensitivity_methods:
                lines.append(f"- Required Methods: {', '.join(constraints.sensitivity_methods)}")
            if 'crossover' in constraints.conditions_detected or 'treatment_switching' in constraints.conditions_detected:
                lines.append("- Treatment Switching: Include RPSFT and IPCW if crossover present")

        return '\n'.join(lines) if lines else "No specific method constraints for this section."

    def _generate_fallback(
        self,
        section_key: str,
        section_title: str,
        facts: Dict[str, Any],
        constraints: MethodConstraints
    ) -> str:
        """Generate section using templates (fallback when LLM unavailable)."""

        if section_key == 'statistical_methods':
            return self._fallback_statistical_methods(facts, constraints)
        elif section_key == 'interim_analysis':
            return self._fallback_interim_analysis(facts, constraints)
        else:
            return f"## {section_title}\n\n[Section to be completed based on protocol specifications.]"

    def _fallback_statistical_methods(self, facts: Dict[str, Any], constraints: MethodConstraints) -> str:
        """Template fallback for statistical methods - uses extracted facts."""
        primary_test = constraints.primary_test or "stratified log-rank test"
        endpoint = facts.get('primary_endpoint', 'the primary endpoint')
        final_events = facts.get('final_events') or facts.get('final_analysis_events') or '[N]'

        text = f"""## Statistical Methods

### Primary Analysis

The primary efficacy endpoint ({endpoint}) will be analyzed using the **{primary_test}**.

The analysis will be based on {final_events} death events.
"""
        if constraints.nph_methods:
            text += f"""
### Non-Proportional Hazards Methods

Given the expected delayed treatment effect, the following methods will be used:
"""
            for method in constraints.nph_methods:
                text += f"- {method}\n"

        return text

    def _fallback_interim_analysis(self, facts: Dict[str, Any], constraints: MethodConstraints) -> str:
        """Template fallback for interim analysis - uses extracted facts."""
        method = constraints.interim_method or "Lan-DeMets"
        spending = constraints.alpha_spending or "O'Brien-Fleming"
        num_interim = facts.get('num_interim_analyses') or facts.get('num_interim') or 1
        interim_events = facts.get('interim_events') or facts.get('interim_analysis_events') or '[N]'
        final_events = facts.get('final_events') or facts.get('final_analysis_events') or '[N]'
        alpha_interim = facts.get('alpha_at_interim') or '[α]'
        alpha_final = facts.get('alpha_at_final') or facts.get('alpha_level') or '[α]'

        return f"""## Interim Analysis

### Alpha Spending Approach

{num_interim} interim analysis will be conducted using the {method} alpha spending function with {spending} spending boundaries.

### Analysis Schedule

- Interim Analysis: At {interim_events} events
- Final Analysis: At {final_events} events

### Stopping Boundaries

- At interim: Reject H₀ if p < {alpha_interim}
- At final: Reject H₀ if p < {alpha_final}
"""

    def _verify_and_correct(
        self,
        sap_text: str,
        facts: Dict[str, Any],
        constraints: MethodConstraints
    ) -> Tuple[Optional[VerificationResult], str, int]:
        """
        Step 5: SELF-RAG verification and correction loop.

        Returns:
            Tuple of (verification_result, corrected_text, regeneration_count)
        """
        if not self.verifier:
            return None, sap_text, 0

        regeneration_count = 0
        current_text = sap_text

        for attempt in range(self.max_regenerations + 1):
            # Verify current text
            constraints_dict = {
                'primary_test': constraints.primary_test,
                'forbidden_primary': constraints.forbidden_primary,
            }
            verification = self.verifier.verify(current_text, facts, constraints_dict)

            if verification.passed:
                return verification, current_text, regeneration_count

            if attempt < self.max_regenerations:
                print(f"[Verification] Attempt {attempt + 1} failed, regenerating...")
                print(f"[Verification] Errors: {[e.context for e in verification.errors]}")

                # Generate correction prompt
                correction_prompt = self.verifier.generate_correction_prompt(current_text, facts)

                # Regenerate
                if self.llm:
                    try:
                        response = self.llm.chat(correction_prompt, max_tokens=3000)
                        if hasattr(response, 'success') and response.success:
                            current_text = response.content
                        elif isinstance(response, str):
                            current_text = response
                        regeneration_count += 1
                    except Exception as e:
                        print(f"[Verification] Regeneration error: {e}")
                        break

        return verification, current_text, regeneration_count

    def _assemble_sap(self, sections: Dict[str, str], facts: Dict[str, Any]) -> str:
        """Assemble sections into full SAP document."""
        nct_id = facts.get('nct_id', 'NCT_UNKNOWN')
        drug = facts.get('drug_name', 'Study Drug')

        sap_text = f"""# STATISTICAL ANALYSIS PLAN

**Protocol:** {nct_id}
**Study Drug:** {drug}
**Version:** 1.0
**Date:** [DATE]

---

"""
        section_order = [
            'introduction', 'objectives', 'study_design', 'sample_size',
            'analysis_populations', 'statistical_methods', 'interim_analysis',
            'sensitivity_analysis', 'missing_data', 'multiplicity', 'safety'
        ]

        for section_key in section_order:
            if section_key in sections:
                sap_text += sections[section_key] + "\n\n---\n\n"

        return sap_text


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_production_pipeline(max_regenerations: int = 2) -> ProductionSAPPipeline:
    """Factory function to create the production pipeline."""
    return ProductionSAPPipeline(max_regenerations=max_regenerations)


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TESTING PRODUCTION SAP PIPELINE")
    print("=" * 60)

    test_protocol = """
    NCT02041533 - CheckMate 078
    Phase 3, Randomized Study of Nivolumab vs Docetaxel in NSCLC

    Primary Endpoint: Overall Survival (OS)
    Sample Size: 504 patients (2:1 randomization)

    Immunotherapy checkpoint inhibitor - delayed treatment effect expected.

    INTERIM ANALYSIS:
    - One interim analysis at 291 events (76% information)
    - Final analysis at 382 events
    - Alpha at interim: 0.020
    - Alpha at final: 0.044
    - Lan-DeMets with O'Brien-Fleming spending function

    CROSSOVER: Patients on docetaxel may cross over to nivolumab upon progression.
    """

    pipeline = create_production_pipeline()
    result = pipeline.generate(test_protocol)

    print(f"\n{'=' * 60}")
    print("RESULT")
    print("=" * 60)
    print(f"Success: {result.success}")
    print(f"Regenerations: {result.regeneration_count}")

    if result.verification:
        print(f"Verification passed: {result.verification.passed}")
        print(f"Score: {result.verification.score:.2f}")
        if result.verification.errors:
            print("Errors:")
            for e in result.verification.errors:
                print(f"  - {e.field}: {e.context}")

    print(f"\nSAP length: {len(result.sap_text)} chars")
    print("\nFirst 2000 chars:")
    print("-" * 60)
    print(result.sap_text[:2000])
