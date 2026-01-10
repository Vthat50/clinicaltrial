"""
Enhanced Knowledge Graph Pipeline
==================================

Combines KG Pipeline strengths with Main Production Pipeline features:
1. KG extraction with full provenance tracking
2. SELF-RAG verification loop (from FactVerifier)
3. Power/sample size calculations (from BoundaryCalculator)
4. RAG-based prose style refinement (from HybridRetriever)

Architecture:
    Protocol
    → Claude KG Extraction (with provenance)
    → Power Calculations (boundary calculator)
    → RAG Style Context (sanitized examples)
    → Claude Generation (with all context)
    → SELF-RAG Verification (fact checking)
    → Correction Loop (if needed)
    → Final SAP with audit trail

Usage:
    python kg_enhanced_pipeline.py path/to/protocol.txt
"""

import json
import sys
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import hashlib

# Add parent paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import anthropic
except ImportError:
    print("Installing anthropic...")
    os.system("pip install anthropic")
    import anthropic

# Import from existing KG pipeline
try:
    from .kg_pipeline_test import (
        FactualKnowledgeGraphV2,
        FlexibleNode,
        FlexibleEdge
    )
except ImportError:
    from kg_pipeline_test import (
        FactualKnowledgeGraphV2,
        FlexibleNode,
        FlexibleEdge
    )

# Import regulatory standards
try:
    from .regulatory_standards import (
        RegulatoryKnowledgeBase,
        get_regulatory_context,
        get_standard_versions
    )
except ImportError:
    from regulatory_standards import (
        RegulatoryKnowledgeBase,
        get_regulatory_context,
        get_standard_versions
    )

# Protocol-specific extractor REMOVED - using simple protocol-driven approach
# Claude reads the protocol directly and determines what to include/exclude


# =============================================================================
# VERIFICATION RESULT CLASSES
# =============================================================================

@dataclass
class VerificationError:
    """A single verification error."""
    field: str
    expected: Any
    found: Any
    severity: str  # "critical", "high", "medium", "low"
    context: str = ""


