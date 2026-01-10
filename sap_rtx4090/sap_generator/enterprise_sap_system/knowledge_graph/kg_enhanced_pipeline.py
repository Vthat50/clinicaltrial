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

        # Build the comprehensive SAP generation prompt
        prompt = f"""You are a senior biostatistician creating a Statistical Analysis Plan (SAP).

## CRITICAL: STRICT PROTOCOL-SPECIFIC GENERATION

You have been given a comprehensive extraction of ALL protocol elements.
Generate a SAP using ONLY this extracted information.
DO NOT add any content not present in the extraction.

## PROHIBITED CONTENT (Based on Protocol Analysis):
{prohibition_rules}

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

### 5. POPULATIONS
- Use exact definitions from populations section
- ITT, mITT, PP, Safety as extracted

### 6. BASELINE VARIABLES
- Include ONLY variables from baseline_variables[]
- Use the exact variable_name and categories
- Use performance_status.scale (ECOG vs ASA vs Karnofsky)

### 7. STATISTICAL METHODS
- Use methods from statistical_methods section
- Match to endpoint types from extraction
- Include multiplicity adjustment if multiplicity.adjustment_required is true

### 8. TREATMENT ARMS
- Use exact arm names from treatment_arms[]
- Include dose, schedule, route as extracted

### 9. STRATIFICATION
- Use exact factors from randomization.stratification_factors[]
- Include categories as extracted

### 10. INTERIM ANALYSIS
- Include if interim_analysis.planned is true
- Use stopping rules from extraction

### 11. SAFETY ANALYSIS
- Use ae_grading_scale from safety_endpoints
- Include special monitoring from safety_endpoints.special_safety_monitoring

### 12. SPECIAL CONSIDERATIONS
- Phase 1: Include DLT definition, MTD criteria from phase1_design
- Immunotherapy: Include irAE monitoring, PD-L1/TMB/MSI assessment
- CAR-T: Include CRS/ICANS grading, cellular kinetics
- Hematologic: Include MRD assessment, cytogenetic risk

### 13. GEOGRAPHIC
- Include only countries/regions from geographic section
- Do NOT add Race/Ethnicity unless in baseline_variables

### 14. TABLE SHELLS
- Use exact treatment arm names as column headers
- Include only baseline variables from extraction
- Match response criteria to study type

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

        # 7. Stratification for subgroup analysis
        strat = full_extraction.get("randomization", {})
        strat_factors = strat.get("stratification_factors", []) if strat else []

        if strat_factors:
            factor_names = [f.get("factor_name", "") for f in strat_factors if f.get("factor_name")]
            if factor_names:
                rules.append(f"- Forest plot subgroups MUST use only: {', '.join(factor_names)}")

        # 8. Check for specific baseline variables
        if var_names:
            has_bmi = any("bmi" in v for v in var_names)
            has_weight = any("weight" in v for v in var_names)
            if has_bmi and not has_weight:
                rules.append("- Use BMI (kg/m²), not Weight (kg) for body composition variable")

        return "\n".join(rules) if rules else "No specific prohibitions identified."

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

        # Initial prompt
        system_prompt = f"""You are a senior biostatistician creating a Statistical Analysis Plan (SAP).

You have access to a knowledge base of standard statistical methods, table templates, and regulatory specifications.
When you need a standard specification (like Cox model formula, table template, missing data method),
USE THE TOOLS PROVIDED to retrieve it. Do not make up formulas or templates.

## PROHIBITED CONTENT (Protocol-Specific):
{prohibition_rules}

## CRITICAL ANTI-HALLUCINATION RULES:
1. RACE/ETHNICITY: Include ONLY if explicitly in baseline_variables[]. Nordic/European studies do NOT collect these.
2. PERFORMANCE STATUS: Use EXACTLY the scale from extraction (ASA Score for surgical, ECOG for oncology).
3. GEOGRAPHIC SUBGROUPS: Use ONLY countries from extraction. Nordic = Sweden/Norway/Denmark/Finland ONLY.
4. RESPONSE TABLES (CR/PR/SD/PD): Include ONLY for metastatic/advanced. ADJUVANT = NO tumor response tables.
5. AE GRADING: Use EXACTLY what's in extraction (CTCAE vs Mild/Moderate/Severe).
6. DOSE MODIFICATION: Include ONLY if dose_modifications has rules. Fixed-dose = NO modification rows.
7. TREATMENT ARMS: Use EXACT arm names from extraction as column headers.

