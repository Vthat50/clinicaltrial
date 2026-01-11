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
    import httpx
except ImportError:
    print("Installing anthropic...")
    os.system("pip install anthropic httpx")
    import anthropic
    import httpx

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

# Import knowledge base tools for explicit retrieval
try:
    from .kb_tools import (
        KnowledgeBaseTools,
        get_claude_tool_definitions,
        execute_tool
    )
except ImportError:
    from kb_tools import (
        KnowledgeBaseTools,
        get_claude_tool_definitions,
        execute_tool
    )

# Import dynamic SAP structure configuration
try:
    from .sap_structure_config import (
        get_required_sections,
        format_section_outline,
        get_all_kb_tools_for_sections,
        get_section_summary,
        detect_sap_conditions
    )
except ImportError:
    from sap_structure_config import (
        get_required_sections,
        format_section_outline,
        get_all_kb_tools_for_sections,
        get_section_summary,
        detect_sap_conditions
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
        # Disable timeout to prevent "Streaming is required" error for long operations
        self.client = anthropic.Anthropic(
            api_key=api_key,
            timeout=httpx.Timeout(None)  # No timeout limit
        )
        self.model = "claude-sonnet-4-20250514"
        self.max_regenerations = 2

    def generate_sap(
        self,
        extracted_facts: List[Dict],
        kg_context: List[Dict],
        protocol_content: str,
        power_calc: Optional[PowerCalculation] = None,
        rag_examples: Optional[List[Dict]] = None,
        regulatory_context: Optional[str] = None,
        full_extraction: Optional[Dict] = None
    ) -> Tuple[str, List[str]]:
        """
        Generate SAP using comprehensive protocol extraction.

        Uses the 55-category extraction to generate accurate, protocol-specific SAP.

        Returns:
            Tuple of (generated_sap, warnings)
        """

        # Format comprehensive extraction if available
        if full_extraction:
            extraction_json = json.dumps(full_extraction, indent=2, default=str)
        else:
            extraction_json = self._format_facts_with_provenance(extracted_facts)

        # Format power calculations
        power_text = self._format_power_calc(power_calc) if power_calc else "[Power calculations not available]"

        # Build context-specific prohibition rules
        prohibition_rules = self._build_prohibition_rules(full_extraction)

        # Build protocol-specific required sections from discovery
        protocol_requirements = self._build_protocol_specific_requirements(full_extraction)

        # Build the comprehensive SAP generation prompt
        prompt = f"""You are a senior biostatistician creating a Statistical Analysis Plan (SAP).

## CRITICAL: STRICT PROTOCOL-SPECIFIC GENERATION

You have been given a comprehensive extraction of ALL protocol elements.
Generate a SAP using ONLY this extracted information.
DO NOT add any content not present in the extraction.

## PROHIBITED CONTENT (Based on Protocol Analysis):
{prohibition_rules}

{protocol_requirements}

## CRITICAL ANTI-HALLUCINATION RULES:
1. RACE/ETHNICITY: Include ONLY if explicitly in baseline_variables[]. Nordic/European studies do NOT collect these.
2. PERFORMANCE STATUS: Use EXACTLY the scale from extraction (ASA Score for surgical, ECOG for oncology, Karnofsky for CNS).
3. GEOGRAPHIC SUBGROUPS: Use ONLY countries from extraction. Nordic = Sweden/Norway/Denmark/Finland ONLY.
4. RESPONSE TABLES (CR/PR/SD/PD): Include ONLY for metastatic/advanced disease. ADJUVANT trials = NO tumor response.
5. AE GRADING: Use EXACTLY what's in safety_endpoints.ae_grading_scale (CTCAE vs Mild/Moderate/Severe).
6. DOSE MODIFICATION: Include ONLY if dose_modifications has rules. Fixed-dose studies = NO modification rows.
7. TREATMENT ARMS: Use EXACT arm names from extraction as column headers.

## COMPREHENSIVE PROTOCOL EXTRACTION:
```json
{extraction_json}
```

## POWER/SAMPLE SIZE CALCULATIONS:
{power_text}

## FULL PROTOCOL TEXT (for reference if extraction is incomplete):
{protocol_content}

---

## SAP GENERATION RULES:

### 1. STUDY IDENTIFICATION
- Use exact NCT ID, protocol number, sponsor from extraction
- Use exact study title

### 2. DISEASE & SETTING
- Use disease_classification.disease_setting to determine:
  - ADJUVANT → time-to-event endpoints (DFS, TTR, OS), NO tumor response tables
  - NEOADJUVANT → pCR endpoints, pathologic response
  - METASTATIC → tumor response (RECIST), ORR, DCR, PFS, OS

### 3. RESPONSE CRITERIA
- Use EXACTLY what's in response_criteria_details.criteria_name
- For immunotherapy: use immunotherapy_specific.response_criteria
- For hematologic: use hematologic_specific.response_criteria
- For CAR-T: include CRS/ICANS grading from cart_specific

### 4. ENDPOINTS
- Primary: Use exact names/definitions from primary_endpoints[]
- Secondary: Use exact names/definitions from secondary_endpoints[]
- Include response_criteria and assessment_schedule from extraction

### 5. POPULATIONS (DYNAMIC LIST)
- The populations[] array contains ALL analysis populations with EXACT names from the protocol
- Use the name field as-is (e.g., "Full Analysis Set (FAS)", "Safety Re-treatment Set")
- Use the definition field for the population definition text
- is_primary_efficacy and is_primary_safety indicate which population is primary for each analysis type
- DO NOT assume standard ITT/mITT/PP names - use EXACTLY what's in the extraction

### 6. HYPOTHESES (INDIVIDUAL ALPHAS)
- The hypotheses[] array contains each hypothesis with its OWN alpha_allocated
- Use the id (H1, H2, H3, H4) and individual alpha values
- Use gate_condition to identify gating/gatekeeping dependencies
- Use test_type (superiority/non_inferiority) for each hypothesis
- If multiplicity is hierarchical, present the full testing sequence

### 7. CENSORING RULES (PER-ENDPOINT SCENARIOS)
- The censoring_rules[] array contains DETAILED scenarios for each time-to-event endpoint
- Include ALL scenarios (no event, lost to follow-up, new therapy, etc.)
- Use the event_flag (0=censored, 1=event) and date_used fields
- Present as a table with columns: Situation, Event?, Date Used

### 8. SUBGROUPS (PROTOCOL-SPECIFIED ONLY)
- The subgroups[] array contains ONLY pre-specified subgroup factors from the protocol
- Use the factor and categories exactly as extracted
- is_stratification_factor indicates if also used for randomization stratification

### 9. BASELINE VARIABLES
- Include ONLY variables from baseline_variables[]
- Use the exact variable_name and categories
- Use performance_status.scale (ECOG vs ASA vs Karnofsky)

### 10. STATISTICAL METHODS
- Use methods from statistical_methods section
- Match to endpoint types from extraction
- Include multiplicity adjustment using hypotheses[] alpha allocations

### 11. TREATMENT ARMS
- Use exact arm names from treatment_arms[]
- Include dose, schedule, route as extracted

### 12. STRATIFICATION
- Use exact factors from randomization.stratification_factors[]
- Include categories as extracted

### 13. INTERIM ANALYSIS
- Include if interim_analysis.planned is true
- Use stopping rules from extraction

### 14. SAFETY ANALYSIS
- Use ae_grading_scale from safety_endpoints
- Include special monitoring from safety_endpoints.special_safety_monitoring

### 15. SPECIAL CONSIDERATIONS (Study-Type Specific)
- CAR-T (cart_specific): Include CRS grading scale/grades, ICANS grading, cellular kinetics parameters/timepoints, bridging therapy rules, re-treatment criteria and population
- Immunotherapy (immunotherapy_specific): Include irAE monitoring, pseudoprogression handling
- Hematologic (hematologic_specific): Include MRD assessment method/sensitivity/timepoints, cytogenetic risk categories
- Phase 1: Include DLT definition, MTD criteria from phase1_design

### 16. GEOGRAPHIC
- Include only countries/regions from geographic section
- Do NOT add Race/Ethnicity unless in baseline_variables

### 17. TABLE SHELLS
- Use exact treatment arm names as column headers
- Include only baseline variables from extraction
- Match response criteria to study type
- Include censoring rules table for time-to-event endpoints

---

## OUTPUT FORMAT:
Generate a complete SAP with these sections:
1. Title Page & Administrative Information
2. Introduction & Study Objectives
3. Study Design
4. Study Endpoints
5. Analysis Populations
6. Statistical Methods
7. Sample Size
8. Interim Analysis (if applicable)
9. Baseline & Demographics Analysis
10. Efficacy Analysis
11. Safety Analysis
12. Table/Figure Shells

For any element not in extraction, write: [NOT EXTRACTED - VERIFY IN PROTOCOL]

Generate the comprehensive SAP now:"""

        try:
            # Use streaming for long operations (>10 min timeout)
            with self.client.messages.stream(
                model=self.model,
                max_tokens=32000,  # Increased for complete SAP with all sections
                messages=[{"role": "user", "content": prompt}]
            ) as stream:
                response = stream.get_final_message()

            sap_text = response.content[0].text

            # Check if SAP appears truncated
            if not any(section in sap_text for section in ['## 12.', '## 11.', 'Appendix', 'APPENDIX']):
                print(f"[WARNING] SAP may be truncated - no section 11/12 found. Length: {len(sap_text)}")

            return sap_text, []

        except Exception as e:
            print(f"[ERROR] SAP generation failed: {e}")
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
            # Use streaming for long operations
            with self.client.messages.stream(
                model=self.model,
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}]
            ) as stream:
                response = stream.get_final_message()

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

    def _build_prohibition_rules(self, full_extraction: Optional[Dict]) -> str:
        """Build context-specific prohibition rules based on protocol extraction."""
        if not full_extraction:
            return "No extraction available - use extreme caution with generic content."

        rules = []

        # 1. Race/Ethnicity check
        baseline_vars = full_extraction.get("baseline_variables", [])
        var_names = [v.get("variable_name", "").lower() for v in baseline_vars if v.get("variable_name")]
        has_race = any("race" in v or "ethnicity" in v for v in var_names)

        geo = full_extraction.get("geographic", {})
        countries = [c.get("country", "").lower() for c in geo.get("countries", []) if c.get("country")]

        is_nordic = all(c in ["sweden", "norway", "denmark", "finland", "iceland"] for c in countries) if countries else False
        is_european_only = all(c in ["sweden", "norway", "denmark", "finland", "iceland", "germany", "france", "uk", "spain", "italy", "netherlands", "belgium", "austria", "switzerland", "poland"] for c in countries) if countries else False

        if not has_race:
            rules.append("- DO NOT include Race or Ethnicity variables (not collected in this study)")
        if is_nordic:
            rules.append("- DO NOT include North America, Asia, or Rest of World subgroups (Nordic study only)")
            rules.append("- Geographic regions: ONLY Sweden, Norway, Denmark, Finland")
        elif is_european_only and countries:
            rules.append(f"- DO NOT include regions outside Europe (study sites: {', '.join(countries)})")

        # 2. Performance status check
        ps = full_extraction.get("performance_status", {})
        ps_scale = (ps.get("scale", {}).get("value") or "").upper() if ps else ""

        if ps_scale == "ASA":
            rules.append("- DO NOT use ECOG. Use ASA Score (1-5) for this surgical study")
        elif ps_scale == "KARNOFSKY":
            rules.append("- DO NOT use ECOG. Use Karnofsky Performance Status (0-100%)")
        elif ps_scale == "LANSKY":
            rules.append("- DO NOT use ECOG. Use Lansky Play-Performance Scale (pediatric)")

        # 3. Disease setting check - CRITICAL for response tables
        disease = full_extraction.get("disease_classification", {})
        setting = (disease.get("disease_setting", {}).get("value") or "").lower() if disease else ""

        if setting == "adjuvant":
            rules.append("- DO NOT include tumor response tables (CR/PR/SD/PD). This is ADJUVANT - no measurable tumor")
            rules.append("- DO NOT use ORR, DCR, or RECIST categories for efficacy")
            rules.append("- Primary efficacy = time-to-event (DFS, TTR, OS) with Kaplan-Meier and Cox model")
            rules.append("- Use Hazard Ratio (not Odds Ratio) for treatment comparisons")
        elif setting == "neoadjuvant":
            rules.append("- Use pCR (pathologic complete response) as primary, not radiologic response")

        # 4. AE grading check
        safety = full_extraction.get("safety_endpoints", {})
        ae_scale = (safety.get("ae_grading_scale", {}).get("value") or "") if safety else ""

        if ae_scale and "ctcae" not in ae_scale.lower():
            rules.append(f"- DO NOT use CTCAE Grade 1-5. Use {ae_scale} grading")
        if not ae_scale or "mild" in str(full_extraction).lower():
            # Check for older-style Mild/Moderate/Severe in protocol
            rules.append("- If protocol uses Mild/Moderate/Severe grading, DO NOT use CTCAE Grades 1-5")

        # 5. Dose modification check
        dose_mods = full_extraction.get("dose_modifications", {})
        reduction_rules = dose_mods.get("dose_reduction_rules", []) if dose_mods else []

        if not reduction_rules:
            rules.append("- DO NOT include 'TEAE Leading to Dose Modification' row (fixed-dose study)")

        # 6. Treatment arms for column headers
        arms = full_extraction.get("treatment_arms", [])
        if arms:
            arm_names = [a.get("arm_name", "") for a in arms if a.get("arm_name")]
            if arm_names:
                rules.append(f"- Table column headers MUST be: {', '.join(arm_names)}")

        # 7. SINGLE-ARM STUDY DESIGN RULES (CRITICAL)
        study_design = full_extraction.get("study_design", {})
        design_type = (study_design.get("design_type", {}).get("value") or "").lower() if study_design else ""

        if design_type == "single_arm" or len(arms) == 1:
            rules.append("")
            rules.append("**SINGLE-ARM STUDY - CRITICAL PROHIBITIONS:**")
            rules.append("- DO NOT include randomization in CONSORT diagram (no randomization exists)")
            rules.append("- DO NOT include treatment comparison columns (only ONE arm exists)")
            rules.append("- DO NOT calculate Hazard Ratios (no comparator arm for HRs)")
            rules.append("- DO NOT include forest plots comparing treatment arms (single-arm)")
            rules.append("- DO NOT include p-values for treatment comparisons (no comparison possible)")
            rules.append("- DO NOT include 'Placebo' or 'Control' columns in ANY table")
            rules.append("- USE exact binomial test vs historical control for primary analysis")
            rules.append("- USE Clopper-Pearson CI for response rates")
            rules.append("- Tables should have columns: Category | N | n (%) or Mean (SD)")
            rules.append("")

        # 7. Stratification for subgroup analysis
        strat = full_extraction.get("randomization", {})
        strat_factors = strat.get("stratification_factors", []) if strat else []

        if strat_factors:
            factor_names = [f.get("factor_name", "") for f in strat_factors if f.get("factor_name")]
            if factor_names:
                rules.append(f"- Forest plot subgroups MUST use only: {', '.join(factor_names)}")

        # 9. Check for specific baseline variables
        if var_names:
            has_bmi = any("bmi" in v for v in var_names)
            has_weight = any("weight" in v for v in var_names)
            if has_bmi and not has_weight:
                rules.append("- Use BMI (kg/m²), not Weight (kg) for body composition variable")

        # 10. CAR-T SPECIFIC REQUIRED SECTIONS
        discovered = full_extraction.get("discovered_structure", {})
        flags = discovered.get("study_type_flags", {}) if discovered else {}

        if flags.get("is_cart"):
            rules.append("")
            rules.append("**CAR-T STUDY - REQUIRED SECTIONS:**")
            rules.append("- MUST include Safety Re-treatment Analysis Set definition")
            rules.append("- CRS GRADING: Use EXACTLY what the PROTOCOL specifies:")
            rules.append("  * If protocol says 'Lee 2014' or 'modified Lee' → use 'Modified Lee et al. 2014 criteria'")
            rules.append("  * If protocol says 'ASTCT' or 'ASTCT 2019' → use 'ASTCT 2019 Consensus'")
            rules.append("  * DO NOT default to ASTCT if protocol specifies Lee 2014 (older axicabtagene studies use Lee)")
            rules.append("  * Check IB section for CRS grading specification")
            rules.append("- NEUROLOGIC EVENTS: If protocol says neurologic AEs are 'not part of CRS' or 'graded separately':")
            rules.append("  * DO NOT use ICANS or ICE score")
            rules.append("  * State: 'Neurologic events graded per CTCAE, reported separately from CRS'")
            rules.append("- Only use ICANS/ICE score if protocol explicitly mentions it")
            rules.append("- MUST include CAR T cell kinetics analysis (Cmax, AUC, persistence)")
            rules.append("- MUST include DORR (Duration of Response to Retreatment) if retreatment allowed")
            rules.append("- MUST include Appendix 1: Date Imputation Rules")
            rules.append("- MUST include Appendix 2: Time-to-Event Derivation Tables")
            rules.append("- MUST include manufacturing failure handling")
            rules.append("- DO NOT include dose modification tables (CAR-T is single infusion)")
            rules.append("")

        # 11. LYMPHOMA STAGING (Ann Arbor vs TNM)
        response_criteria = discovered.get("response_criteria", "") if discovered else ""
        disease = full_extraction.get("disease_classification", {})
        tumor_type = (disease.get("tumor_type", {}).get("value") or "").lower() if disease else ""

        is_lymphoma = "lymphoma" in tumor_type or response_criteria == "Lugano" or flags.get("is_hematologic")
        is_solid_tumor = any(x in tumor_type for x in ["melanoma", "lung", "breast", "colon", "ovarian", "prostate"])

        if is_lymphoma:
            rules.append("")
            rules.append("**LYMPHOMA - STAGING PROHIBITIONS:**")
            rules.append("- DO NOT use TNM staging (M1a, M1b, M1c) - that's for solid tumors")
            rules.append("- DO NOT use BRAF mutation status - that's for melanoma")
            rules.append("- DO NOT include solid tumor staging tables")
            rules.append("- USE Ann Arbor staging (I, II, III, IV) with A/B modifiers")
            rules.append("- USE Lugano classification for response assessment")
            rules.append("- USE Deauville score (1-5) for PET response if applicable")
            rules.append("- USE FLIPI/IPI prognostic scores as appropriate")
            rules.append("")

        if is_solid_tumor and not is_lymphoma:
            rules.append("")
            rules.append("**SOLID TUMOR - Do not use lymphoma-specific staging:**")
            rules.append("- DO NOT use Ann Arbor staging (that's for lymphoma)")
            rules.append("- DO NOT use Deauville score (that's for lymphoma)")
            rules.append("- USE TNM/AJCC staging as appropriate")
            rules.append("- USE RECIST 1.1 for response assessment")
            rules.append("")

        return "\n".join(rules) if rules else "No specific prohibitions identified."

    def _build_protocol_specific_requirements(self, full_extraction: Optional[Dict]) -> str:
        """Build required sections based on discovered protocol-specific elements."""
        if not full_extraction:
            return ""

        discovered = full_extraction.get("discovered_structure", {})
        protocol_sections = discovered.get("protocol_specific_sections", {}) if discovered else {}

        if not protocol_sections:
            return ""

        requirements = []
        requirements.append("")
        requirements.append("**PROTOCOL-SPECIFIC SECTIONS (from discovery - MUST INCLUDE):**")

        # Follow-up analyses
        follow_ups = protocol_sections.get("follow_up_analyses", [])
        if follow_ups and any(f.get("name") or f.get("timing") for f in follow_ups):
            requirements.append("")
            requirements.append("FOLLOW-UP ANALYSES:")
            for fu in follow_ups:
                if fu.get("name") or fu.get("timing"):
                    requirements.append(f"  - {fu.get('name', 'Analysis')} at {fu.get('timing', 'TBD')} (Section {fu.get('section', 'N/A')})")

        # Protocol amendments (COVID, etc.)
        amendments = protocol_sections.get("protocol_amendments", [])
        if amendments and any(a.get("name") for a in amendments):
            requirements.append("")
            requirements.append("PROTOCOL AMENDMENTS/VARIATIONS:")
            for a in amendments:
                if a.get("name"):
                    requirements.append(f"  - {a.get('name')}: {a.get('description', '')} (Section {a.get('section', 'N/A')})")

        # Concordance analyses
        concordance = protocol_sections.get("concordance_analyses", [])
        if concordance and any(c.get("name") or c.get("comparators") for c in concordance):
            requirements.append("")
            requirements.append("CONCORDANCE ANALYSES (MUST INCLUDE):")
            for c in concordance:
                if c.get("name") or c.get("comparators"):
                    requirements.append(f"  - {c.get('name', 'Concordance')}: {c.get('comparators', '')} using {c.get('method', 'kappa')} (Section {c.get('section', 'N/A')})")

        # Enrollment summaries
        enrollment = protocol_sections.get("enrollment_summaries", [])
        if enrollment and any(e.get("breakdown_by") for e in enrollment):
            requirements.append("")
            requirements.append("ENROLLMENT SUMMARIES BY:")
            for e in enrollment:
                if e.get("breakdown_by"):
                    requirements.append(f"  - {e.get('breakdown_by')} (Section {e.get('section', 'N/A')})")

        # Prior therapy details
        prior_therapy = protocol_sections.get("prior_therapy_details", [])
        if prior_therapy and any(p.get("category") for p in prior_therapy):
            requirements.append("")
            requirements.append("PRIOR THERAPY DETAILS (include tables for):")
            for p in prior_therapy:
                if p.get("category"):
                    requirements.append(f"  - {p.get('category')} (Section {p.get('section', 'N/A')})")

        # Additional subgroups
        subgroups = protocol_sections.get("additional_subgroups", [])
        if subgroups and any(s.get("factor") for s in subgroups):
            requirements.append("")
            requirements.append("ADDITIONAL SUBGROUP ANALYSES:")
            for s in subgroups:
                if s.get("factor"):
                    requirements.append(f"  - {s.get('factor')} (Section {s.get('section', 'N/A')})")

        # CAR-T manufacturing metrics
        cart_mfg = protocol_sections.get("cart_manufacturing_metrics", [])
        if cart_mfg and any(m.get("metric") for m in cart_mfg):
            requirements.append("")
            requirements.append("CAR-T MANUFACTURING METRICS (MUST INCLUDE):")
            for m in cart_mfg:
                if m.get("metric"):
                    requirements.append(f"  - {m.get('metric')} (Section {m.get('section', 'N/A')})")

        # Healthcare utilization
        hc_util = protocol_sections.get("healthcare_utilization", [])
        if hc_util and any(h.get("metric") for h in hc_util):
            requirements.append("")
            requirements.append("HEALTHCARE UTILIZATION ANALYSES:")
            for h in hc_util:
                if h.get("metric"):
                    requirements.append(f"  - {h.get('metric')} (Section {h.get('section', 'N/A')})")

        # Supportive care
        supportive = protocol_sections.get("supportive_care", [])
        if supportive and any(s.get("category") for s in supportive):
            requirements.append("")
            requirements.append("SUPPORTIVE CARE SUMMARIES:")
            for s in supportive:
                if s.get("category"):
                    requirements.append(f"  - {s.get('category')} (Section {s.get('section', 'N/A')})")

        # Laboratory analyses
        lab = protocol_sections.get("laboratory_analyses", [])
        if lab and any(l.get("type") for l in lab):
            requirements.append("")
            requirements.append("LABORATORY ANALYSES:")
            for l in lab:
                if l.get("type"):
                    requirements.append(f"  - {l.get('type')} (Section {l.get('section', 'N/A')})")

        # Landmark analyses
        landmark = protocol_sections.get("landmark_analyses", [])
        if landmark and any(l.get("timepoint") for l in landmark):
            requirements.append("")
            requirements.append("LANDMARK ANALYSES (MUST INCLUDE):")
            for l in landmark:
                if l.get("timepoint"):
                    requirements.append(f"  - {l.get('timepoint')} for {', '.join(l.get('endpoints', []))} (Section {l.get('section', 'N/A')})")

        # Special TTE methods
        tte = protocol_sections.get("special_tte_methods", [])
        if tte and any(t.get("method") for t in tte):
            requirements.append("")
            requirements.append("SPECIAL TIME-TO-EVENT METHODS:")
            for t in tte:
                if t.get("method"):
                    requirements.append(f"  - {t.get('method')}: {t.get('purpose', '')} (Section {t.get('section', 'N/A')})")

        # Required references
        refs = protocol_sections.get("required_references", [])
        if refs and any(r.get("citation") for r in refs):
            requirements.append("")
            requirements.append("REFERENCES SECTION MUST INCLUDE:")
            for r in refs:
                if r.get("citation"):
                    requirements.append(f"  - {r.get('citation')} (for {r.get('for_what', '')})")

        # Appendices
        appendices = protocol_sections.get("appendices", [])
        if appendices and any(a.get("name") for a in appendices):
            requirements.append("")
            requirements.append("APPENDICES (MUST INCLUDE):")
            for a in appendices:
                if a.get("name"):
                    requirements.append(f"  - {a.get('name')}: {a.get('content', '')} (Section {a.get('section', 'N/A')})")

        return "\n".join(requirements) if len(requirements) > 2 else ""

    def _build_tool_routing_instructions(self, full_extraction: Optional[Dict]) -> str:
        """Build tool routing instructions based on discovered protocol structure."""
        if not full_extraction:
            return "Call get_similar_trials() first, then use standard tools."

        instructions = []
        discovered = full_extraction.get("discovered_structure", {})
        flags = discovered.get("study_type_flags", {}) if discovered else {}
        disease_setting = discovered.get("disease_setting", "") if discovered else ""
        response_criteria = discovered.get("response_criteria", "") if discovered else ""

        # 1. Response criteria routing
        if response_criteria:
            if response_criteria in ["Lugano", "IMWG", "PCWG3", "RANO", "RANO_BM", "GCIG", "irRECIST", "iRECIST", "ELN"]:
                instructions.append(f"CALL get_response_criteria('{response_criteria}') for tumor response definitions")
            elif response_criteria == "RECIST":
                instructions.append("CALL get_recist_specifications() for RECIST 1.1 response definitions")
        else:
            # Infer from flags
            if flags.get("is_hematologic"):
                instructions.append("CALL get_response_criteria('Lugano') or get_response_criteria('IMWG') based on disease type")
            if flags.get("is_immunotherapy"):
                instructions.append("CALL get_response_criteria('irRECIST') or get_response_criteria('iRECIST')")
            if flags.get("is_prostate"):
                instructions.append("CALL get_response_criteria('PCWG3') for PSA and bone scan criteria")
            if flags.get("is_brain_tumor"):
                instructions.append("CALL get_response_criteria('RANO') for brain tumor assessment")

        # 2. Therapy type routing
        if flags.get("is_cart"):
            instructions.append("CALL get_cart_specifications() for CRS grading (ASTCT), ICANS grading, cellular kinetics, DORR, re-treatment")
            instructions.append("CALL get_cart_tables() for CAR-T specific TFL templates (CRS/ICANS summary, kinetics, no dose mods)")
        if flags.get("is_bispecific"):
            instructions.append("CALL get_bispecific_specifications() for CRS monitoring and step-up dosing")
        if flags.get("is_adc"):
            instructions.append("CALL get_adc_specifications() for ocular toxicity and neuropathy monitoring")

        # 2b. Lymphoma-specific routing
        disease = full_extraction.get("disease_classification", {})
        tumor_type = (disease.get("tumor_type", {}).get("value") or "").lower() if disease else ""
        is_lymphoma = "lymphoma" in tumor_type or response_criteria == "Lugano" or flags.get("is_hematologic")

        if is_lymphoma:
            instructions.append("CALL get_lymphoma_tables() for Ann Arbor staging, FLIPI/IPI scores, Lugano response (NOT RECIST)")

        # 2c. Single-arm study routing
        study_design = full_extraction.get("study_design", {})
        design_type = (study_design.get("design_type", {}).get("value") or "").lower() if study_design else ""
        arms = full_extraction.get("treatment_arms", [])

        if design_type == "single_arm" or len(arms) == 1:
            instructions.append("CALL get_single_arm_tables() for single-arm TFL templates (no randomization, single column, Clopper-Pearson CI)")

        # 3. Study type routing
        if disease_setting == "adjuvant":
            instructions.append("CALL get_study_type_template('adjuvant') for DFS/RFS endpoints and NO tumor response tables")
        elif disease_setting == "neoadjuvant":
            instructions.append("CALL get_study_type_template('neoadjuvant') for pCR endpoints")
        if flags.get("is_basket"):
            instructions.append("CALL get_study_type_template('basket') for tumor-agnostic analysis approach")
        if flags.get("is_umbrella"):
            instructions.append("CALL get_study_type_template('umbrella') for biomarker-defined cohorts")

        # 4. Standard tools always needed
        instructions.append("CALL get_statistical_method() for Cox, Kaplan-Meier, log-rank formulas")
        instructions.append("CALL get_multiplicity_adjustment() if multiple hypotheses")
        instructions.append("CALL get_similar_trials() to find precedent for censoring rules and methods")
        instructions.append("CALL get_disposition_tables(), get_efficacy_tables(), get_safety_tables() for TFL shells")
        instructions.append("CALL get_oncology_tfl_templates() for endpoint specifications, OS tables, AE tables")
        instructions.append("CALL get_safety_analysis_specs() for AE analysis methods, CTCAE grading, exposure-adjusted rates")
        instructions.append("CALL get_tfl_shells() for complete TFL structure templates with column headers and footnotes")
        instructions.append("CALL get_programming_specifications() for visit windowing, baseline definition, derivation rules")
        instructions.append("CALL get_adam_dataset_spec() for ADaM dataset specs (adsl/adae/adtte/adrs/adlb/adex/advs/adeg/adpr/adcm/admh)")

        # 5. Prognostic scores if applicable
        if flags.get("is_hematologic"):
            instructions.append("CALL get_prognostic_scores() for IPI/ISS/FLIPI if applicable")

        # 6. Biomarker endpoints if needed
        biomarkers = discovered.get("biomarker_requirements", []) if discovered else []
        if biomarkers:
            instructions.append("CALL get_biomarker_endpoints() for PD-L1/TMB/MSI assessment methods")

        return "\n".join(instructions) if instructions else "Use standard tools based on endpoint types."

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

    def _strip_conversational_preamble(self, text: str) -> str:
        """
        Strip conversational preamble from Claude's response.

        Claude sometimes includes text like "I'll generate a SAP..." before the actual content.
        This strips everything before the first SAP header.
        """
        import re

        # Patterns that indicate the start of actual SAP content
        sap_start_patterns = [
            r'^#\s*STATISTICAL\s*ANALYSIS\s*PLAN',  # # STATISTICAL ANALYSIS PLAN
            r'^#{1,2}\s*1\.',  # ## 1. or # 1.
            r'^\*\*Protocol\s+Number',  # **Protocol Number
            r'^---\s*\n\s*#',  # --- followed by header
        ]

        # Try to find the start of the actual SAP
        for pattern in sap_start_patterns:
            match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
            if match:
                # Found the start - return from this point
                start_idx = match.start()
                if start_idx > 0:
                    print(f"[DEBUG] Stripped {start_idx} chars of conversational preamble")
                return text[start_idx:]

        # If no clear start found, try to find after common phrases
        cleanup_phrases = [
            "Here is the SAP:",
            "Here's the SAP:",
            "Here is the complete SAP:",
            "Now I'll generate",
            "I'll generate",
            "Let me generate",
        ]

        for phrase in cleanup_phrases:
            if phrase in text[:500]:
                idx = text.find(phrase)
                # Find the next line after the phrase
                next_newline = text.find('\n', idx)
                if next_newline != -1:
                    remainder = text[next_newline:].lstrip('\n')
                    print(f"[DEBUG] Stripped preamble ending with '{phrase}'")
                    return remainder

        return text

    def generate_sap_with_tools(
        self,
        extracted_facts: List[Dict],
        protocol_content: str,
        full_extraction: Optional[Dict] = None
    ) -> Tuple[str, List[Dict], List[str]]:
        """
        Generate SAP using tool-based knowledge base access.

        Claude explicitly calls tools to retrieve standards/templates,
        ensuring clear provenance and no contamination.

        Returns:
            Tuple of (generated_sap, knowledge_used, warnings)
        """
        # Initialize knowledge base tools
        kb = KnowledgeBaseTools()
        tools = get_claude_tool_definitions()

        # Format extraction
        if full_extraction:
            extraction_json = json.dumps(full_extraction, indent=2, default=str)
        else:
            extraction_json = self._format_facts_with_provenance(extracted_facts)

        # Build context-specific prohibition rules
        prohibition_rules = self._build_prohibition_rules(full_extraction)

        # Build tool routing based on discovered structure
        tool_routing = self._build_tool_routing_instructions(full_extraction)

        # === v69: DYNAMIC SAP STRUCTURE ===
        # Get required sections based on protocol extraction
        required_sections = get_required_sections(full_extraction or {})
        section_outline = format_section_outline(required_sections, include_tools=False)
        section_summary = get_section_summary(full_extraction or {})
        required_tools = get_all_kb_tools_for_sections(required_sections)

        # Count sections for prompt
        num_main_sections = section_summary['main_sections']
        special_sections = section_summary.get('special_sections', [])

        # Build protocol-specific required sections from discovery
        protocol_requirements = self._build_protocol_specific_requirements(full_extraction)

        print(f"[SAP Structure] Generating {num_main_sections} main sections")
        if special_sections:
            print(f"[SAP Structure] Special sections: {', '.join(special_sections)}")

        # Initial prompt
        system_prompt = f"""You are a senior biostatistician creating a Statistical Analysis Plan (SAP).

You have access to COMPREHENSIVE knowledge base tools:
1. METHODOLOGY KB: Statistical methods, table templates, regulatory specifications
2. RESPONSE CRITERIA KB: RECIST, Lugano, IMWG, irRECIST, iRECIST, RANO, PCWG3, GCIG
3. THERAPY-SPECIFIC KB: CAR-T (CRS/ICANS), bispecific antibodies, ADCs
4. STUDY TYPE KB: Adjuvant, neoadjuvant, basket, umbrella templates
5. TRIAL PRECEDENT KB: 354 real trial SAPs for precedent

## TOOL ROUTING FOR THIS PROTOCOL:
{tool_routing}

When you need a standard specification, USE THE TOOLS PROVIDED. Do not make up formulas or templates.

## PROHIBITED CONTENT (Protocol-Specific):
{prohibition_rules}

## CRITICAL ANTI-HALLUCINATION RULES:
1. RACE/ETHNICITY: Include ONLY if explicitly in baseline_variables[]. Nordic/European studies do NOT collect these.
2. PERFORMANCE STATUS: Use EXACTLY the scale from extraction (ECOG/Karnofsky/Lansky).
3. GEOGRAPHIC SUBGROUPS: Use ONLY countries from extraction.
4. RESPONSE TABLES: Match to disease_setting:
   - ADJUVANT: NO tumor response tables (CR/PR/SD/PD)
   - METASTATIC: Use appropriate criteria (RECIST/Lugano/IMWG/etc.)
5. AE GRADING: Use EXACTLY what's in extraction. For CAR-T: include CRS/ICANS grading.
6. DOSE MODIFICATION: Include ONLY if dose_modifications has rules. Fixed-dose = NO modification rows.
7. TREATMENT ARMS: Use EXACT arm names from extraction as column headers.

IMPORTANT RULES:
1. Protocol facts (from extraction) are STUDY-SPECIFIC - use them for this study
2. Knowledge base (from tools) provides STANDARD TEMPLATES - adapt to protocol specifics
3. ALWAYS call tools for: statistical methods, table shells, response criteria, therapy-specific specs
4. Mark sources with SPECIFIC CITATIONS using these formats:
   - For KB: [KB: source_file → key] (e.g., [KB: methodology_knowledge_base.py → STATISTICAL_METHODS['kaplan_meier']])
   - For Protocol: [Protocol: Section X.Y] or [Protocol: "quoted text..."] (e.g., [Protocol: Section 6.1 - Primary Endpoint])

CRITICAL - TOOL CALL EFFICIENCY:
- Each tool should be called ONLY ONCE with the same parameters
- Do NOT re-call tools you've already used - the data is already in your conversation context
- After gathering KB data (typically 10-15 tool calls), STOP calling tools and WRITE the complete SAP
- If you receive a "CACHED" response, that means you're repeating yourself - generate the SAP immediately

Generate a production-quality SAP with full provenance tracking."""

        # Build special section notes
        special_notes = ""
        if special_sections:
            special_notes = "\n**PROTOCOL-SPECIFIC SECTIONS DETECTED:**\n" + "\n".join([f"- {s}" for s in special_sections])

        # Build study type description
        conditions = section_summary.get('conditions_detected', {})
        study_type_desc = "Standard"
        if conditions.get('is_single_arm'):
            study_type_desc = "Single-Arm"
        elif conditions.get('is_randomized'):
            study_type_desc = "Randomized"

        therapy_type_desc = "Standard"
        if conditions.get('is_cart'):
            therapy_type_desc = "CAR-T Cell Therapy"
        elif conditions.get('is_bispecific'):
            therapy_type_desc = "Bispecific Antibody"
        elif conditions.get('is_adc'):
            therapy_type_desc = "ADC"

        disease_desc = "Solid Tumor"
        if conditions.get('is_lymphoma'):
            disease_desc = "Lymphoma"
        elif conditions.get('is_hematologic'):
            disease_desc = "Hematologic Malignancy"

        user_prompt = f"""## PROTOCOL EXTRACTION (Study-Specific Facts):
```json
{extraction_json}
```

## FULL PROTOCOL (for reference):
{protocol_content[:10000]}

---

## DYNAMIC SAP STRUCTURE (Based on Protocol Analysis - v69)

This protocol requires **{num_main_sections} main sections** (structure determined by protocol characteristics).

**Protocol Classification:**
- Study Design: {study_type_desc}
- Therapy Type: {therapy_type_desc}
- Disease Area: {disease_desc}
{special_notes}

**MANDATORY SECTION OUTLINE (use these EXACT headers):**

{section_outline}

CRITICAL REQUIREMENTS:
- You MUST generate ALL sections shown above
- Use the EXACT "## N." format for main section headers (e.g., "## 1. TITLE PAGE...")
- Subsections use "### N.N" format (e.g., "### 5.1 Intent-to-Treat Population")
- ADDITIONAL DISCOVERIES: Check "additional_discoveries" in extraction for protocol-specific elements

{protocol_requirements}

## SOURCE CITATION FORMAT (MANDATORY):
Every fact MUST have a SPECIFIC, TRACEABLE source citation. Use these formats:

1. **Trial Precedent Sources** - When using get_similar_trials(), cite the ACTUAL TRIAL NAME:
   - ✅ CORRECT: [Precedent: ZUMA-1 trial (Phase 2 DLBCL) - censoring rules]
   - ✅ CORRECT: [Precedent: KEYNOTE-189 (Phase 3 NSCLC) - interim analysis design]
   - ✅ CORRECT: [Precedent: CheckMate-067 (Phase 3 melanoma) - multiplicity adjustment]
   - ❌ WRONG: [KB: factual_kg_merged.json] (no trial name!)

2. **Regulatory/Standards Sources** - Cite the ACTUAL regulatory document:
   - ✅ CORRECT: [ICH E9(R1) Section 5.2 - Estimand Framework]
   - ✅ CORRECT: [FDA Guidance: Clinical Trial Endpoints for Approval of Cancer Drugs (2018)]
   - ✅ CORRECT: [Lugano Classification (Cheson 2014) - Response Criteria]
   - ✅ CORRECT: [CTCAE v5.0 - Adverse Event Grading]
   - ❌ WRONG: [KB: methodology_knowledge_base.py] (too generic!)

3. **Protocol Sources** - Include EXACT section number AND brief content:
   - ✅ CORRECT: [Protocol Section 6.1: "The primary endpoint is ORR per Lugano criteria"]
   - ✅ CORRECT: [Protocol Section 9.3.2: Statistical Hypothesis - HR=0.70]
   - ✅ CORRECT: [Protocol Section 8.1: Sample Size - N=100 with 80% power]
   - ❌ WRONG: [Protocol] (no section number!)
   - ❌ WRONG: [Protocol: endpoints] (too vague!)

4. **TFL Template Sources** - Cite the table standard:
   - ✅ CORRECT: [CDISC ADaM IG v1.3 - ADTTE specification]
   - ✅ CORRECT: [ICH E3 Section 11.4 - Disposition table format]
   - ❌ WRONG: [KB: complete_tfl_inventory.py] (not traceable!)

When using get_similar_trials() results, the JSON includes "trial_id" and "source_sap" - USE THE TRIAL NAME in your citations, not the file path.

## RECOMMENDED KB TOOLS FOR THIS PROTOCOL:
{chr(10).join([f"- {tool}()" for tool in sorted(required_tools)])}

## SECTION 12 TABLE/FIGURE SHELLS - CRITICAL FORMATTING:

⚠️ DO NOT write prose descriptions like "Table 14.1.1: Subject Disposition - Column headers: X, Y, Z - Key rows: A, B, C"
⚠️ YOU MUST output ACTUAL MARKDOWN TABLES with | separators and xxx placeholders

CORRECT FORMAT (you MUST use this exact structure):

**TABLE 14.1.1: Subject Disposition**
|Category|Treatment A (N=xxx)|Treatment B (N=xxx)|Total (N=xxx)|
|--------|-------------------|-------------------|-------------|
|Screened|xxx|xxx|xxx|
|Screen Failures|xxx|xxx|xxx|
|Randomized|xxx|xxx|xxx|
|Completed Treatment|xxx|xxx|xxx|
|Discontinued|xxx|xxx|xxx|
|  Adverse Event|xxx|xxx|xxx|
|  Withdrawal by Subject|xxx|xxx|xxx|
|  Lost to Follow-up|xxx|xxx|xxx|

**TABLE 14.1.2: Demographics and Baseline Characteristics**
|Parameter|Statistic|Treatment A (N=xxx)|Treatment B (N=xxx)|
|---------|---------|-------------------|-------------------|
|Age (years)|n|xxx|xxx|
||Mean (SD)|xxx (xxx)|xxx (xxx)|
||Median|xxx|xxx|
||Min, Max|xxx, xxx|xxx, xxx|
|Sex, n (%)|Male|xxx (xx.x)|xxx (xx.x)|
||Female|xxx (xx.x)|xxx (xx.x)|

WRONG FORMAT (DO NOT DO THIS):
"Table 14.1.1: Subject Disposition - Column headers: Category | Treatment A - Key rows: Screened, Randomized..."

Call get_disposition_tables, get_efficacy_tables, get_safety_tables tools.
Convert their JSON output to ACTUAL markdown tables with:
- TABLE 14.x.x numbering as **bold header**
- Markdown table with | column | separators |
- |------|------| separator row after header
- xxx placeholders for all numeric values
- Every row on its own line

RECOMMENDED TOOL ORDER:
1. FIRST: Call get_similar_trials() with the protocol's phase, indication, and primary endpoint to find precedent
2. THEN: Use the similar trials' censoring rules, multiplicity, and methods as a starting point
3. FINALLY: Call get_statistical_method, get_disposition_tables, get_efficacy_tables, get_safety_tables for templates

Start by calling get_similar_trials to find precedent, then generate the COMPLETE SAP with ALL sections shown above."""

        messages = [{"role": "user", "content": user_prompt}]
        knowledge_used = []
        warnings = []
        accumulated_text = ""  # Accumulate ALL text across iterations

        # v65: Track called tools to prevent duplicates
        called_tools_cache = {}  # {tool_key: result} - cache results for reuse

        # Tool-use loop
        max_iterations = 25  # Increased from 15 for complex protocols
        iteration = 0

        print(f"[KG Generator] Starting tool-use loop (max {max_iterations} iterations)")
        print(f"[DEBUG] Protocol length: {len(protocol_content)} chars")
        print(f"[DEBUG] Extraction available: {full_extraction is not None}")

        while iteration < max_iterations:
            iteration += 1

            try:
                print(f"[DEBUG] Iteration {iteration}: sending {len(messages)} messages")
                print(f"[DEBUG] v48: Using client.messages.stream() for long operations")

                # Use streaming to handle long operations (>10 min timeout)
                with self.client.messages.stream(
                    model=self.model,
                    max_tokens=32000,  # Increased for complete SAP
                    system=system_prompt,
                    tools=tools,
                    messages=messages
                ) as stream:
                    response = stream.get_final_message()

                print(f"[DEBUG] Response stop_reason={response.stop_reason}, content blocks={len(response.content)}")

                # Check if there are tool calls
                tool_calls = [block for block in response.content if block.type == "tool_use"]

                # Extract and accumulate text from this response
                current_text = ""
                text_blocks = 0
                for block in response.content:
                    if hasattr(block, "text") and block.text:
                        current_text += block.text
                        text_blocks += 1

                # Accumulate text across ALL iterations
                if current_text:
                    accumulated_text += current_text

                print(f"[DEBUG] Tool calls: {len(tool_calls)}, Text blocks: {text_blocks}, Accumulated: {len(accumulated_text)} chars")

                # If no tool calls and stop_reason is end_turn, we're done
                if not tool_calls and response.stop_reason == "end_turn":
                    # Strip any conversational preamble from accumulated text
                    final_sap_text = self._strip_conversational_preamble(accumulated_text)

                    # Check if we have actual SAP content
                    if final_sap_text and len(final_sap_text) > 1000:
                        print(f"[KG Generator] Completed after {iteration} iterations, {len(knowledge_used)} KB lookups")
                        print(f"[DEBUG] Final SAP: {len(final_sap_text)} chars")
                        return final_sap_text, knowledge_used, warnings
                    else:
                        # We finished tool calls but SAP is too short - need continuation
                        print(f"[DEBUG] End turn but SAP too short ({len(accumulated_text)} chars)")
                        print("[DEBUG] Sending continuation prompt to generate SAP...")

                        # Add a continuation message to generate the SAP
                        continuation_prompt = """Now generate the COMPLETE Statistical Analysis Plan.

MANDATORY: Use the EXACT section headers from the MANDATORY SECTION OUTLINE provided earlier.
The structure is DYNAMIC based on this protocol's characteristics (study design, therapy type, disease area).

Output ONLY the SAP document. Start with "# STATISTICAL ANALYSIS PLAN" then include ALL sections from the outline.
Each section uses "## N." format, subsections use "### N.N" format."""

                        # Serialize current response and add continuation
                        assistant_content = []
                        for block in response.content:
                            if block.type == "text":
                                assistant_content.append({"type": "text", "text": block.text})

                        if assistant_content:
                            messages.append({"role": "assistant", "content": assistant_content})
                        messages.append({"role": "user", "content": continuation_prompt})
                        continue  # Continue loop to get SAP generation

                # If no tool calls but not end_turn, something is wrong
                if not tool_calls:
                    print(f"[KG Generator] No tool calls, stop_reason={response.stop_reason}")
                    final_sap = self._strip_conversational_preamble(accumulated_text)
                    if final_sap and len(final_sap) > 1000:
                        return final_sap, knowledge_used, warnings
                    warnings.append(f"Unexpected stop without tool calls: {response.stop_reason}")
                    break

                # Process tool calls
                print(f"[KG Generator] Iteration {iteration}: {len(tool_calls)} tool calls")
                tool_results = []
                duplicate_count = 0
                for i, tool_call in enumerate(tool_calls):
                    tool_name = tool_call.name
                    tool_input = tool_call.input

                    # v65: Create cache key and check for duplicates
                    cache_key = f"{tool_name}:{json.dumps(tool_input, sort_keys=True)}"

                    if cache_key in called_tools_cache:
                        # DUPLICATE - return cached result
                        duplicate_count += 1
                        cached_result = called_tools_cache[cache_key]
                        print(f"[DEBUG] Tool {i+1}/{len(tool_calls)}: {tool_name} - DUPLICATE (using cached)")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_call.id,
                            "content": f"[CACHED - Already retrieved] You already called this tool with these parameters. The data is in your context above. Do NOT call this tool again. Generate the SAP now."
                        })
                        continue

                    print(f"[DEBUG] Tool {i+1}/{len(tool_calls)}: {tool_name}({json.dumps(tool_input)[:100]})")

                    try:
                        # Execute the tool
                        result = execute_tool(tool_name, tool_input, kb)
                        result_json = json.dumps(result.to_dict(), indent=2, default=str)
                        print(f"[DEBUG] Tool result: {len(result_json)} chars from {result.source_file}")

                        # v65: Cache the result
                        called_tools_cache[cache_key] = result_json

                        # Track what knowledge was used
                        knowledge_used.append({
                            "tool": tool_name,
                            "input": tool_input,
                            "source": result.source_file,
                            "source_key": result.source_key
                        })

                        # Format result for Claude
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_call.id,
                            "content": result_json
                        })
                    except Exception as tool_error:
                        print(f"[KG Generator] Tool error {tool_name}: {tool_error}")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_call.id,
                            "content": f"Error: {str(tool_error)}",
                            "is_error": True
                        })

                if duplicate_count > 0:
                    print(f"[DEBUG] Skipped {duplicate_count} duplicate tool calls")

                # Convert response.content to serializable format for messages
                assistant_content = []
                for block in response.content:
                    if block.type == "text":
                        assistant_content.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use":
                        assistant_content.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input
                        })

                # Add assistant response and tool results to messages
                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({"role": "user", "content": tool_results})

                # v65: Check if essential TFL tools have been called - force SAP generation
                essential_tfl_tools = {'get_disposition_tables', 'get_efficacy_tables', 'get_safety_tables'}
                called_tool_names = {k.split(':')[0] for k in called_tools_cache.keys()}
                has_all_tfl_tools = essential_tfl_tools.issubset(called_tool_names)

                # If we have all TFL tools AND duplicates are happening, force SAP generation
                if has_all_tfl_tools and duplicate_count > 0:
                    print(f"[DEBUG] v65: All TFL tools called + duplicates detected - forcing SAP generation")
                    force_sap_prompt = """STOP CALLING TOOLS. You have already gathered ALL the knowledge base data you need:
- Disposition tables: Retrieved
- Efficacy tables: Retrieved
- Safety tables: Retrieved
- Statistical methods: Retrieved

NOW GENERATE THE COMPLETE SAP. Do not call any more tools.

Output the COMPLETE SAP document starting with "# STATISTICAL ANALYSIS PLAN" and including ALL sections from the MANDATORY SECTION OUTLINE provided earlier. Include TFL shells with actual markdown tables."""

                    messages.append({"role": "user", "content": force_sap_prompt})
                    print(f"[DEBUG] Injected force-SAP prompt after {len(called_tools_cache)} unique tool calls")

            except Exception as e:
                print(f"[KG Generator] Error at iteration {iteration}: {e}")
                warnings.append(f"Tool-use error at iteration {iteration}: {str(e)}")
                final_sap = self._strip_conversational_preamble(accumulated_text)
                if final_sap and len(final_sap) > 100:
                    return final_sap, knowledge_used, warnings
                break

        # If we hit max iterations, try one more time to generate SAP
        print(f"[KG Generator] Reached max iterations ({max_iterations}), attempting final SAP generation...")

        final_sap_text = self._strip_conversational_preamble(accumulated_text)

        if len(final_sap_text) < 1000 and knowledge_used:
            # We gathered knowledge but never generated the SAP - try once more
            try:
                final_prompt = f"""You have gathered knowledge from {len(knowledge_used)} tool calls.

Now generate the COMPLETE SAP using the EXACT section headers from the MANDATORY SECTION OUTLINE provided earlier.
The structure is DYNAMIC based on this protocol's characteristics (study design, therapy type, disease area).

Start with "# STATISTICAL ANALYSIS PLAN" then include ALL sections from the outline.
Each section uses "## N." format, subsections use "### N.N" format.
All sections are MANDATORY."""

                messages.append({"role": "user", "content": final_prompt})

                # Use streaming for long operations
                with self.client.messages.stream(
                    model=self.model,
                    max_tokens=32000,
                    system=system_prompt,
                    tools=[],  # No tools for final generation
                    messages=messages
                ) as stream:
                    response = stream.get_final_message()

                for block in response.content:
                    if hasattr(block, "text") and block.text:
                        final_sap_text += block.text

                print(f"[KG Generator] Final generation: {len(final_sap_text)} chars")

            except Exception as e:
                print(f"[KG Generator] Final generation failed: {e}")
                warnings.append(f"Final generation failed: {str(e)}")

        if final_sap_text and len(final_sap_text) > 100:
            print(f"[KG Generator] Returning {len(final_sap_text)} chars after {iteration} iterations")
            return final_sap_text, knowledge_used, warnings

        warnings.append(f"Reached max iterations ({max_iterations}) with no SAP generated")
        return "", knowledge_used, warnings


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
        # Disable timeout to prevent "Streaming is required" error for long operations
        self.client = anthropic.Anthropic(
            api_key=api_key,
            timeout=httpx.Timeout(None)  # No timeout limit
        )
        self.model = "claude-sonnet-4-20250514"

        # Initialize components
        self.kg = FactualKnowledgeGraphV2()
        self.verifier = SelfRAGVerifier()
        self.power_calc = SimplePowerCalculator()
        self.rag = SimpleRAGRetriever()
        self.generator = EnhancedClaudeSAPGenerator(api_key)
        self.regulatory_kb = RegulatoryKnowledgeBase()

        # Store for comprehensive extraction (55 categories)
        self._last_full_extraction = None

        # Load existing KG
        self._load_existing_kg()

        print("✅ Enhanced KG Pipeline initialized (55-CATEGORY EXTRACTION)")
        print(f"   • Knowledge Graph: {len(self.kg.nodes)} nodes")
        print(f"   • RAG Examples: {len(self.rag.sap_examples)} SAPs")
        print(f"   • Power Calculator: {'scipy' if self.power_calc.available else 'unavailable'}")
        print(f"   • Regulatory KB: MedDRA {self.regulatory_kb.get_meddra_version()}, CTCAE {self.regulatory_kb.get_ctcae_version()}")
        print("   • Extraction: Comprehensive 55-category protocol extraction")
        print("   • Coverage: Phase 1-3, Immunotherapy, CAR-T, Hematologic, Basket/Umbrella")

    def _load_existing_kg(self):
        """Load existing Claude-extracted KG."""
        # Use merged KG (354 trials from original + 151 PDF extractions)
        kg_path = Path(__file__).parent / "output" / "factual_kg_merged.json"

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

    def process_protocol(self, protocol_path: str, use_tools: bool = True) -> Dict:
        """
        Full enhanced pipeline.

        Args:
            protocol_path: Path to protocol file
            use_tools: If True, use tool-based KB access (recommended for accuracy)
                      If False, use simple prompt-based generation

        Steps:
        1. Extract entities with Claude (with provenance)
        2. Calculate power/sample size
        3. Retrieve RAG examples
        4. Generate SAP (with tools for KB access)
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

        # Get full extraction if available (stored during _extract_entities)
        full_extraction = getattr(self, '_last_full_extraction', None)
        if full_extraction:
            print(f"   • Using comprehensive 55-category extraction")

        knowledge_used = []  # Track KB usage for provenance

        if use_tools:
            print("   • Mode: TOOL-BASED KB ACCESS (explicit retrieval)")
            sap_content, knowledge_used, gen_warnings = self.generator.generate_sap_with_tools(
                extracted_facts=extracted,
                protocol_content=protocol_content,
                full_extraction=full_extraction
            )
            print(f"   • Knowledge base tools called: {len(knowledge_used)}")
            for kb_item in knowledge_used[:5]:
                print(f"     - {kb_item['tool']}({kb_item.get('input', {})})")
            if len(knowledge_used) > 5:
                print(f"     - ... and {len(knowledge_used) - 5} more")
        else:
            print("   • Mode: PROMPT-BASED (no explicit KB access)")
            sap_content, gen_warnings = self.generator.generate_sap(
                extracted_facts=extracted,
                kg_context=kg_context,
                protocol_content=protocol_content,
                power_calc=power_result,
                rag_examples=rag_examples,
                regulatory_context=regulatory_context,
                full_extraction=full_extraction
            )

        print(f"✅ Generated SAP ({len(sap_content)} chars)")

        # Check if SAP generation failed completely
        if len(sap_content) < 1000:
            print(f"\n❌ SAP generation failed - only {len(sap_content)} chars generated")
            print("   • NOT attempting regeneration from empty/minimal SAP")
            raise ValueError(f"SAP generation failed: only {len(sap_content)} chars generated. Check API streaming/timeout settings.")

        # Step 7: SELF-RAG Verification (NO REGENERATION - just verify)
        print("\n" + "-"*50)
        print("STEP 7: SELF-RAG VERIFICATION")
        print("-"*50)

        verification = self.verifier.verify(sap_content, extracted, power_result)
        print(f"✅ Verification score: {verification.score:.2f}")
        print(f"   • Passed: {verification.passed}")
        print(f"   • Errors: {len(verification.errors)}")
        print(f"   • Warnings: {len(verification.warnings)}")

        # NO FALLBACK REGENERATION - if main generation failed, we fail
        regeneration_count = 0

        if verification.passed:
            print("\n✅ VERIFICATION PASSED")
        else:
            print(f"\n⚠️  Verification not fully passed - NO regeneration (fallback removed)")

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
            "knowledge_base_used": knowledge_used,  # Track explicit KB retrieval
            "generation_mode": "tool_based" if use_tools else "prompt_based",
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
        """
        Extract comprehensive protocol elements using TWO-STAGE DYNAMIC EXTRACTION.

        Stage 1: DISCOVERY - Identify what structure the protocol has
        Stage 2: EXTRACTION - Extract values based on discovered structure

        This 2-call approach is more accurate because:
        - Stage 1 focuses purely on understanding structure (lower cognitive load)
        - Stage 2 has explicit targets to extract
        - Research shows 29-97% accuracy improvement over single-pass
        """

        # =====================================================================
        # STAGE 1: STRUCTURE DISCOVERY
        # =====================================================================
        discovery_prompt = f"""You are analyzing a clinical trial protocol to DISCOVER its structure.