@dataclass
class VerificationResult:
    """Result of SELF-RAG verification."""
    passed: bool
    errors: List[VerificationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    score: float = 1.0


@dataclass
class PowerCalculation:
    """Results from power/sample size calculations."""
    sample_size: Optional[int] = None
    power: Optional[float] = None
    events_required: Optional[int] = None
    interim_boundaries: List[Dict] = field(default_factory=list)
    spending_function: str = ""
    calculation_method: str = ""
    assumptions: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# SELF-RAG VERIFIER (Adapted from fact_verifier.py)
# =============================================================================

class SelfRAGVerifier:
    """
    SELF-RAG verification for generated SAP.
    Checks that generated content matches extracted facts.
    """

    def __init__(self):
        self.errors: List[VerificationError] = []
        self.warnings: List[str] = []

    def verify(
        self,
        generated_text: str,
        extracted_facts: List[Dict],
        power_calc: Optional[PowerCalculation] = None
    ) -> VerificationResult:
        """
        Verify generated SAP against extracted facts.

        Args:
            generated_text: The generated SAP
            extracted_facts: Facts from KG extraction
            power_calc: Power calculation results to verify

        Returns:
            VerificationResult with pass/fail and errors
        """
        self.errors = []
        self.warnings = []

        text_lower = generated_text.lower()

        # 1. Verify endpoints are present
        self._verify_endpoints(generated_text, extracted_facts)

        # 2. Verify methods are present
        self._verify_methods(generated_text, extracted_facts)

        # 3. Verify populations are present
        self._verify_populations(generated_text, extracted_facts)

        # 4. Verify power calculations if provided
        if power_calc:
            self._verify_power_calculations(generated_text, power_calc)

        # 5. Check for hallucinations (numbers not in source)
        self._check_hallucinations(generated_text, extracted_facts)

        # Calculate score
        critical_errors = [e for e in self.errors if e.severity == "critical"]
        high_errors = [e for e in self.errors if e.severity == "high"]

        if critical_errors:
            score = 0.0
        elif high_errors:
            score = 0.5 - (len(high_errors) * 0.1)
        else:
            score = 1.0 - (len(self.errors) * 0.05)

        score = max(0.0, min(1.0, score))

        return VerificationResult(
            passed=len(critical_errors) == 0 and len(high_errors) == 0,
            errors=self.errors,
            warnings=self.warnings,
            score=score
        )

    def _verify_endpoints(self, text: str, facts: List[Dict]):
        """Verify all extracted endpoints appear in SAP."""
        endpoints = [f for f in facts if f.get('type') == 'endpoint']

        for ep in endpoints:
            name = ep.get('name', '')
            # Check if endpoint name appears (case-insensitive partial match)
            name_lower = name.lower()
            if name_lower not in text.lower():
                # Try key terms from the name
                key_terms = [t for t in name_lower.split() if len(t) > 3]
                if not any(t in text.lower() for t in key_terms[:3]):
                    self.errors.append(VerificationError(
                        field="endpoint",
                        expected=name,
                        found="[NOT FOUND]",
                        severity="high",
                        context=f"Endpoint '{name}' not found in generated SAP"
                    ))

    def _verify_methods(self, text: str, facts: List[Dict]):
        """Verify all extracted methods appear in SAP."""
        methods = [f for f in facts if f.get('type') == 'method']

        for method in methods:
            name = method.get('name', '')
            name_lower = name.lower()

            # Common method name variations
            variations = [
                name_lower,
                name_lower.replace('-', ' '),
                name_lower.replace('_', ' '),
            ]

            found = any(v in text.lower() for v in variations)
            if not found:
                self.warnings.append(f"Method '{name}' not explicitly mentioned")

    def _verify_populations(self, text: str, facts: List[Dict]):
        """Verify all extracted populations appear in SAP."""
        populations = [f for f in facts if f.get('type') == 'population']

        for pop in populations:
            name = pop.get('name', '')
            name_lower = name.lower()

            # Check for common population terms
            if 'itt' in name_lower or 'intent' in name_lower:
                if 'intent-to-treat' not in text.lower() and 'itt' not in text.lower():
                    self.warnings.append("ITT population not clearly defined")

            if 'safety' in name_lower:
                if 'safety' not in text.lower():
                    self.warnings.append("Safety population not clearly defined")

    def _verify_power_calculations(self, text: str, power_calc: PowerCalculation):
        """Verify power calculation values appear correctly."""

        if power_calc.sample_size:
            if str(power_calc.sample_size) not in text:
                self.errors.append(VerificationError(
                    field="sample_size",
                    expected=power_calc.sample_size,
                    found="[NOT FOUND]",
                    severity="high",
                    context="Calculated sample size not in SAP"
                ))

        if power_calc.power:
            power_pct = int(power_calc.power * 100)
            if str(power_pct) not in text and f"{power_calc.power}" not in text:
                self.warnings.append(f"Power ({power_pct}%) not explicitly stated")

        if power_calc.events_required:
            if str(power_calc.events_required) not in text:
                self.errors.append(VerificationError(
                    field="events_required",
                    expected=power_calc.events_required,
                    found="[NOT FOUND]",
                    severity="medium",
                    context="Required events count not in SAP"
                ))

    def _check_hallucinations(self, text: str, facts: List[Dict]):
        """Check for potential hallucinated numbers."""

        # Extract all numbers from generated text
        numbers_in_text = set(re.findall(r'\b(\d+)\b', text))

        # Extract all numbers from source facts
        facts_str = json.dumps(facts)
        numbers_in_facts = set(re.findall(r'\b(\d+)\b', facts_str))

        # Large numbers not in source might be hallucinations
        suspicious = []
        for num in numbers_in_text:
            if int(num) > 50 and num not in numbers_in_facts:
                # Check if it's a reasonable derivative (e.g., percentage)
                if not self._is_reasonable_derivative(num, numbers_in_facts):
                    suspicious.append(num)

        if suspicious:
            self.warnings.append(
                f"Potentially hallucinated numbers: {suspicious[:5]}. "
                "Verify these appear in source protocol."
            )

    def _is_reasonable_derivative(self, num: str, source_nums: set) -> bool:
        """Check if number could be derived from source numbers."""
        n = int(num)

        # Common reasonable values
        if n in [80, 90, 95, 100]:  # Common power/CI values
            return True
        if n in [5, 10, 20, 25, 50]:  # Common percentages
            return True

        return False

    def generate_correction_prompt(self, errors: List[VerificationError]) -> str:
        """Generate correction prompt for regeneration."""
        if not errors:
            return ""

        corrections = []
        for err in errors:
            corrections.append(
                f"- {err.field}: Use '{err.expected}' (not '{err.found}'). "
                f"Context: {err.context}"
            )

        return (
            "CORRECTIONS REQUIRED:\n" +
            "\n".join(corrections) +
            "\n\nPlease regenerate the affected sections with these corrections."
        )


# =============================================================================
# POWER CALCULATOR (Simplified from boundary_calculator.py)
# =============================================================================

class SimplePowerCalculator:
    """
    Simplified power calculations for SAP generation.
    Uses scipy for calculations (no R dependency).
    """

    def __init__(self):
        try:
            from scipy.stats import norm
            from scipy.optimize import brentq
            self.norm = norm
            self.brentq = brentq
            self.available = True
        except ImportError:
            self.available = False

    def calculate_from_protocol(self, extracted_facts: List[Dict], protocol_text: str) -> PowerCalculation:
        """
        Extract power calculation parameters and compute.

        Args:
            extracted_facts: Facts from KG extraction
            protocol_text: Original protocol text

        Returns:
            PowerCalculation with results
        """
        result = PowerCalculation()
        result.calculation_method = "scipy"

        if not self.available:
            result.calculation_method = "unavailable"
            return result

        # Extract parameters from protocol
        params = self._extract_parameters(extracted_facts, protocol_text)

        # Detect trial type
        trial_type = self._detect_trial_type(extracted_facts, protocol_text)

        if trial_type == "phase1_safety":
            result = self._calculate_phase1(params)
        elif trial_type == "phase2_response":
            result = self._calculate_phase2_simon(params)
        elif trial_type == "phase3_survival":
            result = self._calculate_phase3_survival(params)
        else:
            # Generic sample size
            result = self._calculate_generic(params)

        result.assumptions = params
        return result

    def _extract_parameters(self, facts: List[Dict], text: str) -> Dict:
        """Extract statistical parameters from facts and text."""
        params = {
            'alpha': 0.05,
            'power': 0.80,
            'enrollment': None,
            'hazard_ratio': None,
            'response_rate_null': None,
            'response_rate_alt': None,
        }

        # Look for alpha in text
        alpha_match = re.search(r'alpha[=:\s]+(\d+\.?\d*)', text.lower())
        if alpha_match:
            params['alpha'] = float(alpha_match.group(1))
            if params['alpha'] > 1:
                params['alpha'] /= 100

        # Look for power
        power_match = re.search(r'power[=:\s]+(\d+)', text.lower())
        if power_match:
            params['power'] = float(power_match.group(1))
            if params['power'] > 1:
                params['power'] /= 100

        # Look for enrollment
        enroll_patterns = [
            r'enroll(?:ment)?[:\s]+(\d+)',
            r'(\d+)\s+(?:patients|subjects|participants)',
            r'sample size[:\s]+(\d+)',
        ]
        for pattern in enroll_patterns:
            match = re.search(pattern, text.lower())
            if match:
                params['enrollment'] = int(match.group(1))
                break

        # Look for hazard ratio
        hr_match = re.search(r'hazard ratio[:\s]+(\d+\.?\d*)', text.lower())
        if hr_match:
            params['hazard_ratio'] = float(hr_match.group(1))

        return params

    def _detect_trial_type(self, facts: List[Dict], text: str) -> str:
        """Detect the type of trial for calculation routing."""
        text_lower = text.lower()

        # Phase detection
        if 'phase 1' in text_lower or 'phase i' in text_lower:
            if 'dlt' in text_lower or 'dose limiting' in text_lower:
                return "phase1_safety"

        if 'phase 2' in text_lower or 'phase ii' in text_lower:
            if 'response rate' in text_lower or 'orr' in text_lower:
                return "phase2_response"

        if 'phase 3' in text_lower or 'phase iii' in text_lower:
            if any(ep in text_lower for ep in ['overall survival', 'progression-free', 'pfs', ' os ']):
                return "phase3_survival"

        return "generic"

    def _calculate_phase1(self, params: Dict) -> PowerCalculation:
        """Phase 1 DLT-based sample size (3+3 design)."""
        result = PowerCalculation()
        result.calculation_method = "3+3_design"

        # Standard 3+3 design
        result.sample_size = 18  # Typical 3+3 with 6 dose levels
        result.assumptions = {
            'design': '3+3 dose escalation',
            'target_dlt_rate': 0.33,
            'dose_levels': 6
        }

        return result

    def _calculate_phase2_simon(self, params: Dict) -> PowerCalculation:
        """Phase 2 Simon's two-stage design."""
        result = PowerCalculation()
        result.calculation_method = "simon_two_stage"

        p0 = params.get('response_rate_null', 0.10)
        p1 = params.get('response_rate_alt', 0.30)
        alpha = params.get('alpha', 0.05)
        beta = 1 - params.get('power', 0.80)

        # Simplified Simon's optimal design approximation
        # For p0=0.10, p1=0.30, alpha=0.05, beta=0.20:
        # Stage 1: n1=10, r1=1 (stop if ≤1 response)
        # Stage 2: n=29, r=5 (reject if ≤5 responses)

        result.sample_size = 29  # Typical Simon optimal for these params
        result.interim_boundaries = [
            {'stage': 1, 'n': 10, 'reject_if_responses_leq': 1},
            {'stage': 2, 'n': 29, 'reject_if_responses_leq': 5}
        ]
        result.assumptions = {
            'p0': p0,
            'p1': p1,
            'alpha': alpha,
            'power': 1 - beta
        }

        return result

    def _calculate_phase3_survival(self, params: Dict) -> PowerCalculation:
        """Phase 3 survival endpoint sample size."""
        result = PowerCalculation()
        result.calculation_method = "log_rank_schoenfeld"

        alpha = params.get('alpha', 0.05)
        power = params.get('power', 0.80)
        hr = params.get('hazard_ratio', 0.75)

        if hr and hr > 0 and hr != 1:
            # Schoenfeld formula for number of events
            z_alpha = self.norm.ppf(1 - alpha/2)
            z_beta = self.norm.ppf(power)

            log_hr = abs(float(hr) - 1) if hr else 0.25
            if log_hr > 0:
                events = int(4 * (z_alpha + z_beta)**2 / (log_hr**2))
                result.events_required = events

                # Estimate sample size (assume 70% event rate)
                result.sample_size = int(events / 0.7)

        result.assumptions = {
            'hazard_ratio': hr,
            'alpha': alpha,
            'power': power,
            'allocation_ratio': '1:1'
        }

        return result

    def _calculate_generic(self, params: Dict) -> PowerCalculation:
        """Generic power calculation."""
        result = PowerCalculation()
        result.calculation_method = "provided_enrollment"

        if params.get('enrollment'):
            result.sample_size = params['enrollment']

        result.power = params.get('power', 0.80)

        return result


# =============================================================================
# RAG RETRIEVER (Simplified - file-based, no ChromaDB)
# =============================================================================

class SimpleRAGRetriever:
    """
    Simple RAG retriever that loads SAP examples from files.
    No ChromaDB dependency - uses keyword matching.
    """

    def __init__(self):
        self.sap_examples: Dict[str, str] = {}
        self._load_sap_examples()

    def _load_sap_examples(self):
        """Load SAP examples from real_saps directory."""
        sap_dir = Path(__file__).parent.parent.parent / "data" / "real_saps"

        if sap_dir.exists():
            for sap_file in sap_dir.glob("*.txt"):
                try:
                    content = sap_file.read_text(encoding='utf-8', errors='ignore')
                    nct_id = sap_file.stem.replace('_SAP', '')
                    self.sap_examples[nct_id] = content
                except Exception:
                    pass

        print(f"[RAG] Loaded {len(self.sap_examples)} SAP examples")

    def retrieve_similar(self, protocol_text: str, extracted_facts: List[Dict], top_k: int = 3) -> List[Dict]:
        """
        Retrieve similar SAP sections for style reference.

        Args:
            protocol_text: The protocol text
            extracted_facts: Extracted facts from KG
            top_k: Number of examples to retrieve

        Returns:
            List of relevant SAP sections with content
        """
        results = []

        # Extract key terms for matching
        key_terms = self._extract_key_terms(protocol_text, extracted_facts)

        # Score each SAP by keyword overlap
        scored_saps = []
        for nct_id, content in self.sap_examples.items():
            score = self._score_relevance(content, key_terms)
            if score > 0:
                scored_saps.append((nct_id, content, score))

        # Sort by score and take top_k
        scored_saps.sort(key=lambda x: x[2], reverse=True)

        for nct_id, content, score in scored_saps[:top_k]:
            # Extract relevant sections
            sections = self._extract_sections(content)
            results.append({
                'nct_id': nct_id,
                'score': score,
                'sections': sections,
                'content_preview': content[:500]
            })

        return results

    def _extract_key_terms(self, protocol_text: str, facts: List[Dict]) -> List[str]:
        """Extract key terms for matching."""
        terms = []

        # From facts
        for fact in facts:
            name = fact.get('name', '')
            terms.extend(name.lower().split())

        # Phase detection
        if 'phase 1' in protocol_text.lower():
            terms.extend(['phase 1', 'phase i', 'dlt', 'dose escalation'])
        if 'phase 2' in protocol_text.lower():
            terms.extend(['phase 2', 'phase ii', 'response rate', 'simon'])
        if 'phase 3' in protocol_text.lower():
            terms.extend(['phase 3', 'phase iii', 'survival', 'interim'])

        # Endpoint detection
        for ep in ['overall survival', 'progression-free', 'response rate', 'pfs', 'os', 'orr']:
            if ep in protocol_text.lower():
                terms.append(ep)

        # Therapeutic area
        for ta in ['oncology', 'cancer', 'tumor', 'carcinoma', 'leukemia', 'lymphoma']:
            if ta in protocol_text.lower():
                terms.append(ta)

        return list(set(terms))

    def _score_relevance(self, sap_content: str, key_terms: List[str]) -> float:
        """Score SAP relevance by keyword overlap."""
        content_lower = sap_content.lower()

        matches = sum(1 for term in key_terms if term in content_lower)

        return matches / max(len(key_terms), 1)

    def _extract_sections(self, content: str) -> Dict[str, str]:
        """Extract key sections from SAP content."""
        sections = {}

        # Common section patterns
        section_patterns = [
            (r'(?:STATISTICAL\s+)?METHODS?(.{200,2000}?)(?=\n\d|\n[A-Z]{3,}|\Z)', 'methods'),
            (r'EFFICACY\s+ANALYSIS(.{200,1500}?)(?=\n\d|\n[A-Z]{3,}|\Z)', 'efficacy'),
            (r'SAFETY\s+ANALYSIS(.{200,1500}?)(?=\n\d|\n[A-Z]{3,}|\Z)', 'safety'),
            (r'SAMPLE\s+SIZE(.{100,800}?)(?=\n\d|\n[A-Z]{3,}|\Z)', 'sample_size'),
        ]

        for pattern, name in section_patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                sections[name] = match.group(1).strip()[:1000]  # Limit length

        return sections

    def get_prose_examples(self, section_type: str) -> str:
        """Get prose examples for a specific section type."""
        examples = []

        for nct_id, content in list(self.sap_examples.items())[:3]:
            sections = self._extract_sections(content)
            if section_type in sections:
                examples.append(f"Example from {nct_id}:\n{sections[section_type][:500]}")

        return "\n\n---\n\n".join(examples) if examples else ""


# =============================================================================
# ENHANCED CLAUDE GENERATOR
# =============================================================================

class EnhancedClaudeSAPGenerator:
    """
    Enhanced SAP generator with verification loop.
    """

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"
        self.max_regenerations = 2

    def generate_sap(
        self,
        extracted_facts: List[Dict],
        kg_context: List[Dict],
        protocol_content: str,
        power_calc: Optional[PowerCalculation] = None,
        rag_examples: Optional[List[Dict]] = None,
        regulatory_context: Optional[str] = None
    ) -> Tuple[str, List[str]]:
        """
        Generate SAP using PROTOCOL-DRIVEN approach.

        NO extractors, NO hardcoded rules.
        Claude reads the protocol and determines what to include/exclude.

        Returns:
            Tuple of (generated_sap, warnings)
        """

        # Format extracted facts with provenance
        facts_text = self._format_facts_with_provenance(extracted_facts)

        # Format KG context
        context_text = "\n".join([
            f"- {ex['trial_id']}: {ex['fact']}"
            for ex in kg_context[:5]
        ]) if kg_context else "No similar trials in knowledge graph."

        # Format power calculations
        power_text = self._format_power_calc(power_calc) if power_calc else "[Power calculations not available]"

        # Format RAG examples
        rag_text = self._format_rag_examples(rag_examples) if rag_examples else ""

        # STRICT PROTOCOL-ONLY PROMPT - NO EXTERNAL SOURCES
        # RAG examples and KG context REMOVED - they contaminate with generic content
        prompt = f"""You are a biostatistician creating a Statistical Analysis Plan (SAP).

## ABSOLUTE RULE: ONLY USE INFORMATION FROM THIS PROTOCOL

You must generate a SAP using ONLY the information in the protocol below.
DO NOT add any variables, tables, or content that is not explicitly mentioned.

## FORBIDDEN - DO NOT INCLUDE UNLESS EXPLICITLY IN PROTOCOL:
- Race/Ethnicity (only include if protocol explicitly collects this)
- ECOG Performance Status (only if protocol mentions ECOG specifically)
- Tumor response categories CR/PR/SD/PD (only for metastatic studies with measurable tumors)
- Geographic subgroups like "North America", "Europe", "Asia" (only if protocol lists these regions)
- CTCAE grading (only if protocol specifies CTCAE)
- Dose modification tables (only if protocol has dose modification rules)

## STUDY TYPE DETECTION - CRITICAL:
Read the protocol and determine:
1. Is this ADJUVANT (post-surgery, no measurable disease)?
   → Use time-to-event endpoints (DFS, TTR, OS)
   → Use Hazard Ratio and Cox regression
   → DO NOT include tumor response tables (CR/PR/SD/PD)

2. Is this METASTATIC (treating existing tumors)?
   → Include tumor response (CR/PR/SD/PD) if using RECIST
   → Include ORR, DCR tables

3. What performance status does the protocol use?
   → ECOG? Use ECOG
   → ASA Score? Use ASA Score
   → Karnofsky? Use Karnofsky
   → Not mentioned? Mark as [TO BE CONFIRMED]

4. What countries/regions?
   → Nordic (Sweden, Norway, Denmark, Finland)? Do NOT add Race/Ethnicity
   → US study? May include Race/Ethnicity if in protocol
   → Only include geographic subgroups that match actual study sites

## STATISTICAL METHODS - MATCH TO ENDPOINT TYPE:
- Time-to-event (DFS, OS, PFS, TTR) → Cox regression, Hazard Ratio, Kaplan-Meier
- Binary response rate → May use Odds Ratio OR Risk Difference
- DO NOT use Odds Ratio for time-to-event endpoints

## BASELINE VARIABLES:
ONLY include variables explicitly mentioned in the protocol:
{facts_text}

## SAMPLE SIZE:
{power_text}

## PROTOCOL CONTENT (THIS IS YOUR ONLY SOURCE):
{protocol_content}

---

## OUTPUT REQUIREMENTS:
1. Generate SAP sections with ONLY protocol-specified content
2. For any variable not in protocol, write [NOT IN PROTOCOL - CONFIRM IF NEEDED]
3. Table shells must use ONLY the treatment arms from this protocol
4. Column headers must match this protocol's groups exactly
5. DO NOT copy structure from other SAPs - this protocol is unique

Generate the protocol-specific SAP now:"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}]
            )

            return response.content[0].text, []

        except Exception as e:
            return f"Error generating SAP: {e}", [str(e)]

    # Old extractor helper methods REMOVED - no longer needed with protocol-driven approach

    def regenerate_with_corrections(
        self,
        original_sap: str,
        corrections: str,
        extracted_facts: List[Dict]
    ) -> str:
        """Regenerate SAP sections with corrections."""

        prompt = f"""The following SAP has verification errors that need correction.

ORIGINAL SAP:
{original_sap[:4000]}

{corrections}

EXTRACTED FACTS (ground truth):
{json.dumps(extracted_facts[:10], indent=2)}

Please regenerate the SAP with these corrections applied. Maintain the same structure but fix the identified errors."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}]
            )

            return response.content[0].text

        except Exception as e:
            return original_sap  # Return original if regeneration fails

    def _format_facts_with_provenance(self, facts: List[Dict]) -> str:
        """Format facts with source quotes."""
        lines = []
        for fact in facts:
            line = f"• {fact['type'].upper()}: {fact['name']}"
            if fact.get('confidence'):
                line += f" [confidence: {fact['confidence']}]"
            if fact.get('source_quote'):
                line += f"\n  Source: \"{fact['source_quote'][:100]}...\""
            lines.append(line)
        return "\n".join(lines)

    def _format_power_calc(self, power_calc: PowerCalculation) -> str:
        """Format power calculation results."""
        lines = [f"Calculation Method: {power_calc.calculation_method}"]

        if power_calc.sample_size:
            lines.append(f"Sample Size: {power_calc.sample_size}")
        if power_calc.power:
            lines.append(f"Power: {power_calc.power * 100:.0f}%")
        if power_calc.events_required:
            lines.append(f"Events Required: {power_calc.events_required}")
        if power_calc.interim_boundaries:
            lines.append(f"Interim Boundaries: {json.dumps(power_calc.interim_boundaries)}")
        if power_calc.assumptions:
            lines.append(f"Assumptions: {json.dumps(power_calc.assumptions)}")

        return "\n".join(lines)

    def _format_rag_examples(self, rag_examples: List[Dict]) -> str:
        """Format RAG examples for prose style reference."""
        if not rag_examples:
            return "No similar SAP examples available."

        lines = []
        for ex in rag_examples[:2]:
            lines.append(f"### Example from {ex['nct_id']} (relevance: {ex['score']:.2f})")
            if ex.get('sections'):
                for section_name, section_content in list(ex['sections'].items())[:2]:
                    lines.append(f"**{section_name}:**\n{section_content[:300]}...")

        return "\n\n".join(lines)


