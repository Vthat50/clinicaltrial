"""
Rule-Based SAP Pipeline
========================
Architecture: REASONER -> LLM WRITER -> VERIFIER

Uses existing components:
- StructuredFactExtractor (fact extraction)
- KnowledgeRuleEngine (condition detection + method slots)
- ChromaDB RAG (real SAP examples)

New components:
- ConstrainedSAPWriter (LLM writes prose with slot constraints)
- SlotVerifier (checks critical methods are included)
"""

import json
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

# Import existing components - try both relative and absolute imports
try:
    from .schemas import StructuredFactExtractor
except ImportError:
    try:
        from enterprise_sap_system.core.schemas import StructuredFactExtractor
    except ImportError:
        StructuredFactExtractor = None

# Import Claude extractor for LLM-based extraction
try:
    from .claude_extractor import ClaudeProtocolExtractor
except ImportError:
    try:
        from enterprise_sap_system.core.claude_extractor import ClaudeProtocolExtractor
    except ImportError:
        ClaudeProtocolExtractor = None

try:
    from .knowledge_rule_engine import KnowledgeRuleEngine
except ImportError:
    try:
        from enterprise_sap_system.core.knowledge_rule_engine import KnowledgeRuleEngine
    except ImportError:
        KnowledgeRuleEngine = None

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
    try:
        from enterprise_sap_system.core.tiered_llm import TieredLLMClient
    except ImportError:
        TieredLLMClient = None


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class SlotConstraints:
    """Method slots determined by the Reasoner (Knowledge Graph)"""
    primary_test: str = "stratified log-rank"
    primary_test_params: Dict[str, Any] = field(default_factory=dict)
    nph_methods: List[str] = field(default_factory=list)
    sensitivity_methods: List[str] = field(default_factory=list)
    interim_method: str = ""
    alpha_spending: str = ""
    multiplicity_method: str = ""
    conditions_detected: List[str] = field(default_factory=list)


@dataclass
class VerificationResult:
    """Result of slot verification"""
    passed: bool
    missing_slots: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    details: Dict[str, bool] = field(default_factory=dict)


@dataclass
class GenerationResult:
    """Final SAP generation result"""
    success: bool
    sap_text: str = ""
    sections: Dict[str, str] = field(default_factory=dict)
    slot_constraints: Optional[SlotConstraints] = None
    verification: Optional[VerificationResult] = None
    facts: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    error: str = ""


# =============================================================================
# SLOT VERIFIER (Step 6)
# =============================================================================