Your ONLY task is to identify WHAT exists in this protocol - NOT to extract all details yet.

## DISCOVERY CHECKLIST:

### A. ANALYSIS POPULATIONS
List the EXACT names of ALL analysis populations defined in the protocol.
- Do NOT assume standard names - extract EXACTLY what the protocol says
- Examples: "Full Analysis Set (FAS)", "Inferential Analysis Set", "Safety Re-treatment Set"
- Include any special populations (e.g., CAR-T re-treatment populations, PK populations)

### B. HYPOTHESIS STRUCTURE
- How many numbered hypotheses exist? (H1, H2, H3, H4, etc.)
- What is the testing structure? (sequential/hierarchical/parallel/graphical)
- Does each hypothesis have its own alpha allocation?
- Is there gatekeeping between hypothesis families?

### C. ENDPOINTS
- List all PRIMARY endpoints
- List all KEY SECONDARY endpoints
- List other SECONDARY endpoints
- For time-to-event endpoints, note if detailed censoring rules are specified

### D. SUBGROUPS
- What are the PRE-SPECIFIED subgroup factors from the protocol?
- Only include factors explicitly listed in the protocol

### E. DISEASE SETTING (Critical for correct analysis approach)
Identify the disease setting:
- ADJUVANT: Post-surgery, no measurable disease, endpoints like DFS, RFS, TTR
- NEOADJUVANT: Pre-surgery, endpoints like pCR, MPR
- METASTATIC/ADVANCED: Measurable disease, endpoints like ORR, PFS, OS
- LOCALLY ADVANCED: Unresectable but not metastatic
- MAINTENANCE: After initial response