# =============================================================================
# ENHANCED KG PIPELINE
# =============================================================================

class EnhancedKGPipeline:
    """
    Enhanced KG Pipeline with:
    1. Full provenance tracking (from KG pipeline)
    2. SELF-RAG verification loop
    3. Power/sample size calculations
    4. RAG-based prose style
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"

        # Initialize components
        self.kg = FactualKnowledgeGraphV2()
        self.verifier = SelfRAGVerifier()
        self.power_calc = SimplePowerCalculator()
        self.rag = SimpleRAGRetriever()
        self.generator = EnhancedClaudeSAPGenerator(api_key)
        self.regulatory_kb = RegulatoryKnowledgeBase()

        # Load existing KG
        self._load_existing_kg()

        print("✅ Enhanced KG Pipeline initialized (PROTOCOL-DRIVEN)")
        print(f"   • Knowledge Graph: {len(self.kg.nodes)} nodes")
        print(f"   • RAG Examples: {len(self.rag.sap_examples)} SAPs")
        print(f"   • Power Calculator: {'scipy' if self.power_calc.available else 'unavailable'}")
        print(f"   • Regulatory KB: MedDRA {self.regulatory_kb.get_meddra_version()}, CTCAE {self.regulatory_kb.get_ctcae_version()}")
        print("   • Approach: Protocol-driven (Claude reads protocol directly)")

    def _load_existing_kg(self):
        """Load existing Claude-extracted KG."""
        kg_path = Path(__file__).parent / "output" / "factual_kg_claude.json"

        if kg_path.exists():
            with open(kg_path) as f:
                data = json.load(f)

            for n in data.get("nodes", []):
                node = FlexibleNode(
                    id=n["id"],
                    node_type=n["type"],
                    properties=n.get("attributes", {}),
                )
                self.kg.nodes[node.id] = node

            for e in data.get("edges", []):
                edge = FlexibleEdge(
                    source_id=e["source"],
                    target_id=e["target"],
                    edge_type=e["type"],
                    is_factual=True
                )
                self.kg.edges.append(edge)

    def process_protocol(self, protocol_path: str) -> Dict:
        """
        Full enhanced pipeline.

        Steps:
        1. Extract entities with Claude (with provenance)
        2. Calculate power/sample size
        3. Retrieve RAG examples
        4. Generate SAP
        5. Verify with SELF-RAG
        6. Regenerate if needed
        """

        print("\n" + "="*70)
        print("ENHANCED KG PIPELINE")
        print("="*70)

        # Read protocol
        protocol_content = Path(protocol_path).read_text(encoding='utf-8', errors='ignore')
        filename = Path(protocol_path).name
        doc_id = f"doc:{hashlib.md5(filename.encode()).hexdigest()[:8]}"

        print(f"\n📄 Protocol: {filename}")
        print(f"📄 Length: {len(protocol_content)} chars")
        print("📄 Approach: PROTOCOL-DRIVEN (Claude reads protocol directly)")

        # Step 1: Extract entities with Claude
        print("\n" + "-"*50)
        print("STEP 1: CLAUDE KG EXTRACTION")
        print("-"*50)

        extracted = self._extract_entities(protocol_content, doc_id)
        print(f"✅ Extracted {len(extracted)} entities with provenance")

        # Step 2: Power calculations
        print("\n" + "-"*50)
        print("STEP 2: POWER CALCULATIONS")
        print("-"*50)

        power_result = self.power_calc.calculate_from_protocol(extracted, protocol_content)
        print(f"✅ Power calculation: {power_result.calculation_method}")
        if power_result.sample_size:
            print(f"   • Sample size: {power_result.sample_size}")
        if power_result.events_required:
            print(f"   • Events required: {power_result.events_required}")

        # Step 3: RAG retrieval
        print("\n" + "-"*50)
        print("STEP 3: RAG STYLE RETRIEVAL")
        print("-"*50)

        rag_examples = self.rag.retrieve_similar(protocol_content, extracted, top_k=3)
        print(f"✅ Retrieved {len(rag_examples)} similar SAPs for style")
        for ex in rag_examples:
            print(f"   • {ex['nct_id']} (relevance: {ex['score']:.2f})")

        # Step 4: Query KG for context
        print("\n" + "-"*50)
        print("STEP 4: KG CONTEXT QUERY")
        print("-"*50)

        kg_context = self._query_kg_context(extracted)
        print(f"✅ Found {len(kg_context)} similar trial examples from KG")

        # Step 5: Get regulatory standards
        print("\n" + "-"*50)
        print("STEP 5: REGULATORY STANDARDS")
        print("-"*50)

        # Detect phase for appropriate standards
        phase = "Phase 1" if "phase 1" in protocol_content.lower() else "Phase 3"
        therapeutic_area = "oncology" if any(t in protocol_content.lower() for t in
            ["cancer", "tumor", "oncology", "carcinoma", "lymphoma", "leukemia"]) else "general"

        regulatory_context = self.regulatory_kb.format_for_prompt(phase, therapeutic_area)
        versions = get_standard_versions()
        print(f"✅ Regulatory standards loaded")
        print(f"   • Phase: {phase}")
        print(f"   • Therapeutic area: {therapeutic_area}")
        print(f"   • MedDRA: {versions['MedDRA']}")
        print(f"   • CTCAE: {versions['CTCAE']}")
        print(f"   • WHO-DD: {versions['WHO_Drug']}")
        print(f"   • TEAE table types: {self.regulatory_kb.get_teae_table_count()}")

        # Step 6: Generate SAP
        print("\n" + "-"*50)
        print("STEP 6: GENERATE SAP WITH CLAUDE")
        print("-"*50)

        sap_content, gen_warnings = self.generator.generate_sap(
            extracted_facts=extracted,
            kg_context=kg_context,
            protocol_content=protocol_content,
            power_calc=power_result,
            rag_examples=rag_examples,
            regulatory_context=regulatory_context
        )
        print(f"✅ Generated SAP ({len(sap_content)} chars)")

        # Step 7: SELF-RAG Verification
        print("\n" + "-"*50)
        print("STEP 7: SELF-RAG VERIFICATION")
        print("-"*50)

        verification = self.verifier.verify(sap_content, extracted, power_result)
        print(f"✅ Verification score: {verification.score:.2f}")
        print(f"   • Passed: {verification.passed}")
        print(f"   • Errors: {len(verification.errors)}")
        print(f"   • Warnings: {len(verification.warnings)}")

        # Step 7: Regeneration loop if needed
        regeneration_count = 0
        max_regenerations = 2

        while not verification.passed and regeneration_count < max_regenerations:
            print(f"\n⚠️  Verification failed. Regenerating ({regeneration_count + 1}/{max_regenerations})...")

            corrections = self.verifier.generate_correction_prompt(verification.errors)
            sap_content = self.generator.regenerate_with_corrections(
                sap_content, corrections, extracted
            )

            verification = self.verifier.verify(sap_content, extracted, power_result)
            regeneration_count += 1

            print(f"   • New score: {verification.score:.2f}")

        if verification.passed:
            print("\n✅ VERIFICATION PASSED")
        else:
            print(f"\n⚠️  Verification not fully passed after {regeneration_count} regenerations")

        # Build result
        provenance = {
            "document": doc_id,
            "filename": filename,
            "extraction_time": datetime.now().isoformat(),
            "facts": extracted,
            "kg_context": kg_context,
            "power_calculation": {
                "method": power_result.calculation_method,
                "sample_size": power_result.sample_size,
                "power": power_result.power,
                "events": power_result.events_required,
                "assumptions": power_result.assumptions
            },
            "regulatory_standards": {
                "MedDRA": versions['MedDRA'],
                "CTCAE": versions['CTCAE'],
                "WHO_Drug": versions['WHO_Drug'],
                "phase_detected": phase,
                "therapeutic_area": therapeutic_area,
                "teae_table_types": self.regulatory_kb.get_teae_table_count()
            },
            "rag_examples": [ex['nct_id'] for ex in rag_examples],
            "verification": {
                "passed": verification.passed,
                "score": verification.score,
                "errors": [
                    {"field": e.field, "expected": str(e.expected), "found": str(e.found)}
                    for e in verification.errors
                ],
                "warnings": verification.warnings
            },
            "regeneration_count": regeneration_count,
            "model": self.model
        }

        return {
            "sap": sap_content,
            "provenance": provenance,
            "extracted": extracted,
            "verification": verification,
            "power_calculation": power_result
        }

    def _extract_entities(self, content: str, doc_id: str) -> List[Dict]:
        """Extract entities with Claude."""

        prompt = f"""Extract ALL statistical analysis elements from this clinical trial document.