class SlotVerifier:
    """
    Verifies that generated SAP contains required method slots.
    Deterministic checker - no LLM needed.
    """

    # Method name variations for matching
    METHOD_ALIASES = {
        'fleming_harrington': ['fleming-harrington', 'fleming harrington', 'fh test', 'fh(', 'weighted log-rank', 'g(ρ', 'g(rho'],
        'fleming-harrington': ['fleming-harrington', 'fleming harrington', 'fh test', 'fh(', 'weighted log-rank', 'g(ρ', 'g(rho'],
        'rpsft': ['rpsft', 'rank preserving structural failure time', 'rank-preserving'],
        'ipcw': ['ipcw', 'inverse probability of censoring', 'inverse probability weighting'],
        'lan_demets': ['lan-demets', 'lan demets', 'alpha spending', 'spending function'],
        'lan-demets': ['lan-demets', 'lan demets', 'alpha spending', 'spending function'],
        'obrien_fleming': ["o'brien-fleming", 'obrien-fleming', 'obrien fleming', 'ofb'],
        'rmst': ['rmst', 'restricted mean survival time', 'restricted mean'],
        'landmark_analysis': ['landmark', 'milestone survival', 'milestone analysis', '12-month', '18-month', '24-month', 'month survival rate'],
        'maxcombo': ['maxcombo', 'max-combo', 'maximum combination'],
        'hierarchical': ['hierarchical', 'gatekeeping', 'fixed-sequence', 'sequential testing'],
        'hochberg': ['hochberg', 'simes'],
        'holm': ['holm', 'holm-bonferroni'],
        'cox': ['cox proportional', 'cox regression', 'cox model', 'cox ph'],
        'kaplan_meier': ['kaplan-meier', 'kaplan meier', 'km estimate', 'km curve'],
        'log_rank': ['log-rank', 'logrank', 'log rank'],
        'logrank': ['log-rank', 'logrank', 'log rank', 'log-rank test'],
    }

    def verify(self, generated_text: str, constraints: SlotConstraints) -> VerificationResult:
        """Verify that generated SAP contains required methods."""
        text_lower = generated_text.lower()
        missing = []
        warnings = []
        details = {}

        # Check primary test
        if constraints.primary_test:
            found = self._find_method(text_lower, constraints.primary_test)
            details['primary_test'] = found
            if not found:
                missing.append(f"Primary test: {constraints.primary_test}")

        # Check NPH methods (if immunotherapy/delayed effect detected)
        if constraints.nph_methods:
            for method in constraints.nph_methods:
                found = self._find_method(text_lower, method)
                details[f'nph_{method}'] = found
                if not found:
                    missing.append(f"NPH method: {method}")

        # Check sensitivity methods (critical for crossover)
        if constraints.sensitivity_methods:
            for method in constraints.sensitivity_methods:
                found = self._find_method(text_lower, method)
                details[f'sensitivity_{method}'] = found
                if not found:
                    missing.append(f"Sensitivity method: {method}")

        # Check interim analysis method
        if constraints.interim_method:
            found = self._find_method(text_lower, constraints.interim_method)
            details['interim_method'] = found
            if not found:
                missing.append(f"Interim method: {constraints.interim_method}")

        # Check alpha spending
        if constraints.alpha_spending:
            found = self._find_method(text_lower, constraints.alpha_spending)
            details['alpha_spending'] = found
            if not found:
                warnings.append(f"Alpha spending not explicit: {constraints.alpha_spending}")

        # Check multiplicity
        if constraints.multiplicity_method:
            found = self._find_method(text_lower, constraints.multiplicity_method)
            details['multiplicity'] = found
            if not found:
                warnings.append(f"Multiplicity method not explicit: {constraints.multiplicity_method}")

        passed = len(missing) == 0
        return VerificationResult(
            passed=passed,
            missing_slots=missing,
            warnings=warnings,
            details=details
        )

    def _find_method(self, text: str, method: str) -> bool:
        """Check if method is mentioned in text."""
        method_key = method.lower().replace('-', '_').replace(' ', '_')

        # Check direct mention
        if method.lower() in text:
            return True

        # Check aliases
        aliases = self.METHOD_ALIASES.get(method_key, [])
        for alias in aliases:
            if alias in text:
                return True

        return False


# =============================================================================
# CONSTRAINED SAP WRITER (Step 5)
# =============================================================================