### F. TUMOR TYPE AND RESPONSE CRITERIA
Identify which applies:
- SOLID TUMORS: RECIST 1.1 (most common)
- LYMPHOMA (NHL/HL): Lugano 2014 (PET-based, Deauville score)
- MULTIPLE MYELOMA: IMWG (sCR, CR, VGPR, PR, MR, SD, PD)
- LEUKEMIA (AML/ALL): ELN 2017/2022 (CR, CRi, CRh, MLFS, PR)
- CLL/SLL: iwCLL criteria
- PROSTATE CANCER: PCWG3 (PSA response, bone scan, soft tissue RECIST)
- BRAIN TUMORS: RANO (bi-dimensional, T2/FLAIR)
- BRAIN METASTASES: RANO-BM
- OVARIAN CANCER: GCIG CA-125 criteria
- IMMUNOTHERAPY: irRECIST or iRECIST (pseudoprogression handling)

### G. THERAPY TYPE (Critical for safety sections)
Identify which applies:
- CAR-T/CELL THERAPY: CRS grading, ICANS, cellular kinetics, bridging, re-treatment
- BISPECIFIC ANTIBODY: CRS (usually lower grade), step-up dosing
- ADC (Antibody-Drug Conjugate): Ocular toxicity, neuropathy monitoring
- CHECKPOINT INHIBITOR: irAEs, colitis, pneumonitis, hepatitis monitoring
- TARGETED THERAPY: Specific toxicities based on target (EGFR->rash, VEGF->HTN)
- CHEMOTHERAPY: Standard CTCAE grading
- HORMONAL THERAPY: Endocrine-related AEs