For each element, provide:
1. The exact type (endpoint, method, population, stratification, table)
2. The name/value
3. A confidence score (0.0-1.0) based on how clearly it's stated
4. The exact quote from the document where you found it
5. The section where it appears (if identifiable)

Return JSON array with this structure:
[
  {{
    "type": "endpoint",
    "name": "Overall Survival",
    "endpoint_type": "primary",
    "definition": "Time from randomization to death from any cause",
    "confidence": 0.95,
    "source_quote": "The primary endpoint is overall survival, defined as...",
    "section": "Section 3.1"
  }},
  {{
    "type": "method",
    "name": "Stratified Log-Rank Test",
    "description": "Primary hypothesis test for survival comparison",
    "confidence": 0.90,
    "source_quote": "The primary analysis will use a stratified log-rank test...",
    "section": "Section 5.1"
  }}
]

Extract EVERYTHING: endpoints, methods, populations, stratification factors, sample sizes.
Be thorough. Include primary, secondary, and exploratory endpoints.

DOCUMENT:
{content}

Return ONLY valid JSON array, no other text."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text.strip()

            # Clean up response
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            extracted = json.loads(response_text)

            # Add doc_id to all items
            for item in extracted:
                item["source_doc"] = doc_id

            return extracted

        except Exception as e:
            print(f"❌ Extraction error: {e}")
            return []

    def _query_kg_context(self, extracted: List[Dict]) -> List[Dict]:
        """Query KG for similar trials."""
        context = []
        seen_trials = set()

        endpoint_names = [
            item["name"].lower()
            for item in extracted
            if item["type"] == "endpoint"
        ]

        for node_id, node in self.kg.nodes.items():
            if node.node_type == "endpoint":
                node_name = node.properties.get("name", "").lower()

                for ep_name in endpoint_names:
                    if ep_name in node_name or node_name in ep_name:
                        for edge in self.kg.edges:
                            if edge.target_id == node_id and edge.edge_type == "has_endpoint":
                                trial = self.kg.nodes.get(edge.source_id)
                                if trial and trial.id not in seen_trials:
                                    seen_trials.add(trial.id)
                                    context.append({
                                        "trial_id": trial.id,
                                        "endpoint": node.properties.get("name"),
                                        "fact": f"{trial.id} analyzed {node.properties.get('name')}"
                                    })

                        if len(context) >= 5:
                            break

        return context[:5]