class ConstrainedSAPWriter:
    """
    LLM-based writer that generates SAP prose with slot constraints.
    The LLM MUST use the methods specified by the Reasoner.
    """

    # SAP section order
    SECTIONS = [
        ('introduction', 'Introduction'),
        ('objectives', 'Study Objectives and Endpoints'),
        ('study_design', 'Study Design'),
        ('sample_size', 'Sample Size'),
        ('analysis_populations', 'Analysis Populations'),
        ('statistical_methods', 'Statistical Methods'),
        ('interim_analysis', 'Interim Analysis'),
        ('sensitivity_analysis', 'Sensitivity Analyses'),
        ('missing_data', 'Missing Data'),
        ('multiplicity', 'Multiplicity Adjustment'),
        ('safety', 'Safety Analyses'),
    ]

    def __init__(self, llm_client=None, rag_store=None):
        self.llm = llm_client
        self.rag = rag_store

        # Initialize LLM if not provided
        if self.llm is None and TieredLLMClient:
            try:
                self.llm = TieredLLMClient()
            except Exception as e:
                print(f"[ConstrainedSAPWriter] Warning: Could not initialize LLM: {e}")

    def write_full_sap(
        self,
        facts: Dict[str, Any],
        constraints: SlotConstraints,
        rag_examples: Dict[str, List[str]]
    ) -> Dict[str, str]:
        """Generate all SAP sections with slot constraints."""
        sections = {}

        for section_key, section_title in self.SECTIONS:
            examples = rag_examples.get(section_key, [])
            section_text = self.write_section(
                section_key, section_title, facts, constraints, examples
            )
            sections[section_key] = section_text

        return sections

    def write_section(
        self,
        section_key: str,
        section_title: str,
        facts: Dict[str, Any],
        constraints: SlotConstraints,
        examples: List[str]
    ) -> str:
        """Generate a single SAP section."""

        # Build constraint instructions based on section
        constraint_text = self._build_constraint_instructions(section_key, constraints)

        # Format examples
        examples_text = "\n\n---\n\n".join(examples[:2]) if examples else "No examples available."

        # Format facts
        facts_text = self._format_facts(facts)

        # Build prompt
        prompt = self._build_section_prompt(
            section_key, section_title, facts_text, constraint_text, examples_text
        )

        # Generate with LLM
        if self.llm:
            try:
                response = self.llm.chat(prompt, max_tokens=2000)
                # Check if LLM returned successfully with content
                if hasattr(response, 'success') and response.success and hasattr(response, 'content') and response.content:
                    return response.content
                elif isinstance(response, str) and response:
                    return response
                else:
                    # LLM failed or returned empty - use fallback
                    return self._generate_fallback(section_key, section_title, facts, constraints)
            except Exception as e:
                print(f"[ConstrainedSAPWriter] LLM error for {section_key}: {e}")
                return self._generate_fallback(section_key, section_title, facts, constraints)
        else:
            # No LLM - use template fallback
            return self._generate_fallback(section_key, section_title, facts, constraints)

    def _build_constraint_instructions(self, section_key: str, constraints: SlotConstraints) -> str:
        """Build method constraint instructions for prompt."""
        instructions = []

        if section_key == 'statistical_methods':
            instructions.append(f"PRIMARY ANALYSIS TEST: You MUST use {constraints.primary_test}")
            instructions.append(f"CRITICAL: The PRIMARY test is {constraints.primary_test} - do NOT use stratified log-rank as the primary test for immunotherapy trials")
            if constraints.primary_test_params:
                instructions.append(f"TEST PARAMETERS: {constraints.primary_test_params}")
            if constraints.nph_methods:
                instructions.append(f"NPH METHODS (required for immunotherapy): {', '.join(constraints.nph_methods)}")
            instructions.append("Stratified log-rank test should only be used as a SENSITIVITY analysis, not the primary test")
            instructions.append("Include: estimands (ICH E9 R1), censoring rules, model covariates")

        elif section_key == 'sensitivity_analysis':
            if constraints.sensitivity_methods:
                instructions.append(f"REQUIRED SENSITIVITY METHODS: {', '.join(constraints.sensitivity_methods)}")
                if 'rpsft' in [m.lower() for m in constraints.sensitivity_methods]:
                    instructions.append("RPSFT: Explain rank-preserving structural failure time model for treatment switching")
                if 'ipcw' in [m.lower() for m in constraints.sensitivity_methods]:
                    instructions.append("IPCW: Explain inverse probability of censoring weighting for crossover adjustment")

        elif section_key == 'interim_analysis':
            if constraints.interim_method:
                instructions.append(f"INTERIM METHOD: {constraints.interim_method}")
            if constraints.alpha_spending:
                instructions.append(f"ALPHA SPENDING: {constraints.alpha_spending}")
            instructions.append("Include: number of analyses, information fractions, stopping boundaries")

        elif section_key == 'multiplicity':
            if constraints.multiplicity_method:
                instructions.append(f"MULTIPLICITY METHOD: {constraints.multiplicity_method}")
            instructions.append("Include: testing hierarchy, alpha allocation, gatekeeping rules")

        if not instructions:
            return "No specific method constraints for this section."

        return "REQUIRED METHODS (from knowledge graph - MUST USE THESE):\n" + "\n".join(f"- {i}" for i in instructions)

    def _build_section_prompt(
        self,
        section_key: str,
        section_title: str,
        facts_text: str,
        constraint_text: str,
        examples_text: str
    ) -> str:
        """Build the LLM prompt for section generation."""
        return f"""You are an expert biostatistician writing a Statistical Analysis Plan (SAP) section.

SECTION TO WRITE: {section_title}

{constraint_text}

PROTOCOL FACTS:
{facts_text}

EXAMPLES FROM REAL SAPs (use as reference for style and detail):
{examples_text}

INSTRUCTIONS:
1. Write the {section_title} section in formal SAP language
2. MUST include all required methods specified above
3. Use ICH E9 / ICH E9(R1) terminology where appropriate
4. Be specific about parameters, thresholds, and decision rules
5. Reference the protocol facts provided

Write the section now. Start with "## {section_title}" as the header."""

    def _format_facts(self, facts: Dict[str, Any]) -> str:
        """Format facts for prompt."""
        key_facts = [
            ('nct_id', 'NCT ID'),
            ('drug_name', 'Study Drug'),
            ('comparator', 'Comparator'),
            ('indication', 'Indication'),
            ('phase', 'Phase'),
            ('primary_endpoint', 'Primary Endpoint'),
            ('secondary_endpoints', 'Secondary Endpoints'),
            ('sample_size', 'Sample Size'),
            ('randomization_ratio', 'Randomization'),
            ('stratification_factors', 'Stratification'),
        ]

        lines = []
        for key, label in key_facts:
            value = facts.get(key)
            if value:
                if isinstance(value, list):
                    value = ', '.join(str(v) for v in value)
                lines.append(f"- {label}: {value}")

        return '\n'.join(lines) if lines else "No facts extracted."

    def _generate_fallback(
        self,
        section_key: str,
        section_title: str,
        facts: Dict[str, Any],
        constraints: SlotConstraints
    ) -> str:
        """Generate section without LLM using templates."""

        if section_key == 'statistical_methods':
            return self._fallback_statistical_methods(facts, constraints)
        elif section_key == 'sensitivity_analysis':
            return self._fallback_sensitivity_analysis(facts, constraints)
        elif section_key == 'interim_analysis':
            return self._fallback_interim_analysis(facts, constraints)
        else:
            return f"## {section_title}\n\n[Section to be completed based on protocol specifications.]"

    def _fallback_statistical_methods(self, facts: Dict[str, Any], constraints: SlotConstraints) -> str:
        """Template fallback for statistical methods."""
        primary_test = constraints.primary_test or "stratified log-rank test"
        endpoint = facts.get('primary_endpoint', 'the primary endpoint')

        text = f"""## Statistical Methods

### Primary Analysis

The primary efficacy endpoint ({endpoint}) will be analyzed using the {primary_test}.

"""
        if constraints.nph_methods:
            text += f"""### Non-Proportional Hazards Methods

Given the expected delayed treatment effect pattern, the following methods will be used:
"""
            for method in constraints.nph_methods:
                if 'fleming' in method.lower():
                    text += """
- **Fleming-Harrington Test**: A weighted log-rank test with weights G(rho, gamma) will be used to increase sensitivity to late differences in survival curves. Parameters will be pre-specified based on expected delayed effect.
"""
                elif 'rmst' in method.lower():
                    text += """
- **Restricted Mean Survival Time (RMST)**: RMST difference will be calculated as a supportive analysis, providing a clinically interpretable measure of treatment benefit.
"""

        text += """
### Hazard Ratio Estimation

Hazard ratios and 95% confidence intervals will be estimated using a Cox proportional hazards model, stratified by the randomization stratification factors.

### Estimand Framework (ICH E9 R1)

The primary estimand is defined as:
- **Population**: All randomized patients (ITT)
- **Variable**: Time to event
- **Intercurrent Events**: Treatment discontinuation handled using treatment policy strategy
- **Summary Measure**: Hazard ratio
"""
        return text

    def _fallback_sensitivity_analysis(self, facts: Dict[str, Any], constraints: SlotConstraints) -> str:
        """Template fallback for sensitivity analysis."""
        text = """## Sensitivity Analyses

The following sensitivity analyses will be conducted to assess the robustness of the primary analysis:

"""
        if constraints.sensitivity_methods:
            if 'rpsft' in [m.lower() for m in constraints.sensitivity_methods]:
                text += """### Treatment Switching Adjustment: RPSFT

The Rank Preserving Structural Failure Time (RPSFT) model will be used to adjust for treatment switching/crossover from control to experimental arm. This method:
- Estimates the causal treatment effect by adjusting for switching
- Uses the g-estimation procedure to find the treatment effect parameter
- Provides counterfactual survival times had patients not switched
- Is recommended by NICE TSD16 for treatment switching adjustment

"""
            if 'ipcw' in [m.lower() for m in constraints.sensitivity_methods]:
                text += """### Treatment Switching Adjustment: IPCW

Inverse Probability of Censoring Weighting (IPCW) will be used as an alternative sensitivity analysis:
- Patients who switch are censored at the time of switching
- Weights are calculated based on probability of remaining on assigned treatment
- Provides an estimate of treatment effect in absence of switching
- Complements RPSFT by using a different statistical framework

"""
        else:
            text += """### Standard Sensitivity Analyses

- Per-protocol population analysis
- Tipping point analysis for missing data
- Alternative censoring rules
"""

        return text

    def _fallback_interim_analysis(self, facts: Dict[str, Any], constraints: SlotConstraints) -> str:
        """Template fallback for interim analysis."""
        method = constraints.interim_method or "Lan-DeMets"
        spending = constraints.alpha_spending or "O'Brien-Fleming"

        return f"""## Interim Analysis

### Alpha Spending Approach

Interim analyses will be conducted using the {method} alpha spending function with {spending} spending boundaries.

### Analysis Schedule

- Interim Analysis 1: At approximately 50% of planned events
- Interim Analysis 2: At approximately 75% of planned events
- Final Analysis: At 100% of planned events

### Stopping Rules

The study may be stopped early for:
- **Efficacy**: If the observed p-value crosses the efficacy boundary
- **Futility**: If conditional power falls below 10% (non-binding)

### Alpha Allocation

The overall Type I error rate of 0.025 (one-sided) will be preserved across all analyses using the pre-specified spending function.
"""