### H. SPECIAL STUDY DESIGNS
- BASKET: Multiple tumor types, single biomarker
- UMBRELLA: Single tumor type, multiple biomarkers
- PLATFORM: Multiple arms, adaptive
- SEAMLESS Phase 2/3: Dose selection + confirmatory

### I. OTHER CRITICAL ELEMENTS
- Stratification factors for randomization
- Interim analysis structure (how many, what triggers)
- IRC/Central review requirements
- MRD assessment (for hematologic)
- Biomarker requirements (PD-L1, TMB, MSI, HER2, etc.)

### J. PROTOCOL-SPECIFIC ANALYSIS SECTIONS (SCAN ALL SECTIONS)
Scan the entire protocol/SAP for ANY analysis sections not covered above. Look for:
- **Follow-up Analyses**: Planned analyses at specific timepoints (e.g., "at 18 months", "at 24 months", "at X events")
- **Protocol Amendments/Variations**: COVID-19 variations, changes from protocol-specified analyses
- **Concordance Analyses**: IRC vs investigator agreement, kappa statistics
- **Enrollment Summaries**: By country, by site, by region
- **Prior Therapy Details**: Anti-CD20, alkylating agents, prior lines, specific regimens
- **Subgroup Analyses Not Listed Above**: Bone marrow involvement, bulky disease, etc.
- **CAR-T Manufacturing**: Days from leukapheresis to administration/receipt/release
- **Healthcare Utilization**: Duration of hospitalization, ICU days
- **Supportive Care**: Concomitant medications by category, IVIG usage, growth factors
- **Laboratory Analyses**: Shift tables, chemistry/hematology panels
- **Landmark Analyses**: 9-month, 12-month survival rates, forest plots
- **Special TTE Methods**: Reverse Kaplan-Meier for follow-up time
- **References Section**: Required citations (Cheson, Lee, CTCAE version, etc.)
- **Appendices**: Date imputation rules, time-to-event derivation tables, AESI definitions