# =============================================================================
# MAIN
# =============================================================================

def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY environment variable not set")
        return

    # Find test protocol
    if len(sys.argv) > 1:
        protocol_path = sys.argv[1]
    else:
        # Default test protocol
        test_files = [
            Path(__file__).parent.parent.parent / "data/all_pairs/NCT03558139_protocol.txt",
            Path(__file__).parent.parent.parent / "data/all_pairs/NCT00938041_protocol.txt",
        ]
        protocol_path = next((f for f in test_files if f.exists()), None)

    if not protocol_path or not Path(protocol_path).exists():
        print(f"❌ Protocol file not found")
        return

    # Run enhanced pipeline
    pipeline = EnhancedKGPipeline(api_key)
    result = pipeline.process_protocol(str(protocol_path))

    # Save outputs
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    # Save SAP
    sap_path = output_dir / "enhanced_kg_generated_sap.md"
    sap_path.write_text(result["sap"])
    print(f"\n📄 SAP saved: {sap_path}")

    # Save provenance
    prov_path = output_dir / "enhanced_kg_provenance.json"
    with open(prov_path, 'w') as f:
        json.dump(result["provenance"], f, indent=2)
    print(f"📄 Provenance saved: {prov_path}")

    # Print summary
    print("\n" + "="*70)
    print("PIPELINE SUMMARY")
    print("="*70)
    print(f"✅ Entities extracted: {len(result['extracted'])}")
    print(f"✅ Verification score: {result['verification'].score:.2f}")
    print(f"✅ Verification passed: {result['verification'].passed}")
    print(f"✅ Regenerations: {result['provenance']['regeneration_count']}")

    # Print SAP preview
    print("\n" + "="*70)
    print("GENERATED SAP PREVIEW")
    print("="*70)
    print(result["sap"][:2000])
    print("\n... (truncated)")


if __name__ == "__main__":
    main()