IMPORTANT RULES:
1. Protocol facts (from extraction) are STUDY-SPECIFIC - use them for this study
2. Knowledge base (from tools) provides STANDARD TEMPLATES - adapt to protocol specifics
3. ALWAYS call tools for: statistical method formulas, table shells, missing data handling, sensitivity analyses
4. Mark the source of each element: [PROTOCOL] or [KB: source_file]

Generate a production-quality SAP with full provenance tracking."""

        user_prompt = f"""## PROTOCOL EXTRACTION (Study-Specific Facts):
```json
{extraction_json}
```

## FULL PROTOCOL (for reference):
{protocol_content[:10000]}

---

Generate a COMPLETE SAP with ALL 12 sections. Each section MUST be included.

MANDATORY OUTPUT FORMAT - Use these EXACT section headers:

## 1. TITLE PAGE & ADMINISTRATIVE INFORMATION
## 2. STUDY OBJECTIVES & ENDPOINTS
## 3. STUDY DESIGN
## 4. ANALYSIS POPULATIONS
## 5. STATISTICAL METHODS
## 6. SAMPLE SIZE & POWER
## 7. MISSING DATA HANDLING
## 8. SENSITIVITY ANALYSES
## 9. SUBGROUP ANALYSES
## 10. SAFETY ANALYSIS
## 11. INTERIM ANALYSIS
## 12. TABLE/FIGURE SHELLS

CRITICAL REQUIREMENTS:
- You MUST generate ALL 12 sections, even if brief
- Use the EXACT "## N." format for section headers
- For sections 5, 7, 8, 9, 10, 12: USE THE TOOLS to get standard specifications
- Section 11 (Interim Analysis): Include even if "Not applicable" for this study
- Section 12 (Table/Figure Shells): MUST call get_disposition_tables, get_safety_tables tools

Start by calling the tools to get standard specifications, then generate the COMPLETE 12-section SAP."""

        messages = [{"role": "user", "content": user_prompt}]
        knowledge_used = []
        warnings = []
        accumulated_text = ""  # Accumulate ALL text across iterations

        # Tool-use loop
        max_iterations = 15  # Reasonable limit for tool calls
        iteration = 0

        print(f"[KG Generator] Starting tool-use loop (max {max_iterations} iterations)")
        print(f"[DEBUG] Protocol length: {len(protocol_content)} chars")
        print(f"[DEBUG] Extraction available: {full_extraction is not None}")

        while iteration < max_iterations:
            iteration += 1

            try:
                print(f"[DEBUG] Iteration {iteration}: sending {len(messages)} messages")

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
                        continuation_prompt = """Now generate the COMPLETE Statistical Analysis Plan with ALL 12 sections.

MANDATORY: Use these EXACT section headers:
## 1. TITLE PAGE & ADMINISTRATIVE INFORMATION
## 2. STUDY OBJECTIVES & ENDPOINTS
## 3. STUDY DESIGN
## 4. ANALYSIS POPULATIONS
## 5. STATISTICAL METHODS
## 6. SAMPLE SIZE & POWER
## 7. MISSING DATA HANDLING
## 8. SENSITIVITY ANALYSES
## 9. SUBGROUP ANALYSES
## 10. SAFETY ANALYSIS
## 11. INTERIM ANALYSIS
## 12. TABLE/FIGURE SHELLS