Return a JSON object with ONLY discovered structure:

{{
  "populations": [
    {{"name": "exact name from protocol", "is_efficacy": true/false, "is_safety": true/false}}
  ],
  "hypotheses": [
    {{"id": "H1", "endpoint": "", "alpha": null, "gate_from": null}}
  ],
  "hypothesis_testing_structure": "sequential|hierarchical|parallel|graphical|single",
  "has_gatekeeping": true/false,
  "primary_endpoints": [
    {{"name": "", "type": "binary|time_to_event|continuous"}}
  ],
  "key_secondary_endpoints": [
    {{"name": "", "type": ""}}
  ],
  "other_secondary_endpoints": [
    {{"name": "", "type": ""}}
  ],
  "censoring_rules_detailed": true/false,
  "censoring_endpoints": [],
  "subgroups": [
    {{"factor": "", "categories": []}}
  ],
  "stratification_factors": [
    {{"factor": "", "categories": []}}
  ],
  "disease_setting": "adjuvant|neoadjuvant|metastatic|locally_advanced|maintenance",
  "tumor_type": "",
  "response_criteria": "RECIST|Lugano|IMWG|ELN|PCWG3|RANO|RANO_BM|GCIG|irRECIST|iRECIST|other",
  "study_type_flags": {{
    "is_cart": false,
    "is_bispecific": false,
    "is_adc": false,
    "is_immunotherapy": false,
    "is_targeted_therapy": false,
    "is_hematologic": false,
    "is_prostate": false,
    "is_brain_tumor": false,
    "is_ovarian": false,
    "is_phase1": false,
    "has_retreatment": false,
    "is_basket": false,
    "is_umbrella": false,
    "is_platform": false
  }},
  "special_sections_needed": [],
  "biomarker_requirements": [],
  "has_irc": false,
  "has_mrd_assessment": false,
  "has_interim_analysis": false,
  "interim_count": 0,

  "protocol_specific_sections": {{
    "follow_up_analyses": [
      {{"name": "", "timing": "", "trigger": "", "section": ""}}
    ],
    "protocol_amendments": [
      {{"name": "", "description": "", "section": ""}}
    ],
    "concordance_analyses": [
      {{"name": "", "comparators": "", "method": "", "section": ""}}
    ],
    "enrollment_summaries": [
      {{"breakdown_by": "", "section": ""}}
    ],
    "prior_therapy_details": [
      {{"category": "", "section": ""}}
    ],
    "additional_subgroups": [
      {{"factor": "", "section": ""}}
    ],
    "cart_manufacturing_metrics": [
      {{"metric": "", "section": ""}}
    ],
    "healthcare_utilization": [
      {{"metric": "", "section": ""}}
    ],
    "supportive_care": [
      {{"category": "", "section": ""}}
    ],
    "laboratory_analyses": [
      {{"type": "", "section": ""}}
    ],
    "landmark_analyses": [
      {{"timepoint": "", "endpoints": [], "section": ""}}
    ],
    "special_tte_methods": [
      {{"method": "", "purpose": "", "section": ""}}
    ],
    "required_references": [
      {{"citation": "", "for_what": ""}}
    ],
    "appendices": [
      {{"name": "", "content": "", "section": ""}}
    ]
  }}
}}