# =============================================================================
# MAIN PIPELINE (Combines all steps)
# =============================================================================

class RuleBasedSAPPipeline:
    """
    Main pipeline: REASONER -> LLM WRITER -> VERIFIER

    Uses existing components:
    - StructuredFactExtractor
    - KnowledgeRuleEngine
    - ChromaDB RAG

    Adds:
    - ConstrainedSAPWriter
    - SlotVerifier
    """

    def __init__(self, use_llm_extraction: bool = True):
        # Step 1: Fact Extractor - prefer Claude LLM extraction
        self.claude_extractor = None
        self.regex_extractor = None

        if use_llm_extraction and ClaudeProtocolExtractor:
            try:
                self.claude_extractor = ClaudeProtocolExtractor()
                print("[Pipeline] Using ClaudeProtocolExtractor (LLM-based)")
            except Exception as e:
                print(f"[Pipeline] ClaudeProtocolExtractor failed: {e}")

        # Fallback to regex extractor
        if StructuredFactExtractor:
            self.regex_extractor = StructuredFactExtractor()
            if not self.claude_extractor:
                print("[Pipeline] Using StructuredFactExtractor (regex fallback)")

        if not self.claude_extractor and not self.regex_extractor:
            print("[Pipeline] Warning: No extractors available")

        # Step 2-3: Knowledge Rule Engine (REUSE)
        if KnowledgeRuleEngine:
            self.knowledge_engine = KnowledgeRuleEngine()
            print(f"[Pipeline] Loaded KnowledgeRuleEngine with {len(self.knowledge_engine.rules)} rules")
        else:
            self.knowledge_engine = None
            print("[Pipeline] Warning: KnowledgeRuleEngine not available")

        # Step 4: RAG Store (REUSE)
        if create_vector_store:
            try:
                self.rag = create_vector_store()
                print("[Pipeline] Connected to ChromaDB RAG")
            except Exception as e:
                self.rag = None
                print(f"[Pipeline] Warning: RAG not available: {e}")
        else:
            self.rag = None

        # Step 5: Constrained Writer (NEW)
        self.writer = ConstrainedSAPWriter(rag_store=self.rag)

        # Step 6: Verifier (NEW)
        self.verifier = SlotVerifier()

    def generate(self, protocol_text: str, max_retries: int = 2) -> GenerationResult:
        """
        Generate SAP using the full pipeline.

        STEP 1: Extract facts from protocol
        STEP 2: Detect conditions (crossover, immunotherapy, etc.)
        STEP 3: Get method slot constraints from knowledge graph
        STEP 4: Query RAG for examples
        STEP 5: LLM writes prose with constraints
        STEP 6: Verify slots are correct
        """

        try:
            # STEP 1: Extract facts
            print("[Pipeline] Step 1: Extracting facts...")
            facts = self._extract_facts(protocol_text)

            # STEP 2: Detect conditions
            print("[Pipeline] Step 2: Detecting conditions...")
            conditions = self._detect_conditions(facts, protocol_text)
            print(f"[Pipeline] Detected conditions: {conditions}")

            # STEP 3: Get method constraints (REASONER)
            print("[Pipeline] Step 3: Getting method constraints from knowledge graph...")
            constraints = self._get_slot_constraints(facts, conditions)
            print(f"[Pipeline] Constraints: primary={constraints.primary_test}, sensitivity={constraints.sensitivity_methods}")

            # STEP 4: Query RAG for examples
            print("[Pipeline] Step 4: Querying RAG for examples...")
            rag_examples = self._query_rag(facts, conditions)

            # STEP 5: Generate with LLM (WRITER)
            print("[Pipeline] Step 5: Generating SAP with LLM writer...")
            sections = self.writer.write_full_sap(facts, constraints, rag_examples)

            # Assemble full SAP
            sap_text = self._assemble_sap(sections, facts)

            # STEP 6: Verify (VERIFIER)
            print("[Pipeline] Step 6: Verifying slot constraints...")
            verification = self.verifier.verify(sap_text, constraints)

            if not verification.passed:
                print(f"[Pipeline] Verification failed: {verification.missing_slots}")
                # Could retry here with stronger constraints
            else:
                print("[Pipeline] Verification passed!")

            return GenerationResult(
                success=True,
                sap_text=sap_text,
                sections=sections,
                slot_constraints=constraints,
                verification=verification,
                facts=facts
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            return GenerationResult(
                success=False,
                error=str(e)
            )

    def _extract_facts(self, protocol_text: str) -> Dict[str, Any]:
        """Step 1: Extract facts using Claude LLM or regex fallback."""

        # Try Claude LLM extraction first
        if self.claude_extractor:
            try:
                print("[Pipeline] Extracting with Claude LLM...")
                extracted = self.claude_extractor.extract(protocol_text)
                if extracted:
                    # Convert ExtractedProtocol to dict
                    if hasattr(extracted, 'dict'):
                        facts = extracted.dict()
                    elif hasattr(extracted, '__dict__'):
                        facts = {k: v for k, v in extracted.__dict__.items() if not k.startswith('_')}
                    else:
                        facts = dict(extracted)
                    print(f"[Pipeline] Claude extracted: drug={facts.get('drug_name')}, sample_size={facts.get('sample_size')}")
                    return facts
            except Exception as e:
                print(f"[Pipeline] Claude extraction error: {e}")

        # Fallback to regex extractor
        if self.regex_extractor:
            try:
                print("[Pipeline] Falling back to regex extraction...")
                facts = self.regex_extractor.extract_all(protocol_text)
                if hasattr(facts, 'dict'):
                    return facts.dict()
                elif hasattr(facts, '__dict__'):
                    return facts.__dict__
                else:
                    return dict(facts) if facts else {}
            except Exception as e:
                print(f"[Pipeline] Regex extractor error: {e}")

        # Last resort: basic regex extraction
        return self._basic_extraction(protocol_text)

    def _basic_extraction(self, text: str) -> Dict[str, Any]:
        """Basic regex extraction fallback."""
        facts = {}
        text_lower = text.lower()

        # NCT ID
        nct_match = re.search(r'NCT\d{8}', text, re.IGNORECASE)
        if nct_match:
            facts['nct_id'] = nct_match.group()

        # Phase
        phase_match = re.search(r'phase\s*([123]|I{1,3})', text, re.IGNORECASE)
        if phase_match:
            facts['phase'] = phase_match.group()

        # Sample size
        size_match = re.search(r'(\d+)\s*(?:patients|subjects|participants)', text, re.IGNORECASE)
        if size_match:
            facts['sample_size'] = int(size_match.group(1))

        # Crossover detection
        facts['has_crossover'] = 'crossover' in text_lower or 'cross-over' in text_lower

        # Interim analysis detection
        facts['has_interim'] = 'interim' in text_lower

        # Primary endpoint
        endpoint_match = re.search(r'primary\s+endpoint[:\s]+([^\n.]+)', text, re.IGNORECASE)
        if endpoint_match:
            facts['primary_endpoint'] = endpoint_match.group(1).strip()

        # Drug name (simple heuristic)
        drug_patterns = [
            r'(pembrolizumab|nivolumab|atezolizumab|durvalumab|ipilimumab)',
            r'study\s+(?:drug|treatment)[:\s]+(\w+)',
        ]
        for pattern in drug_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                facts['drug_name'] = match.group(1)
                break

        facts['raw_text'] = text_lower
        return facts

    def _detect_conditions(self, facts: Dict[str, Any], protocol_text: str) -> List[str]:
        """Step 2: Detect conditions using knowledge engine."""
        if self.knowledge_engine:
            facts_with_text = {**facts, 'raw_text': protocol_text.lower()}
            conditions = self.knowledge_engine.detect_conditions(facts_with_text)
            return list(conditions)

        # Fallback: basic detection
        conditions = []
        text_lower = protocol_text.lower()

        if 'crossover' in text_lower or facts.get('has_crossover'):
            conditions.extend(['crossover', 'treatment_switching'])
        if 'interim' in text_lower or facts.get('has_interim'):
            conditions.append('interim_analysis')
        if any(x in text_lower for x in ['immunotherapy', 'pd-1', 'pd-l1', 'checkpoint']):
            conditions.extend(['immunotherapy', 'delayed_effect', 'non_proportional_hazards'])
        if any(x in text_lower for x in ['survival', 'pfs', 'os', 'time to']):
            conditions.append('time_to_event')

        return conditions

    def _get_slot_constraints(self, facts: Dict[str, Any], conditions: List[str]) -> SlotConstraints:
        """Step 3: Get method constraints from knowledge graph (REASONER)."""
        constraints = SlotConstraints(conditions_detected=conditions)

        if self.knowledge_engine:
            methods = self.knowledge_engine.get_primary_analysis_methods(facts)

            if methods:
                # Primary test
                primary = methods.get('primary_test', {})
                if primary:
                    constraints.primary_test = primary.get('method', 'stratified log-rank')
                    constraints.primary_test_params = primary.get('params', {})

                # NPH methods - extract and dedupe
                nph = methods.get('nph_methods', [])
                nph_list = [m.get('method', m) if isinstance(m, dict) else m for m in nph]
                # Dedupe while preserving order
                seen = set()
                constraints.nph_methods = []
                for m in nph_list:
                    if m not in seen:
                        seen.add(m)
                        constraints.nph_methods.append(m)

                # Sensitivity methods (critical for crossover)
                sensitivity = methods.get('treatment_switching_methods', [])
                constraints.sensitivity_methods = [m.get('method', m) if isinstance(m, dict) else m for m in sensitivity]

                # Interim
                interim = methods.get('interim_analysis_method', {})
                if interim:
                    constraints.interim_method = interim.get('method', '')
                    constraints.alpha_spending = interim.get('spending_function', "O'Brien-Fleming")

                # Multiplicity
                mult = methods.get('multiplicity_method', {})
                if mult:
                    constraints.multiplicity_method = mult.get('method', '')

        # Apply condition-based defaults
        if 'crossover' in conditions and not constraints.sensitivity_methods:
            constraints.sensitivity_methods = ['RPSFT', 'IPCW']

        # CRITICAL: Immunotherapy + time-to-event = Fleming-Harrington as PRIMARY
        # ALWAYS override for immunotherapy trials - don't trust knowledge graph duplicates
        if 'immunotherapy' in conditions and 'time_to_event' in conditions:
            constraints.primary_test = 'Fleming-Harrington weighted log-rank test G(ρ=0, γ=1)'
            # Set clean NPH methods list - Fleming-Harrington IS the weighted log-rank, no need for duplicates
            constraints.nph_methods = ['Fleming-Harrington', 'RMST', 'landmark_analysis']
        elif 'immunotherapy' in conditions:
            # For immunotherapy without time-to-event
            constraints.nph_methods = ['Fleming-Harrington', 'RMST']

        if 'interim_analysis' in conditions and not constraints.interim_method:
            constraints.interim_method = 'Lan-DeMets'
            constraints.alpha_spending = "O'Brien-Fleming"

        return constraints

    def _query_rag(self, facts: Dict[str, Any], conditions: List[str]) -> Dict[str, List[str]]:
        """Step 4: Query RAG for examples."""
        examples = {}

        if not self.rag:
            return examples

        # Build query from facts - handle dict/list values
        query_parts = []
        for key in ['primary_endpoint', 'indication', 'drug_name']:
            value = facts.get(key)
            if value:
                if isinstance(value, str):
                    query_parts.append(value)
                elif isinstance(value, dict):
                    # Extract string from dict if possible
                    query_parts.append(str(value.get('name', value.get('value', ''))))
                elif isinstance(value, list):
                    query_parts.extend([str(v) for v in value if v])

        query = ' '.join(query_parts) if query_parts else 'oncology phase 3 survival'

        # Query each section type
        section_types = [
            'methods', 'sensitivity_analysis', 'interim_analysis',
            'endpoints', 'sample_size', 'populations', 'safety'
        ]

        for section_type in section_types:
            try:
                # API: query(section_type, query_text, n_results=5, filters=None)
                results = self.rag.query(section_type, query, n_results=2)
                if results:
                    extracted = []
                    for r in results:
                        if isinstance(r, dict):
                            extracted.append(r.get('content', str(r)))
                        elif hasattr(r, 'content'):
                            # RetrievalResult object
                            extracted.append(r.content)
                        else:
                            extracted.append(str(r))
                    examples[section_type] = extracted
            except Exception as e:
                print(f"[Pipeline] RAG query error for {section_type}: {e}")

        return examples

    def _assemble_sap(self, sections: Dict[str, str], facts: Dict[str, Any]) -> str:
        """Assemble sections into full SAP document."""

        # Header
        nct_id = facts.get('nct_id', 'NCT_UNKNOWN')
        drug = facts.get('drug_name', 'Study Drug')

        sap_text = f"""# STATISTICAL ANALYSIS PLAN

**Protocol:** {nct_id}
**Study Drug:** {drug}
**Version:** 1.0
**Date:** [DATE]

---

"""
        # Add sections in order
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

def create_rule_based_pipeline() -> RuleBasedSAPPipeline:
    """Factory function to create the pipeline."""
    return RuleBasedSAPPipeline()


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    # Test the pipeline
    test_protocol = """
    NCT ID: NCT12345678
    Title: Phase 3 Study of Pembrolizumab vs Chemotherapy in Advanced NSCLC

    Phase: 3
    Primary Endpoint: Overall Survival
    Secondary Endpoints: PFS, ORR, DOR

    Design: Randomized, double-blind, placebo-controlled
    Sample Size: 600 patients (1:1 randomization)

    CROSSOVER: Patients randomized to chemotherapy may crossover to pembrolizumab
    upon confirmed disease progression per RECIST v1.1.

    INTERIM ANALYSIS: Two interim analyses planned at 50% and 75% of events.
    Alpha spending using Lan-DeMets with O'Brien-Fleming spending function.

    Stratification: PD-L1 expression (<1% vs >=1%), ECOG PS (0 vs 1), Region
    """

    print("="*60)
    print("TESTING RULE-BASED SAP PIPELINE")
    print("="*60)

    pipeline = create_rule_based_pipeline()
    result = pipeline.generate(test_protocol)

    print(f"\nSuccess: {result.success}")
    print(f"Sections generated: {list(result.sections.keys())}")

    if result.slot_constraints:
        print(f"\nSlot Constraints:")
        print(f"  Primary test: {result.slot_constraints.primary_test}")
        print(f"  NPH methods: {result.slot_constraints.nph_methods}")
        print(f"  Sensitivity: {result.slot_constraints.sensitivity_methods}")
        print(f"  Conditions: {result.slot_constraints.conditions_detected}")

    if result.verification:
        print(f"\nVerification: {'PASSED' if result.verification.passed else 'FAILED'}")
        if result.verification.missing_slots:
            print(f"  Missing: {result.verification.missing_slots}")

    print(f"\nSAP length: {len(result.sap_text)} chars")
    print("\nFirst 2000 chars of SAP:")
    print("-"*60)
    print(result.sap_text[:2000])