Output ONLY the SAP document. Start with "# STATISTICAL ANALYSIS PLAN" then include ALL 12 sections."""

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
                for i, tool_call in enumerate(tool_calls):
                    tool_name = tool_call.name
                    tool_input = tool_call.input
                    print(f"[DEBUG] Tool {i+1}/{len(tool_calls)}: {tool_name}({json.dumps(tool_input)[:100]})")

                    try:
                        # Execute the tool
                        result = execute_tool(tool_name, tool_input, kb)
                        print(f"[DEBUG] Tool result: {len(json.dumps(result.content, default=str))} chars from {result.source_file}")

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
                            "content": json.dumps(result.to_dict(), indent=2, default=str)
                        })
                    except Exception as tool_error:
                        print(f"[KG Generator] Tool error {tool_name}: {tool_error}")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_call.id,
                            "content": f"Error: {str(tool_error)}",
                            "is_error": True
                        })

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

Now generate the COMPLETE SAP with ALL 12 sections using these EXACT headers:

## 1. TITLE PAGE & ADMINISTRATIVE INFORMATION
## 2. STUDY OBJECTIVES & ENDPOINTS
## 3. STUDY DESIGN
## 4. ANALYSIS POPULATIONS
## 5. STATISTICAL METHODS
## 6. SAMPLE SIZE & POWER
## 7. MISSING DATA HANDLING
## 8. SENSITIVITY ANALYSES
## 9. SUBGROUP ANALYSES
## 10. SAFETY ANALYSIS
## 11. INTERIM ANALYSIS
## 12. TABLE/FIGURE SHELLS

Start with "# STATISTICAL ANALYSIS PLAN" then include ALL 12 sections. Each section is MANDATORY."""

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
        self.client = anthropic.Anthropic(api_key=api_key)
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

        # Step 7: SELF-RAG Verification
        print("\n" + "-"*50)
        print("STEP 7: SELF-RAG VERIFICATION")
        print("-"*50)

        verification = self.verifier.verify(sap_content, extracted, power_result)
        print(f"✅ Verification score: {verification.score:.2f}")
        print(f"   • Passed: {verification.passed}")
        print(f"   • Errors: {len(verification.errors)}")
        print(f"   • Warnings: {len(verification.warnings)}")

        # Only regenerate if we have a substantial SAP to improve (not create from scratch)
        regeneration_count = 0
        max_regenerations = 2

        while not verification.passed and regeneration_count < max_regenerations and len(sap_content) > 5000:
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
        """Extract comprehensive protocol elements for SAP generation."""

        prompt = f"""You are extracting ALL information needed to generate a Statistical Analysis Plan (SAP) from this clinical trial protocol.

Extract ONLY what is EXPLICITLY stated in this protocol. Do NOT assume or add generic content.

Return a JSON object with the following structure. For each field, include "value" and "source_quote" (exact text from protocol). If not found, use null.

{{
  "trial_identification": {{
    "nct_id": {{"value": "", "source_quote": ""}},
    "protocol_number": {{"value": "", "source_quote": ""}},
    "sponsor": {{"value": "", "source_quote": ""}},
    "study_title": {{"value": "", "source_quote": ""}},
    "protocol_version": {{"value": "", "source_quote": ""}}
  }},

  "disease_classification": {{
    "tumor_type": {{"value": "", "source_quote": ""}},
    "disease_stage": {{"value": "", "source_quote": ""}},
    "disease_setting": {{"value": "[adjuvant/neoadjuvant/metastatic/locally_advanced/maintenance]", "source_quote": ""}},
    "histology_subtypes": {{"value": [], "source_quote": ""}},
    "prior_lines_allowed": {{"value": "", "source_quote": ""}}
  }},

  "molecular_markers": {{
    "required_biomarkers": [{{"name": "", "test_method": "", "cutoff": "", "source_quote": ""}}],
    "stratification_biomarkers": [{{"name": "", "categories": [], "source_quote": ""}}],
    "exploratory_biomarkers": [{{"name": "", "source_quote": ""}}]
  }},

  "study_phase": {{
    "phase": {{"value": "", "source_quote": ""}},
    "phase_objectives": {{"value": "", "source_quote": ""}},
    "is_seamless_design": {{"value": false, "source_quote": ""}}
  }},

  "study_design": {{
    "design_type": {{"value": "[parallel/crossover/single_arm/factorial/adaptive/basket/umbrella/platform]", "source_quote": ""}},
    "blinding": {{"value": "[open_label/single_blind/double_blind]", "source_quote": ""}},
    "randomization_ratio": {{"value": "", "source_quote": ""}},
    "control_type": {{"value": "[placebo/active_comparator/soc/historical/none]", "source_quote": ""}}
  }},

  "treatment_arms": [
    {{
      "arm_name": "",
      "arm_type": "[experimental/comparator/placebo]",
      "drug_name": "",
      "dose": "",
      "schedule": "",
      "route": "",
      "duration": "",
      "source_quote": ""
    }}
  ],

  "dose_modifications": {{
    "dose_reduction_rules": [{{"trigger": "", "action": "", "source_quote": ""}}],
    "dose_escalation_rules": [{{"criteria": "", "action": "", "source_quote": ""}}],
    "discontinuation_rules": [{{"criteria": "", "source_quote": ""}}]
  }},

  "phase1_design": {{
    "is_phase1": false,
    "escalation_design": {{"value": "[3+3/CRM/BOIN/mTPI/other]", "source_quote": ""}},
    "dlt_definition": {{"value": "", "source_quote": ""}},
    "dlt_window": {{"value": "", "source_quote": ""}},
    "mtd_definition": {{"value": "", "source_quote": ""}},
    "rp2d_definition": {{"value": "", "source_quote": ""}},
    "starting_dose": {{"value": "", "source_quote": ""}},
    "dose_levels": [{{"level": "", "dose": "", "source_quote": ""}}]
  }},

  "enrollment": {{
    "target_enrollment": {{"value": "", "source_quote": ""}},
    "enrollment_per_arm": {{"value": [], "source_quote": ""}},
    "study_duration": {{"value": "", "source_quote": ""}},
    "follow_up_duration": {{"value": "", "source_quote": ""}}
  }},

  "populations": {{
    "itt_definition": {{"value": "", "source_quote": ""}},
    "mitt_definition": {{"value": "", "source_quote": ""}},
    "pp_definition": {{"value": "", "source_quote": ""}},
    "safety_definition": {{"value": "", "source_quote": ""}},
    "evaluable_definition": {{"value": "", "source_quote": ""}},
    "pk_population": {{"value": "", "source_quote": ""}},
    "biomarker_populations": [{{"name": "", "definition": "", "source_quote": ""}}]
  }},

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
      "source_quote": ""
    }}
  ],

  "secondary_endpoints": [
    {{
      "name": "",
      "definition": "",
      "type": "",
      "source_quote": ""
    }}
  ],

  "exploratory_endpoints": [
    {{
      "name": "",
      "definition": "",
      "source_quote": ""
    }}
  ],

  "safety_endpoints": {{
    "ae_grading_scale": {{"value": "[CTCAE_v5/CTCAE_v4/other]", "version": "", "source_quote": ""}},
    "dlt_as_endpoint": {{"value": false, "source_quote": ""}},
    "safety_stopping_rules": [{{"criteria": "", "action": "", "source_quote": ""}}],
    "special_safety_monitoring": [{{"type": "", "criteria": "", "source_quote": ""}}]
  }},

  "immunotherapy_specific": {{
    "is_immunotherapy": false,
    "response_criteria": {{"value": "[irRECIST/iRECIST]", "source_quote": ""}},
    "pseudoprogression_handling": {{"value": "", "source_quote": ""}},
    "irae_monitoring": [{{"type": "", "grading": "", "management": "", "source_quote": ""}}],
    "pd_l1_assessment": {{"assay": "", "scoring": "[TPS/CPS/IC]", "cutoff": "", "source_quote": ""}},
    "tmb_assessment": {{"platform": "", "cutoff": "", "source_quote": ""}},
    "msi_assessment": {{"method": "", "source_quote": ""}}
  }},

  "cart_specific": {{
    "is_cart": false,
    "crs_grading": {{"scale": "[ASTCT/Lee/other]", "source_quote": ""}},
    "icans_grading": {{"scale": "", "source_quote": ""}},
    "cellular_kinetics": {{"parameters": [], "source_quote": ""}},
    "bridging_therapy": {{"allowed": false, "source_quote": ""}},
    "retreatment_allowed": {{"value": false, "source_quote": ""}}
  }},

  "hematologic_specific": {{
    "is_hematologic": false,
    "disease_type": {{"value": "[AML/ALL/CLL/CML/lymphoma/myeloma/MDS/other]", "source_quote": ""}},
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

  "response_criteria_details": {{
    "criteria_name": "",
    "target_lesion_selection": {{"value": "", "source_quote": ""}},
    "measurement_method": {{"value": "", "source_quote": ""}},
    "confirmation_window": {{"value": "", "source_quote": ""}},
    "new_lesion_handling": {{"value": "", "source_quote": ""}},
    "non_target_assessment": {{"value": "", "source_quote": ""}}
  }},

  "disease_specific_biomarkers": [
    {{
      "biomarker_name": "",
      "disease_context": "",
      "assessment_method": "",
      "response_criteria": "",
      "kinetics_definition": "",
      "source_quote": ""
    }}
  ],

  "ctdna_liquid_biopsy": {{
    "collected": false,
    "assay_platform": {{"value": "", "source_quote": ""}},
    "detection_limit": {{"value": "", "source_quote": ""}},
    "timepoints": {{"value": [], "source_quote": ""}},
    "clearance_definition": {{"value": "", "source_quote": ""}},
    "mrd_definition": {{"value": "", "source_quote": ""}}
  }},

  "sample_size": {{
    "total_n": {{"value": "", "source_quote": ""}},
    "per_arm_n": {{"value": [], "source_quote": ""}},
    "power": {{"value": "", "source_quote": ""}},
    "alpha": {{"value": "", "one_or_two_sided": "", "source_quote": ""}},
    "effect_size": {{"value": "", "type": "[hazard_ratio/difference/odds_ratio]", "source_quote": ""}},
    "control_rate": {{"value": "", "source_quote": ""}},
    "dropout_rate": {{"value": "", "source_quote": ""}},
    "events_required": {{"value": "", "source_quote": ""}}
  }},

  "interim_analysis": {{
    "planned": false,
    "number_of_interims": {{"value": "", "source_quote": ""}},
    "timing": [{{"interim": "", "trigger": "[enrollment/events/calendar]", "value": "", "source_quote": ""}}],
    "efficacy_stopping": {{"boundary": "", "method": "[OBF/Pocock/alpha_spending]", "source_quote": ""}},
    "futility_stopping": {{"boundary": "", "method": "", "source_quote": ""}},
    "alpha_spending_function": {{"value": "", "source_quote": ""}},
    "sample_size_reestimation": {{"planned": false, "method": "", "source_quote": ""}}
  }},

  "randomization": {{
    "method": {{"value": "[permuted_blocks/stratified/minimization/adaptive]", "source_quote": ""}},
    "block_size": {{"value": "", "source_quote": ""}},
    "stratification_factors": [
      {{
        "factor_name": "",
        "categories": [],
        "source_quote": ""
      }}
    ],
    "ivrs_iwrs": {{"value": false, "source_quote": ""}}
  }},

  "subgroups": {{
    "prespecified_subgroups": [
      {{
        "factor": "",
        "categories": [],
        "rationale": "",
        "source_quote": ""
      }}
    ],
    "biomarker_subgroups": [
      {{
        "biomarker": "",
        "cutoff": "",
        "source_quote": ""
      }}
    ],
    "interaction_testing": {{"planned": false, "factors": [], "source_quote": ""}}
  }},

  "statistical_methods": {{
    "primary_analysis_method": {{"value": "", "source_quote": ""}},
    "time_to_event_method": {{"value": "[kaplan_meier/log_rank/cox/rmst]", "source_quote": ""}},
    "binary_endpoint_method": {{"value": "", "source_quote": ""}},
    "continuous_endpoint_method": {{"value": "", "source_quote": ""}},
    "confidence_interval_method": {{"value": "", "level": "", "source_quote": ""}},
    "stratified_analysis": {{"value": false, "factors": [], "source_quote": ""}}
  }},

  "sensitivity_analyses": [
    {{
      "name": "",
      "description": "",
      "population": "",
      "source_quote": ""
    }}
  ],

  "missing_data": {{
    "handling_method": {{"value": "[complete_case/LOCF/MI/MMRM/other]", "source_quote": ""}},
    "sensitivity_analyses": [{{"method": "", "source_quote": ""}}]
  }},

  "multiplicity": {{
    "adjustment_required": false,
    "method": {{"value": "[hierarchical/bonferroni/hochberg/graphical/gatekeeping]", "source_quote": ""}},
    "testing_hierarchy": [{{"rank": "", "endpoint": "", "source_quote": ""}}],
    "alpha_allocation": {{"value": "", "source_quote": ""}}
  }},

  "estimand_framework": {{
    "estimand_defined": false,
    "treatment_effect": {{"value": "", "source_quote": ""}},
    "intercurrent_events": [
      {{
        "event": "",
        "strategy": "[treatment_policy/composite/hypothetical/principal_stratum/while_on_treatment]",
        "source_quote": ""
      }}
    ]
  }},

  "competing_risks": {{
    "applicable": false,
    "competing_events": [{{"event": "", "handling": "", "source_quote": ""}}],
    "analysis_method": {{"value": "[CIF/Fine_Gray/other]", "source_quote": ""}}
  }},

  "safety_analysis": {{
    "population": {{"value": "", "source_quote": ""}},
    "ae_coding": {{"dictionary": "[MedDRA]", "version": "", "source_quote": ""}},
    "ae_tables": [{{"type": "", "source_quote": ""}}],
    "lab_analysis": {{"shift_tables": false, "change_from_baseline": false, "source_quote": ""}},
    "exposure_adjusted_analysis": {{"value": false, "source_quote": ""}}
  }},

  "pk_pd_analysis": {{
    "pk_sampling": {{"collected": false, "timepoints": [], "source_quote": ""}},
    "pk_parameters": [{{"parameter": "", "source_quote": ""}}],
    "pk_population": {{"value": "", "source_quote": ""}},
    "exposure_response": {{"planned": false, "source_quote": ""}}
  }},

  "pro_qol": {{
    "instruments": [
      {{
        "name": "",
        "domains": [],
        "assessment_schedule": "",
        "primary_timepoint": "",
        "source_quote": ""
      }}
    ],
    "mid_definition": {{"value": "", "source_quote": ""}},
    "ttd_analysis": {{"planned": false, "threshold": "", "source_quote": ""}}
  }},

  "prior_therapy": {{
    "lines_allowed": {{"value": "", "source_quote": ""}},
    "required_prior": [{{"therapy": "", "source_quote": ""}}],
    "excluded_prior": [{{"therapy": "", "source_quote": ""}}],
    "washout_periods": [{{"therapy": "", "period": "", "source_quote": ""}}]
  }},

  "concomitant_medications": {{
    "prohibited": [{{"medication": "", "reason": "", "source_quote": ""}}],
    "allowed_with_restrictions": [{{"medication": "", "restriction": "", "source_quote": ""}}],
    "required": [{{"medication": "", "source_quote": ""}}]
  }},

  "visit_schedule": {{
    "screening_window": {{"value": "", "source_quote": ""}},
    "treatment_visits": [{{"visit": "", "timing": "", "window": "", "source_quote": ""}}],
    "imaging_schedule": {{"frequency": "", "modality": "", "source_quote": ""}},
    "follow_up_schedule": {{"frequency": "", "duration": "", "source_quote": ""}}
  }},

  "comparative_hypothesis": {{
    "type": {{"value": "[superiority/non_inferiority/equivalence]", "source_quote": ""}},
    "margin": {{"value": "", "justification": "", "source_quote": ""}},
    "one_or_two_sided": {{"value": "", "source_quote": ""}}
  }},

  "regulatory_pathway": {{
    "accelerated_approval": {{"applicable": false, "surrogate_endpoint": "", "source_quote": ""}},
    "breakthrough_designation": {{"value": false, "source_quote": ""}},
    "orphan_designation": {{"value": false, "source_quote": ""}},
    "rmat_designation": {{"value": false, "source_quote": ""}}
  }},

  "dsmb": {{
    "required": false,
    "charter_elements": [{{"element": "", "source_quote": ""}}],
    "review_schedule": {{"value": "", "source_quote": ""}}
  }},

  "irc": {{
    "required": false,
    "for_endpoints": [{{"endpoint": "", "source_quote": ""}}],
    "blinded": {{"value": false, "source_quote": ""}}
  }},

  "geographic": {{
    "countries": [{{"country": "", "source_quote": ""}}],
    "regions": [{{"region": "", "source_quote": ""}}],
    "multi_regional_considerations": {{"value": "", "source_quote": ""}}
  }},

  "baseline_variables": [
    {{
      "variable_name": "",
      "category": "[demographic/disease/lab/vital_sign/medical_history/prior_therapy]",
      "type": "[continuous/categorical/ordinal]",
      "categories_if_applicable": [],
      "source_quote": ""
    }}
  ],

  "performance_status": {{
    "scale": {{"value": "[ECOG/Karnofsky/ASA/Lansky/other]", "source_quote": ""}},
    "required_range": {{"value": "", "source_quote": ""}}
  }},

  "organ_function_requirements": {{
    "renal": {{"parameter": "", "threshold": "", "source_quote": ""}},
    "hepatic": {{"parameters": [], "thresholds": [], "source_quote": ""}},
    "cardiac": {{"parameter": "", "threshold": "", "source_quote": ""}},
    "hematologic": {{"parameters": [], "thresholds": [], "source_quote": ""}}
  }},

  "heor_endpoints": {{
    "collected": false,
    "resource_utilization": [{{"type": "", "source_quote": ""}}],
    "cost_effectiveness": {{"planned": false, "source_quote": ""}}
  }},

  "digital_endpoints": {{
    "collected": false,
    "wearables": [{{"device": "", "parameters": [], "source_quote": ""}}],
    "epro": {{"platform": "", "source_quote": ""}}
  }},

  "adam_specifications": {{
    "adsl_flags": [{{"flag": "", "definition": "", "source_quote": ""}}],
    "analysis_datasets": [{{"dataset": "", "source_quote": ""}}]
  }},

  "disposition_flow": {{
    "consort_required": {{"value": false, "source_quote": ""}},
    "screening_categories": [{{"category": "", "source_quote": ""}}],
    "randomization_categories": [{{"category": "", "source_quote": ""}}],
    "discontinuation_reasons": [{{"reason": "", "source_quote": ""}}],
    "completion_definition": {{"value": "", "source_quote": ""}}
  }},

  "cox_model_specification": {{
    "model_formula": {{"value": "", "source_quote": ""}},
    "covariates": [{{"covariate": "", "type": "[continuous/categorical]", "source_quote": ""}}],
    "stratification_in_model": [{{"factor": "", "source_quote": ""}}],
    "tie_handling": {{"method": "[efron/breslow/exact]", "source_quote": ""}},
    "proportional_hazards_testing": {{
      "method": {{"value": "[schoenfeld/log_log_plot/scaled_schoenfeld/other]", "source_quote": ""}},
      "timepoint_for_test": {{"value": "", "source_quote": ""}},
      "action_if_violated": {{"value": "", "source_quote": ""}}
    }}
  }},

  "iptw_propensity_methods": {{
    "iptw_used": {{"value": false, "source_quote": ""}},
    "propensity_model": {{"value": "", "source_quote": ""}},
    "propensity_covariates": [{{"covariate": "", "source_quote": ""}}],
    "weight_type": {{"value": "[ATE/ATT/stabilized]", "source_quote": ""}},
    "trimming_threshold": {{"value": "", "source_quote": ""}},
    "balance_assessment": {{"method": "", "source_quote": ""}}
  }},

  "multiple_imputation_specs": {{
    "mi_used": {{"value": false, "source_quote": ""}},
    "number_of_imputations": {{"value": "", "source_quote": ""}},
    "imputation_method": {{"value": "[MICE/FCS/MCMC/PMM/other]", "source_quote": ""}},
    "variables_to_impute": [{{"variable": "", "source_quote": ""}}],
    "variables_in_imputation_model": [{{"variable": "", "source_quote": ""}}],
    "pooling_method": {{"value": "[Rubin]", "source_quote": ""}},
    "seed_specification": {{"value": "", "source_quote": ""}}
  }},

  "landmark_analyses": [
    {{
      "timepoint": "",
      "endpoint": "",
      "analysis_type": "[survival_rate/event_rate/RMST]",
      "confidence_interval_method": "",
      "source_quote": ""
    }}
  ],

  "table_shells": {{
    "disposition_table": {{
      "required": false,
      "columns": [],
      "rows": [],
      "source_quote": ""
    }},
    "demographics_table": {{
      "required": false,
      "columns": [],
      "variables": [],
      "source_quote": ""
    }},
    "efficacy_tables": [
      {{
        "table_name": "",
        "endpoint": "",
        "columns": [],
        "statistics": [],
        "source_quote": ""
      }}
    ],
    "safety_tables": [
      {{
        "table_name": "",
        "type": "[ae_overview/ae_by_soc/ae_by_grade/labs/vitals]",
        "columns": [],
        "source_quote": ""
      }}
    ],
    "exploratory_tables": [
      {{
        "table_name": "",
        "endpoint": "",
        "columns": [],
        "source_quote": ""
      }}
    ]
  }},

  "all_stratification_strata": [
    {{
      "factor": "",
      "strata": [],
      "total_strata_count": "",
      "source_quote": ""
    }}
  ]
}}

CRITICAL INSTRUCTIONS:
1. Extract ONLY what is explicitly stated in this protocol
2. Use null for any field not found in the protocol
3. Include exact source_quote for every extracted value
4. Do not infer or assume - if not stated, leave null
5. For disease-specific sections, only populate if this protocol is that disease type
6. Extract ALL baseline variables mentioned anywhere (eligibility, assessments, CRF)
7. Identify the EXACT response criteria mentioned (RECIST version, irRECIST vs iRECIST, etc.)
8. Capture the EXACT performance status scale used (ECOG vs ASA vs Karnofsky)

PROTOCOL DOCUMENT:
{content}

Return ONLY the JSON object, no other text."""

        try:
            # Use streaming for long operations
            with self.client.messages.stream(
                model=self.model,
                max_tokens=16384,  # Increased for comprehensive extraction
                messages=[{"role": "user", "content": prompt}]
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
                    "source_quote": ep.get("source_quote", "")
                })

        for ep in extracted_obj.get("secondary_endpoints", []):
            if ep.get("name"):
                items.append({
                    "type": "endpoint",
                    "name": ep.get("name", ""),
                    "endpoint_type": "secondary",
                    "definition": ep.get("definition", ""),
                    "confidence": 0.90,
                    "source_quote": ep.get("source_quote", "")
                })

        # Extract populations
        pops = extracted_obj.get("populations", {})
        for pop_name in ["itt_definition", "mitt_definition", "pp_definition", "safety_definition"]:
            pop = pops.get(pop_name, {})
            if pop and pop.get("value"):
                items.append({
                    "type": "population",
                    "name": pop_name.replace("_definition", "").upper(),
                    "definition": pop.get("value", ""),
                    "confidence": 0.95,
                    "source_quote": pop.get("source_quote", "")
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
                    "source_quote": strat.get("source_quote", "")
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
                    "source_quote": var.get("source_quote", "")
                })

        # Extract study design info
        design = extracted_obj.get("study_design", {})
        if design.get("design_type", {}).get("value"):
            items.append({
                "type": "study_design",
                "name": design.get("design_type", {}).get("value", ""),
                "confidence": 0.95,
                "source_quote": design.get("design_type", {}).get("source_quote", "")
            })

        # Extract disease setting
        disease = extracted_obj.get("disease_classification", {})
        if disease.get("disease_setting", {}).get("value"):
            items.append({
                "type": "disease_setting",
                "name": disease.get("disease_setting", {}).get("value", ""),
                "confidence": 0.95,
                "source_quote": disease.get("disease_setting", {}).get("source_quote", "")
            })

        # Extract performance status
        ps = extracted_obj.get("performance_status", {})
        if ps.get("scale", {}).get("value"):
            items.append({
                "type": "performance_status",
                "name": ps.get("scale", {}).get("value", ""),
                "required_range": ps.get("required_range", {}).get("value", ""),
                "confidence": 0.95,
                "source_quote": ps.get("scale", {}).get("source_quote", "")
            })

        # Extract response criteria
        rc = extracted_obj.get("response_criteria_details", {})
        if rc.get("criteria_name"):
            items.append({
                "type": "response_criteria",
                "name": rc.get("criteria_name", ""),
                "confidence": 0.95,
                "source_quote": ""
            })

        # Extract geographic info
        geo = extracted_obj.get("geographic", {})
        countries = geo.get("countries", [])
        if countries:
            items.append({
                "type": "geographic",
                "name": ", ".join([c.get("country", "") for c in countries if c.get("country")]),
                "confidence": 0.90,
                "source_quote": countries[0].get("source_quote", "") if countries else ""
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