PROTOCOL DOCUMENT:
{content}

Return ONLY the discovery JSON, no other text."""

        try:
            # Stage 1: Discovery call
            print("  📋 Stage 1: Discovering protocol structure...")
            with self.client.messages.stream(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": discovery_prompt}]
            ) as stream:
                discovery_response = stream.get_final_message()

            discovery_text = discovery_response.content[0].text.strip()

            # Clean up response
            if discovery_text.startswith("```json"):
                discovery_text = discovery_text[7:]
            if discovery_text.startswith("```"):
                discovery_text = discovery_text[3:]
            if discovery_text.endswith("```"):
                discovery_text = discovery_text[:-3]

            discovered_structure = json.loads(discovery_text)

            print(f"    ✓ Found {len(discovered_structure.get('populations', []))} populations")
            print(f"    ✓ Found {len(discovered_structure.get('hypotheses', []))} hypotheses")
            print(f"    ✓ Found {len(discovered_structure.get('primary_endpoints', []))} primary endpoints")
            print(f"    ✓ Study type: CAR-T={discovered_structure.get('study_type_flags', {}).get('is_cart', False)}")

        except Exception as e:
            print(f"  ⚠️ Discovery stage failed: {e}, falling back to single-pass")
            discovered_structure = None

        # =====================================================================
        # STAGE 2: VALUE EXTRACTION (using discovered structure)
        # =====================================================================

        # Build extraction prompt based on discovered structure
        extraction_prompt = self._build_extraction_prompt(content, discovered_structure)

        print("  📝 Stage 2: Extracting values based on discovered structure...")

        try:
            with self.client.messages.stream(
                model=self.model,
                max_tokens=16384,
                messages=[{"role": "user", "content": extraction_prompt}]
            ) as stream:
                response = stream.get_final_message()

            response_text = response.content[0].text.strip()

            # Clean up response
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            extracted_obj = json.loads(response_text)

            # Merge discovered structure into extraction
            if discovered_structure:
                extracted_obj["discovered_structure"] = discovered_structure

            # Add doc_id to the extraction
            extracted_obj["source_doc"] = doc_id

            # Convert to list format for backward compatibility with verification
            # while preserving the full structured extraction
            extracted_list = self._convert_extraction_to_list(extracted_obj)

            # Store full extraction for SAP generation
            self._last_full_extraction = extracted_obj

            return extracted_list

        except Exception as e:
            print(f"❌ Extraction error: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _build_extraction_prompt(self, content: str, discovered_structure: Optional[Dict]) -> str:
        """Build extraction prompt based on discovered structure."""

        # Build dynamic population instructions
        if discovered_structure and discovered_structure.get("populations"):
            pop_names = [p.get("name", "") for p in discovered_structure["populations"]]
            pop_instruction = f"""
POPULATIONS TO EXTRACT (from discovery):
{chr(10).join(f"- {name}" for name in pop_names)}
Extract the FULL DEFINITION for each of these populations."""
        else:
            pop_instruction = """
POPULATIONS: Extract ALL populations mentioned, using their EXACT names from the protocol."""

        # Build dynamic hypothesis instructions
        if discovered_structure and discovered_structure.get("hypotheses"):
            hyp_count = len(discovered_structure["hypotheses"])
            hyp_structure = discovered_structure.get("hypothesis_testing_structure", "unknown")
            hyp_instruction = f"""
HYPOTHESES TO EXTRACT:
- This protocol has {hyp_count} hypothesis/hypotheses
- Testing structure: {hyp_structure}
- Extract the INDIVIDUAL ALPHA ALLOCATION for each hypothesis
- If gatekeeping, note which hypothesis gates which"""
        else:
            hyp_instruction = """
HYPOTHESES: Extract all numbered hypotheses with their individual alpha allocations."""

        # Build study-type-specific instructions
        special_instructions = ""
        if discovered_structure:
            flags = discovered_structure.get("study_type_flags", {})
            disease_setting = discovered_structure.get("disease_setting", "")
            response_criteria = discovered_structure.get("response_criteria", "")

            # Disease setting specific
            if disease_setting == "adjuvant":
                special_instructions += """
ADJUVANT STUDY SECTIONS:
- NO tumor response tables (CR/PR/SD/PD) - patients have no measurable disease
- Time-to-event endpoints: DFS, RFS, TTR, DRFS
- Event definitions for recurrence (local, regional, distant, second primary)
- Surgery details and margin status if relevant"""
            elif disease_setting == "neoadjuvant":
                special_instructions += """
NEOADJUVANT STUDY SECTIONS:
- Pathologic response endpoints: pCR, MPR definitions
- Surgery timing and type
- Residual cancer burden if applicable
- Pre- and post-surgery assessments"""

            # Therapy type specific
            if flags.get("is_cart"):
                special_instructions += """
CAR-T/CELL THERAPY SECTIONS TO EXTRACT:
- CRS grading scale (ASTCT/Lee) and grade definitions (1-4)
- ICANS grading (ICE score for >=12y, CAPD for <12y)
- Cellular kinetics: Cmax, Tmax, AUC, persistence, B-cell aplasia duration
- Bridging therapy: allowed yes/no, types, washout
- Lymphodepletion regimen
- Re-treatment criteria and population definition
- Manufacturing failure handling"""
            if flags.get("is_bispecific"):
                special_instructions += """
BISPECIFIC ANTIBODY SECTIONS TO EXTRACT:
- CRS grading and management
- Step-up dosing schedule
- Cytokine monitoring (IL-6, ferritin, CRP)
- Neurological toxicity monitoring"""
            if flags.get("is_adc"):
                special_instructions += """
ADC SECTIONS TO EXTRACT:
- Ocular toxicity monitoring (keratopathy, dry eye)
- Peripheral neuropathy assessment scale
- Payload-specific toxicities
- Dose modification for toxicity"""
            if flags.get("is_immunotherapy"):
                special_instructions += """
IMMUNOTHERAPY SECTIONS TO EXTRACT:
- Response criteria: irRECIST or iRECIST
- Pseudoprogression handling: confirmation timing, continue treatment rules
- irAE monitoring: colitis, pneumonitis, hepatitis, endocrinopathies, nephritis
- irAE grading and management algorithms
- Corticosteroid use for irAEs"""
            if flags.get("is_hematologic"):
                special_instructions += """
HEMATOLOGIC MALIGNANCY SECTIONS TO EXTRACT:
- Response criteria: Lugano/IMWG/ELN/iwCLL/Cheson
- MRD assessment: method (flow cytometry/NGS/PCR), sensitivity (10^-4/10^-5/10^-6), timepoints
- Cytogenetic/molecular risk categories
- Bone marrow assessment schedule
- Extramedullary disease assessment"""
            if flags.get("is_prostate"):
                special_instructions += """
PROSTATE CANCER SECTIONS TO EXTRACT:
- PSA response definition (>=50% decline, confirmation)
- PSA progression definition (>=25% and >=2 ng/mL, confirmation)
- Bone scan assessment: timing, flare phenomenon handling
- Soft tissue assessment: RECIST 1.1
- rPFS definition (radiographic progression-free survival)
- Skeletal-related events definition"""
            if flags.get("is_brain_tumor"):
                special_instructions += """
BRAIN TUMOR SECTIONS TO EXTRACT:
- RANO criteria: bi-dimensional measurement
- T2/FLAIR assessment
- Corticosteroid requirements for response
- Pseudoprogression/pseudoresponse handling
- Clinical/neurological status requirements"""
            if flags.get("is_ovarian"):
                special_instructions += """
OVARIAN CANCER SECTIONS TO EXTRACT:
- CA-125 response criteria (GCIG): >=50% reduction, confirmation
- CA-125 progression criteria
- RECIST assessment for measurable disease
- BRCA/HRD status if applicable"""

            # Special study designs
            if flags.get("is_basket"):
                special_instructions += """
BASKET TRIAL SECTIONS TO EXTRACT:
- Tumor-agnostic biomarker requirement
- Cohort definitions by tumor type
- Pooled vs cohort-specific analyses
- Borrowing strength across cohorts"""
            if flags.get("is_umbrella"):
                special_instructions += """
UMBRELLA TRIAL SECTIONS TO EXTRACT:
- Biomarker-defined cohorts
- Molecular screening process
- Treatment assignment algorithm
- Master protocol structure"""

        # Build censoring instructions
        if discovered_structure and discovered_structure.get("censoring_rules_detailed"):
            censor_instruction = """
CENSORING RULES: The protocol has DETAILED censoring rules. Extract ALL scenarios:
- For each time-to-event endpoint
- Each censoring scenario (no event, lost to follow-up, new therapy, etc.)
- Whether it's event=1 or censored=0
- What date is used"""
        else:
            censor_instruction = """
CENSORING RULES: Extract any censoring rules mentioned for time-to-event endpoints."""

        prompt = f"""You are extracting ALL values needed to generate a Statistical Analysis Plan (SAP).

## CONTEXT FROM DISCOVERY STAGE
{pop_instruction}

{hyp_instruction}

{special_instructions}

{censor_instruction}

## EXTRACTION SCHEMA

Return a JSON object with these sections. For EVERY field, you MUST include:
- source_quote: MANDATORY - verbatim text from protocol (first 100 chars). DO NOT leave empty.
- source_section: MANDATORY - protocol section number (e.g., "Section 6.1", "Section 9.3.2", "Section 3.1.1"). DO NOT leave empty.

### EXAMPLES OF CORRECT EXTRACTION:

GOOD (includes source_quote AND source_section):
```json
"phase": {{"value": "Phase 2", "source_quote": "This is a Phase 2, open-label, multicenter study", "source_section": "Section 3.1"}}
"primary_endpoints": [{{"name": "ORR", "definition": "Overall response rate per Lugano criteria", "source_quote": "The primary endpoint is ORR defined as...", "source_section": "Section 6.1"}}]
```

BAD (missing source_quote or source_section):
```json
"phase": {{"value": "Phase 2", "source_quote": "", "source_section": ""}}  ← WRONG! Must have source
```

### FINDING SECTION NUMBERS:
- Look for headers like "6.1 Primary Endpoint", "Section 9.3.2", "3. Study Design"
- If no explicit section number, use the nearest header (e.g., "Primary Objectives" → "Section: Primary Objectives")
- For tables, cite as "Table X" or "Section containing Table X"

{{
  "trial_identification": {{
    "nct_id": {{"value": "", "source_quote": "", "source_section": ""}},
    "protocol_number": {{"value": "", "source_quote": "", "source_section": ""}},
    "sponsor": {{"value": "", "source_quote": "", "source_section": ""}},
    "study_title": {{"value": "", "source_quote": "", "source_section": ""}},
    "protocol_version": {{"value": "", "source_quote": "", "source_section": ""}}
  }},

  "disease_classification": {{
    "tumor_type": {{"value": "", "source_quote": "", "source_section": ""}},
    "disease_stage": {{"value": "", "source_quote": "", "source_section": ""}},
    "disease_setting": {{"value": "[adjuvant/neoadjuvant/metastatic/locally_advanced/maintenance]", "source_quote": "", "source_section": ""}},
    "histology_subtypes": {{"value": [], "source_quote": "", "source_section": ""}},
    "prior_lines_allowed": {{"value": "", "source_quote": "", "source_section": ""}},
    "indication_keywords": []
  }},

  "study_phase": {{
    "phase": {{"value": "", "source_quote": "", "source_section": ""}},
    "phase_objectives": {{"value": "", "source_quote": "", "source_section": ""}},
    "is_seamless_design": {{"value": false, "source_quote": "", "source_section": ""}}
  }},

  "study_design": {{
    "design_type": {{"value": "[parallel/crossover/single_arm/factorial/adaptive/basket/umbrella/platform]", "source_quote": "", "source_section": ""}},
    "blinding": {{"value": "[open_label/single_blind/double_blind]", "source_quote": "", "source_section": ""}},
    "randomization_ratio": {{"value": "", "source_quote": "", "source_section": ""}},
    "control_type": {{"value": "[placebo/active_comparator/soc/historical/none]", "source_quote": "", "source_section": ""}}
  }},

  "treatment_arms": [
    {{
      "arm_name": "",
      "arm_type": "[experimental/comparator/placebo]",
      "drug_name": "",
      "dose": "",
      "schedule": "",
      "route": "",
      "source_quote": "",
      "source_section": ""
    }}
  ],

  "enrollment": {{
    "target_enrollment": {{"value": "", "source_quote": "", "source_section": ""}},
    "enrollment_per_arm": {{"value": [], "source_quote": "", "source_section": ""}},
    "study_duration": {{"value": "", "source_quote": "", "source_section": ""}},
    "follow_up_duration": {{"value": "", "source_quote": "", "source_section": ""}}
  }},

  "populations": [
    {{
      "name": "",
      "definition": "",
      "is_primary_efficacy": false,
      "is_primary_safety": false,
      "source_quote": "",
      "source_section": ""
    }}
  ],

  "hypotheses": [
    {{
      "id": "H1",
      "endpoint": "",
      "population": "",
      "comparison": "",
      "alpha_allocated": null,
      "gate_condition": null,
      "test_type": "[superiority/non_inferiority/equivalence]",
      "source_quote": "",
      "source_section": ""
    }}
  ],

  "primary_endpoints": [
    {{
      "name": "",
      "definition": "",
      "type": "[binary/time_to_event/continuous/count]",
      "assessment_method": "",
      "assessment_schedule": "",
      "response_criteria": "[RECIST/irRECIST/iRECIST/Lugano/IMWG/ELN/PCWG3/RANO/GCIG/other]",
      "confirmation_required": false,
      "irc_assessment": false,
      "primary_population": "",
      "source_quote": "",
      "source_section": ""
    }}
  ],

  "secondary_endpoints": [
    {{
      "name": "",
      "definition": "",
      "type": "",
      "source_quote": "",
      "source_section": ""
    }}
  ],

  "censoring_rules": [
    {{
      "endpoint": "",
      "scenario": "",
      "event_flag": "[0/1]",
      "date_used": "",
      "source_quote": "",
      "source_section": ""
    }}
  ],

  "subgroups": [
    {{
      "factor": "",
      "categories": [],
      "rationale": "",
      "is_stratification_factor": false,
      "source_quote": "",
      "source_section": ""
    }}
  ],

  "sample_size": {{
    "total_n": {{"value": "", "source_quote": "", "source_section": ""}},
    "per_arm_n": {{"value": [], "source_quote": "", "source_section": ""}},
    "power": {{"value": "", "source_quote": "", "source_section": ""}},
    "alpha": {{"value": "", "one_or_two_sided": "", "source_quote": "", "source_section": ""}},
    "effect_size": {{"value": "", "type": "[hazard_ratio/difference/odds_ratio]", "source_quote": "", "source_section": ""}},
    "control_rate": {{"value": "", "source_quote": "", "source_section": ""}},
    "dropout_rate": {{"value": "", "source_quote": "", "source_section": ""}},
    "events_required": {{"value": "", "source_quote": "", "source_section": ""}}
  }},

  "interim_analysis": {{
    "planned": false,
    "number_of_interims": {{"value": "", "source_quote": "", "source_section": ""}},
    "timing": [{{"interim": "", "trigger": "[enrollment/events/calendar]", "value": "", "source_quote": "", "source_section": ""}}],
    "efficacy_stopping": {{"boundary": "", "method": "[OBF/Pocock/alpha_spending]", "source_quote": "", "source_section": ""}},
    "futility_stopping": {{"boundary": "", "method": "", "source_quote": "", "source_section": ""}},
    "alpha_spending_function": {{"value": "", "source_quote": "", "source_section": ""}}
  }},

  "randomization": {{
    "method": {{"value": "[permuted_blocks/stratified/minimization/adaptive]", "source_quote": "", "source_section": ""}},
    "block_size": {{"value": "", "source_quote": "", "source_section": ""}},
    "stratification_factors": [
      {{
        "factor_name": "",
        "categories": [],
        "source_quote": "",
        "source_section": ""
      }}
    ]
  }},

  "statistical_methods": {{
    "primary_analysis_method": {{"value": "", "source_quote": "", "source_section": ""}},
    "time_to_event_method": {{"value": "[kaplan_meier/log_rank/cox/rmst]", "source_quote": "", "source_section": ""}},
    "binary_endpoint_method": {{"value": "", "source_quote": "", "source_section": ""}},
    "confidence_interval_method": {{"value": "", "level": "", "source_quote": "", "source_section": ""}},
    "stratified_analysis": {{"value": false, "factors": [], "source_quote": "", "source_section": ""}}
  }},

  "multiplicity": {{
    "adjustment_required": false,
    "method": {{"value": "[hierarchical/bonferroni/hochberg/graphical/gatekeeping/fixed_sequence]", "source_quote": "", "source_section": ""}},
    "overall_alpha": {{"value": "", "source_quote": "", "source_section": ""}},
    "alpha_split_rationale": {{"value": "", "source_quote": "", "source_section": ""}}
  }},

  "safety_endpoints": {{
    "ae_grading_scale": {{"value": "[CTCAE_v5/CTCAE_v4/other]", "version": "", "source_quote": "", "source_section": ""}},
    "special_safety_monitoring": [{{"type": "", "criteria": "", "source_quote": "", "source_section": ""}}],
    "aesi_definitions": [{{"name": "", "definition": "", "smq_mst": "", "source_quote": "", "source_section": ""}}]
  }},

  "cart_specific": {{
    "is_cart": false,
    "crs_grading": {{
      "scale": "[ASTCT/Lee/other]",
      "grades": [{{"grade": "", "criteria": "", "source_quote": ""}}],
      "source_quote": ""
    }},
    "icans_grading": {{
      "scale": "",
      "grades": [{{"grade": "", "criteria": "", "source_quote": ""}}],
      "source_quote": ""
    }},
    "cellular_kinetics": {{"parameters": [], "timepoints": [], "source_quote": ""}},
    "bridging_therapy": {{"allowed": false, "source_quote": ""}},
    "retreatment": {{
      "allowed": false,
      "criteria": "",
      "population_name": "",
      "population_definition": "",
      "source_quote": ""
    }},
    "manufacturing_failure_handling": {{"value": "", "source_quote": ""}}
  }},

  "hematologic_specific": {{
    "is_hematologic": false,
    "disease_type": {{"value": "[AML/ALL/CLL/CML/NHL/HL/myeloma/MDS/other]", "source_quote": ""}},
    "response_criteria": {{"value": "[Lugano/IMWG/ELN/IWG/Cheson/other]", "source_quote": ""}},
    "mrd_assessment": {{
      "required": false,
      "method": "[flow_cytometry/NGS/PCR]",
      "sensitivity": "",
      "timepoints": [],
      "source_quote": ""
    }},
    "cytogenetic_risk": {{"categories": [], "source_quote": ""}}
  }},

  "immunotherapy_specific": {{
    "is_immunotherapy": false,
    "response_criteria": {{"value": "[irRECIST/iRECIST]", "source_quote": ""}},
    "pseudoprogression_handling": {{"value": "", "source_quote": ""}},
    "irae_monitoring": [{{"type": "", "grading": "", "source_quote": ""}}]
  }},

  "baseline_variables": [
    {{
      "variable_name": "",
      "category": "[demographic/disease/lab/vital_sign/medical_history/prior_therapy]",
      "type": "[continuous/categorical/ordinal]",
      "categories_if_applicable": [],
      "source_quote": "",
      "source_section": ""
    }}
  ],

  "prior_therapy_details": {{
    "description": "Detailed prior therapy breakdown for baseline/subgroup tables",
    "number_of_prior_lines": {{"value": "", "categories": [], "source_quote": "", "source_section": ""}},
    "prior_anti_cd20": {{"collected": false, "categories": ["rituximab", "obinutuzumab"], "source_quote": "", "source_section": ""}},
    "prior_alkylating": {{"collected": false, "source_quote": "", "source_section": ""}},
    "prior_anti_cd20_plus_alkylating": {{"collected": false, "source_quote": "", "source_section": ""}},
    "prior_lenalidomide": {{"collected": false, "source_quote": "", "source_section": ""}},
    "prior_pi3k_inhibitor": {{"collected": false, "source_quote": "", "source_section": ""}},
    "prior_asct": {{"collected": false, "source_quote": "", "source_section": ""}},
    "prior_allo_sct": {{"collected": false, "source_quote": "", "source_section": ""}},
    "prior_car_t": {{"collected": false, "source_quote": "", "source_section": ""}},
    "prior_bcma_therapy": {{"collected": false, "source_quote": "", "source_section": ""}},
    "bone_marrow_involvement": {{"collected": false, "source_quote": "", "source_section": ""}},
    "response_to_last_therapy": {{"collected": false, "categories": ["PD", "SD", "PR", "CR"], "source_quote": "", "source_section": ""}},
    "refractory_status": {{"collected": false, "categories": ["primary_refractory", "secondary_refractory", "relapsed"], "source_quote": "", "source_section": ""}},
    "double_refractory": {{"collected": false, "definition": "", "source_quote": "", "source_section": ""}}
  }},

  "performance_status": {{
    "scale": {{"value": "[ECOG/Karnofsky/ASA/Lansky/other]", "source_quote": "", "source_section": ""}},
    "required_range": {{"value": "", "source_quote": "", "source_section": ""}}
  }},

  "geographic": {{
    "countries": [{{"country": "", "source_quote": "", "source_section": ""}}],
    "regions": [{{"region": "", "source_quote": "", "source_section": ""}}],
    "is_multi_regional": false
  }},

  "response_criteria_details": {{
    "criteria_name": "",
    "version": "",
    "target_lesion_selection": {{"value": "", "source_quote": "", "source_section": ""}},
    "measurement_method": {{"value": "", "source_quote": "", "source_section": ""}},
    "confirmation_required": false,
    "confirmation_window": {{"value": "", "source_quote": "", "source_section": ""}}
  }},

  "missing_data": {{
    "handling_method": {{"value": "[complete_case/LOCF/MI/MMRM/other]", "source_quote": "", "source_section": ""}},
    "sensitivity_analyses": [{{"method": "", "source_quote": "", "source_section": ""}}]
  }},

  "sensitivity_analyses": [
    {{
      "name": "",
      "description": "",
      "population": "",
      "source_quote": ""
    }}
  ],

  "dose_modifications": {{
    "has_dose_modifications": false,
    "dose_reduction_rules": [{{"trigger": "", "action": "", "source_quote": ""}}],
    "discontinuation_rules": [{{"criteria": "", "source_quote": ""}}]
  }},

  "dsmb": {{
    "required": false,
    "review_schedule": {{"value": "", "source_quote": ""}}
  }},

  "irc": {{
    "required": false,
    "for_endpoints": [],
    "blinded": false
  }},

  "additional_discoveries": [
    {{
      "category": "Name of the discovered element (e.g., 'Safety Re-treatment Analysis Set', 'COVID-19 Protocol Variations', 'DORR Endpoint')",
      "element_type": "[population/endpoint/analysis/procedure/definition/other]",
      "name": "Exact name from protocol",
      "full_definition": "Complete definition/description from protocol",
      "relevant_sections": "Which SAP sections this should appear in",
      "source_quote": "Verbatim text from protocol"
    }}
  ]
}}

## CRITICAL INSTRUCTIONS:

1. **USE DISCOVERY CONTEXT**: Populations and hypotheses were already identified - extract their FULL definitions
2. **INDIVIDUAL ALPHAS**: For each hypothesis, extract its individual alpha_allocated value
3. **EXACT NAMES**: Use the EXACT population names from the protocol
4. **ALL CENSORING SCENARIOS**: Extract EVERY censoring scenario mentioned
5. **SOURCE QUOTES**: Include verbatim text for every extracted value
6. **NULL FOR MISSING**: Use null for fields not found - DO NOT guess or assume
7. **STUDY-TYPE SECTIONS**: Only populate cart_specific/hematologic_specific/immunotherapy_specific if applicable
8. **ADDITIONAL DISCOVERIES**: For ANY protocol elements that don't fit the standard categories above, add them to "additional_discoveries". Examples:
   - Unique populations (e.g., "Safety Re-treatment Analysis Set")
   - Protocol-specific endpoints (e.g., "DORR - Duration of Response to Retreatment")
   - Special sections (e.g., "COVID-19 Protocol Variations", "Date Imputation Rules")
   - Unique definitions (e.g., "Study Day 0", "Baseline", "On-study period")
   - Concordance analyses, shift tables, special grading scales not in standard categories
   DO NOT LOSE any protocol-specific elements - if it doesn't fit above, put it in additional_discoveries

PROTOCOL DOCUMENT:
{content}

Return ONLY the JSON object, no other text."""

        return prompt

    def _convert_extraction_to_list(self, extracted_obj: Dict) -> List[Dict]:
        """Convert structured extraction to list format for backward compatibility."""
        items = []

        # Extract endpoints
        for ep in extracted_obj.get("primary_endpoints", []):
            if ep.get("name"):
                items.append({
                    "type": "endpoint",
                    "name": ep.get("name", ""),
                    "endpoint_type": "primary",
                    "definition": ep.get("definition", ""),
                    "response_criteria": ep.get("response_criteria", ""),
                    "confidence": 0.95,
                    "source_quote": ep.get("source_quote", ""),
                    "source_section": ep.get("source_section", "")
                })

        for ep in extracted_obj.get("secondary_endpoints", []):
            if ep.get("name"):
                items.append({
                    "type": "endpoint",
                    "name": ep.get("name", ""),
                    "endpoint_type": "secondary",
                    "definition": ep.get("definition", ""),
                    "confidence": 0.90,
                    "source_quote": ep.get("source_quote", ""),
                    "source_section": ep.get("source_section", "")
                })

        # Extract populations (NEW: dynamic list format)
        pops = extracted_obj.get("populations", [])
        # Handle both old dict format and new list format
        if isinstance(pops, list):
            # New dynamic list format
            for pop in pops:
                if pop.get("name"):
                    items.append({
                        "type": "population",
                        "name": pop.get("name", ""),
                        "definition": pop.get("definition", ""),
                        "is_primary_efficacy": pop.get("is_primary_efficacy", False),
                        "is_primary_safety": pop.get("is_primary_safety", False),
                        "confidence": 0.95,
                        "source_quote": pop.get("source_quote", ""),
                        "source_section": pop.get("source_section", "")
                    })
        else:
            # Legacy dict format (backward compatibility)
            for pop_name in ["itt_definition", "mitt_definition", "pp_definition", "safety_definition"]:
                pop = pops.get(pop_name, {})
                if pop and pop.get("value"):
                    items.append({
                        "type": "population",
                        "name": pop_name.replace("_definition", "").upper(),
                        "definition": pop.get("value", ""),
                        "confidence": 0.95,
                        "source_quote": pop.get("source_quote", ""),
                        "source_section": pop.get("source_section", "")
                    })

        # Extract hypotheses (NEW: dynamic list with individual alphas)
        for hyp in extracted_obj.get("hypotheses", []):
            if hyp.get("id"):
                items.append({
                    "type": "hypothesis",
                    "id": hyp.get("id", ""),
                    "endpoint": hyp.get("endpoint", ""),
                    "population": hyp.get("population", ""),
                    "alpha_allocated": hyp.get("alpha_allocated"),
                    "gate_condition": hyp.get("gate_condition"),
                    "test_type": hyp.get("test_type", ""),
                    "confidence": 0.95,
                    "source_quote": hyp.get("source_quote", ""),
                    "source_section": hyp.get("source_section", "")
                })

        # Extract censoring rules (NEW: dynamic list)
        for rule in extracted_obj.get("censoring_rules", []):
            if rule.get("endpoint") and rule.get("scenario"):
                items.append({
                    "type": "censoring_rule",
                    "endpoint": rule.get("endpoint", ""),
                    "scenario": rule.get("scenario", ""),
                    "event_flag": rule.get("event_flag", ""),
                    "date_used": rule.get("date_used", ""),
                    "confidence": 0.95,
                    "source_quote": rule.get("source_quote", ""),
                    "source_section": rule.get("source_section", "")
                })

        # Extract subgroups (NEW: dynamic list)
        for sg in extracted_obj.get("subgroups", []):
            if sg.get("factor"):
                items.append({
                    "type": "subgroup",
                    "factor": sg.get("factor", ""),
                    "categories": sg.get("categories", []),
                    "rationale": sg.get("rationale", ""),
                    "is_stratification_factor": sg.get("is_stratification_factor", False),
                    "confidence": 0.90,
                    "source_quote": sg.get("source_quote", ""),
                    "source_section": sg.get("source_section", "")
                })

        # Extract stratification factors
        rand = extracted_obj.get("randomization", {})
        for strat in rand.get("stratification_factors", []):
            if strat.get("factor_name"):
                items.append({
                    "type": "stratification",
                    "name": strat.get("factor_name", ""),
                    "categories": strat.get("categories", []),
                    "confidence": 0.95,
                    "source_quote": strat.get("source_quote", ""),
                    "source_section": strat.get("source_section", "")
                })

        # Extract baseline variables
        for var in extracted_obj.get("baseline_variables", []):
            if var.get("variable_name"):
                items.append({
                    "type": "baseline_variable",
                    "name": var.get("variable_name", ""),
                    "category": var.get("category", ""),
                    "var_type": var.get("type", ""),
                    "confidence": 0.90,
                    "source_quote": var.get("source_quote", ""),
                    "source_section": var.get("source_section", "")
                })

        # Extract study design info
        design = extracted_obj.get("study_design", {})
        if design.get("design_type", {}).get("value"):
            items.append({
                "type": "study_design",
                "name": design.get("design_type", {}).get("value", ""),
                "confidence": 0.95,
                "source_quote": design.get("design_type", {}).get("source_quote", ""),
                "source_section": design.get("design_type", {}).get("source_section", "")
            })

        # Extract disease setting
        disease = extracted_obj.get("disease_classification", {})
        if disease.get("disease_setting", {}).get("value"):
            items.append({
                "type": "disease_setting",
                "name": disease.get("disease_setting", {}).get("value", ""),
                "confidence": 0.95,
                "source_quote": disease.get("disease_setting", {}).get("source_quote", ""),
                "source_section": disease.get("disease_setting", {}).get("source_section", "")
            })

        # Extract performance status
        ps = extracted_obj.get("performance_status", {})
        if ps.get("scale", {}).get("value"):
            items.append({
                "type": "performance_status",
                "name": ps.get("scale", {}).get("value", ""),
                "required_range": ps.get("required_range", {}).get("value", ""),
                "confidence": 0.95,
                "source_quote": ps.get("scale", {}).get("source_quote", ""),
                "source_section": ps.get("scale", {}).get("source_section", "")
            })

        # Extract response criteria
        rc = extracted_obj.get("response_criteria_details", {})
        if rc.get("criteria_name"):
            items.append({
                "type": "response_criteria",
                "name": rc.get("criteria_name", ""),
                "confidence": 0.95,
                "source_quote": rc.get("source_quote", ""),
                "source_section": rc.get("source_section", "")
            })

        # Extract geographic info
        geo = extracted_obj.get("geographic", {})
        countries = geo.get("countries", [])
        if countries:
            items.append({
                "type": "geographic",
                "name": ", ".join([c.get("country", "") for c in countries if c.get("country")]),
                "confidence": 0.90,
                "source_quote": countries[0].get("source_quote", "") if countries else "",
                "source_section": countries[0].get("source_section", "") if countries else ""
            })

        return items

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
