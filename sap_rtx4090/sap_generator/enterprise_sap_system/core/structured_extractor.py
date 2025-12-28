#!/usr/bin/env python3
"""
Structured Fact Extractor for Production SAP Generation
========================================================
Extracts ALL protocol facts as structured data using regex/rules.
NO LLM involved - pure deterministic extraction.

This is LAYER 1 of the production pipeline:
Protocol → StructuredFactExtractor → JSON Facts → LLM Generation → Validation
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from pydantic import BaseModel, Field
from enum import Enum


class RouteOfAdministration(str, Enum):
    IV = "intravenous"
    SC = "subcutaneous"
    IM = "intramuscular"
    ORAL = "oral"
    TOPICAL = "topical"
    INHALED = "inhaled"
    OTHER = "other"


class StudyPhase(str, Enum):
    PHASE_1 = "Phase 1"
    PHASE_1_2 = "Phase 1/2"
    PHASE_2 = "Phase 2"
    PHASE_2_3 = "Phase 2/3"
    PHASE_3 = "Phase 3"
    PHASE_4 = "Phase 4"
    UNKNOWN = "Unknown"


class TreatmentArm(BaseModel):
    """A treatment arm in the study"""
    name: str
    dose: Optional[str] = None
    route: Optional[str] = None
    frequency: Optional[str] = None
    n_patients: Optional[int] = None
    is_placebo: bool = False
    is_active_comparator: bool = False


class EndpointDefinition(BaseModel):
    """Definition of an endpoint"""
    name: str
    definition: str
    timepoint: Optional[str] = None
    scoring_system: Optional[str] = None
    components: List[str] = Field(default_factory=list)


class AlphaSpecification(BaseModel):
    """Alpha/significance level specification"""
    primary_alpha: float = 0.05
    sidedness: str = "two-sided"  # "one-sided" or "two-sided"
    additional_levels: List[float] = Field(default_factory=list)
    multiplicity_adjustment: Optional[str] = None


class SampleSizeSpec(BaseModel):
    """Sample size specification"""
    total_n: int
    per_arm: Dict[str, int] = Field(default_factory=dict)
    power: Optional[float] = None
    effect_size: Optional[str] = None
    dropout_rate: Optional[float] = None


class ProtocolFacts(BaseModel):
    """
    Complete structured facts extracted from protocol.
    This is the SINGLE SOURCE OF TRUTH for SAP generation.
    """
    # Identifiers
    nct_id: Optional[str] = None
    study_id: Optional[str] = None
    protocol_title: Optional[str] = None
    sponsor: Optional[str] = None

    # Study Design
    phase: StudyPhase = StudyPhase.UNKNOWN
    therapeutic_area: Optional[str] = None
    indication: Optional[str] = None
    design_type: Optional[str] = None  # "randomized", "open-label", etc.
    is_blinded: bool = False
    blinding_type: Optional[str] = None  # "double-blind", "single-blind", "open-label"

    # Drug/Treatment
    drug_name: Optional[str] = None
    drug_names_all: List[str] = Field(default_factory=list)
    route_of_administration: RouteOfAdministration = RouteOfAdministration.OTHER

    # Arms and Randomization
    num_arms: int = 0
    arms: List[TreatmentArm] = Field(default_factory=list)
    randomization_ratio: Optional[str] = None
    stratification_factors: List[str] = Field(default_factory=list)

    # Sample Size
    sample_size: SampleSizeSpec = Field(default_factory=lambda: SampleSizeSpec(total_n=0))

    # Endpoints
    primary_endpoint: Optional[EndpointDefinition] = None
    secondary_endpoints: List[EndpointDefinition] = Field(default_factory=list)

    # Statistical
    alpha: AlphaSpecification = Field(default_factory=AlphaSpecification)
    primary_analysis_method: Optional[str] = None
    primary_analysis_population: Optional[str] = None  # ITT, FAS, PP, etc.

    # Populations
    itt_definition: Optional[str] = None
    fas_definition: Optional[str] = None
    pp_definition: Optional[str] = None
    safety_population_definition: Optional[str] = None

    # Timepoints
    primary_timepoint: Optional[str] = None
    study_duration: Optional[str] = None
    treatment_duration: Optional[str] = None


class StructuredFactExtractor:
    """
    Extracts ALL protocol facts using regex/rules - NO LLM.

    This ensures:
    1. Deterministic extraction (same input → same output)
    2. No hallucination (only extracts what's actually there)
    3. Fast execution (no API calls)
    4. Auditable (every extraction has a pattern)
    """

    def extract_all(self, protocol_text: str) -> ProtocolFacts:
        """
        Extract all facts from protocol.

        Args:
            protocol_text: Full protocol document text

        Returns:
            ProtocolFacts with all extracted values
        """
        facts = ProtocolFacts()

        # Identifiers
        facts.nct_id = self._extract_nct_id(protocol_text)
        facts.study_id = self._extract_study_id(protocol_text)
        facts.protocol_title = self._extract_title(protocol_text)
        facts.sponsor = self._extract_sponsor(protocol_text)

        # Study Design
        facts.phase = self._extract_phase(protocol_text)
        facts.therapeutic_area = self._extract_therapeutic_area(protocol_text)
        facts.indication = self._extract_indication(protocol_text)
        facts.design_type = self._extract_design_type(protocol_text)
        facts.is_blinded, facts.blinding_type = self._extract_blinding(protocol_text)

        # Drug/Treatment
        facts.drug_name, facts.drug_names_all = self._extract_drug_names(protocol_text)
        facts.route_of_administration = self._extract_route(protocol_text)

        # Arms and Randomization
        facts.arms = self._extract_arms(protocol_text)
        facts.num_arms = len(facts.arms) if facts.arms else self._extract_num_arms(protocol_text)
        facts.randomization_ratio = self._extract_randomization_ratio(protocol_text)
        facts.stratification_factors = self._extract_stratification_factors(protocol_text)

        # Sample Size
        facts.sample_size = self._extract_sample_size(protocol_text, facts.num_arms)

        # Endpoints
        facts.primary_endpoint = self._extract_primary_endpoint(protocol_text)
        facts.secondary_endpoints = self._extract_secondary_endpoints(protocol_text)

        # Statistical
        facts.alpha = self._extract_alpha(protocol_text)
        facts.primary_analysis_method = self._extract_primary_analysis_method(protocol_text)
        facts.primary_analysis_population = self._extract_analysis_population(protocol_text)

        # Populations
        facts.itt_definition = self._extract_population_definition(protocol_text, "ITT")
        facts.fas_definition = self._extract_population_definition(protocol_text, "FAS")
        facts.pp_definition = self._extract_population_definition(protocol_text, "PP")
        facts.safety_population_definition = self._extract_population_definition(protocol_text, "safety")

        # Timepoints
        facts.primary_timepoint = self._extract_primary_timepoint(protocol_text)
        facts.study_duration = self._extract_study_duration(protocol_text)

        return facts

    def _extract_nct_id(self, text: str) -> Optional[str]:
        """Extract NCT ID"""
        match = re.search(r'NCT\d{8}', text, re.IGNORECASE)
        return match.group(0).upper() if match else None

    def _extract_study_id(self, text: str) -> Optional[str]:
        """Extract internal study ID (e.g., CTJ301UC201)"""
        patterns = [
            r'\b([A-Z]{2,5}\d{3,4}[A-Z]{0,3}\d{0,3})\b',
            r'(?:study|protocol)\s+(?:id|number|#)?[:\s]+([A-Z0-9-]{5,20})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                study_id = match.group(1)
                # Filter out common non-study-ID patterns
                if not re.match(r'^(NCT|EUR|IND|NDA|BLA|ICH|FDA|EMA)\d', study_id):
                    return study_id
        return None

    def _extract_title(self, text: str) -> Optional[str]:
        """Extract protocol title"""
        patterns = [
            r'(?:protocol\s+)?title[:\s]+([^\n]+)',
            r'^([A-Z][^.]+(?:study|trial|evaluation)[^.]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text[:3000], re.IGNORECASE | re.MULTILINE)
            if match:
                title = match.group(1).strip()
                if len(title) > 20 and len(title) < 500:
                    return title
        return None

    def _extract_sponsor(self, text: str) -> Optional[str]:
        """Extract sponsor name"""
        patterns = [
            r'(?:sponsor|sponsored\s+by)[:\s]+([A-Z][A-Za-z\s&,]+(?:Inc|LLC|Ltd|Corp|Pharma|Therapeutics)?)',
            r'(?:conducted\s+by|supported\s+by)[:\s]+([A-Z][A-Za-z\s&,]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text[:5000], re.IGNORECASE)
            if match:
                return match.group(1).strip()[:100]
        return None

    def _extract_phase(self, text: str) -> StudyPhase:
        """Extract study phase"""
        text_lower = text.lower()

        if re.search(r'phase\s*[12]/[23]|phase\s*1/2|phase\s*2/3', text_lower):
            if 'phase 1/2' in text_lower or 'phase i/ii' in text_lower:
                return StudyPhase.PHASE_1_2
            return StudyPhase.PHASE_2_3
        elif re.search(r'phase\s*(?:4|iv|four)', text_lower):
            return StudyPhase.PHASE_4
        elif re.search(r'phase\s*(?:3|iii|three)', text_lower):
            return StudyPhase.PHASE_3
        elif re.search(r'phase\s*(?:2|ii|two)', text_lower):
            return StudyPhase.PHASE_2
        elif re.search(r'phase\s*(?:1|i|one)', text_lower):
            return StudyPhase.PHASE_1

        return StudyPhase.UNKNOWN

    def _extract_therapeutic_area(self, text: str) -> Optional[str]:
        """Extract therapeutic area"""
        text_lower = text.lower()

        ta_patterns = {
            'IBD': r'ulcerative\s+colitis|crohn|inflammatory\s+bowel|IBD',
            'Oncology': r'cancer|tumor|carcinoma|lymphoma|leukemia|melanoma|metastatic|neoplasm',
            'Cardiology': r'heart\s+failure|cardiac|cardiovascular|myocardial|hypertension',
            'Neurology': r'alzheimer|parkinson|multiple\s+sclerosis|epilepsy|stroke',
            'Rheumatology': r'rheumatoid|arthritis|lupus|psoriatic|ankylosing',
            'Dermatology': r'psoriasis|atopic\s+dermatitis|eczema',
            'Pulmonology': r'asthma|COPD|pulmonary|respiratory',
            'Endocrinology': r'diabetes|thyroid|metabolic',
            'Infectious': r'HIV|hepatitis|infection|bacterial|viral',
        }

        for ta, pattern in ta_patterns.items():
            if re.search(pattern, text_lower):
                return ta

        return None

    def _extract_indication(self, text: str) -> Optional[str]:
        """Extract disease indication"""
        patterns = [
            r'(?:patients?\s+with|diagnosis\s+of|treatment\s+of)\s+([a-zA-Z\s\'-]+(?:disease|syndrome|disorder|cancer|colitis|arthritis))',
            r'(?:indication)[:\s]+([^\n]+)',
            r'(?:moderate[- ]to[- ]severe|mild[- ]to[- ]moderate)\s+([a-zA-Z\s\']+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text[:10000], re.IGNORECASE)
            if match:
                indication = match.group(1).strip()
                if len(indication) > 5 and len(indication) < 100:
                    return indication
        return None

    def _extract_design_type(self, text: str) -> Optional[str]:
        """Extract study design type"""
        text_lower = text.lower()

        design_parts = []
        if 'randomized' in text_lower or 'randomised' in text_lower:
            design_parts.append('randomized')
        if 'double-blind' in text_lower or 'double blind' in text_lower:
            design_parts.append('double-blind')
        elif 'single-blind' in text_lower or 'single blind' in text_lower:
            design_parts.append('single-blind')
        elif 'open-label' in text_lower or 'open label' in text_lower:
            design_parts.append('open-label')
        if 'placebo-controlled' in text_lower or 'placebo controlled' in text_lower:
            design_parts.append('placebo-controlled')
        if 'parallel' in text_lower:
            design_parts.append('parallel-group')
        if 'crossover' in text_lower:
            design_parts.append('crossover')

        return ', '.join(design_parts) if design_parts else None

    def _extract_blinding(self, text: str) -> Tuple[bool, Optional[str]]:
        """Extract blinding information"""
        text_lower = text.lower()

        if 'double-blind' in text_lower or 'double blind' in text_lower:
            return True, 'double-blind'
        elif 'single-blind' in text_lower or 'single blind' in text_lower:
            return True, 'single-blind'
        elif 'open-label' in text_lower or 'open label' in text_lower:
            return False, 'open-label'

        return False, None

    def _extract_drug_names(self, text: str) -> Tuple[Optional[str], List[str]]:
        """Extract drug/compound names"""
        drug_names = set()

        # Pattern 1: Drug codes (TJ301, PF-06480605, etc.)
        code_patterns = [
            r'\b([A-Z]{2,4}[-]?\d{5,8})\b',  # PF-06480605
            r'\b([A-Z]{2,3}\d{3,4})\b',  # TJ301
        ]
        for pattern in code_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if not re.match(r'^(NCT|EUR|IND|NDA|BLA)\d', match, re.IGNORECASE):
                    drug_names.add(match.upper())

        # Pattern 2: INN names (biologics: -mab, -nib; small molecules: -statin, etc.)
        inn_patterns = [
            r'\b([A-Za-z]{4,}(?:mab|nib|lib|zumab|ximab|tinib|ciclib))\b',
            r'\b([A-Za-z]{4,}(?:cillin|mycin|statin|pril|sartan|olol|dipine|azole|prazole))\b',
        ]
        for pattern in inn_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                drug_names.add(match.lower())

        # Pattern 3: Named as investigational product
        ip_patterns = [
            r'(?:investigational\s+(?:product|drug|medicinal\s+product)|IMP)[:\s]+([A-Za-z][A-Za-z0-9-]{2,})',
            r'(?:study\s+drug)[:\s]+([A-Za-z][A-Za-z0-9-]{2,})',
        ]
        for pattern in ip_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if len(name) > 2 and name.lower() not in ['the', 'and', 'or', 'with']:
                    drug_names.add(name)

        # Filter out common false positives
        false_positives = {'patients', 'subjects', 'treatment', 'placebo', 'study', 'trial'}
        drug_names = {d for d in drug_names if d.lower() not in false_positives}

        drug_list = list(drug_names)

        # DEBUG: Print all found drug names for troubleshooting
        if drug_list:
            print(f"[DEBUG] All drug names found in protocol: {drug_list}")

        # Prioritize drug codes - but prefer SHORTER codes (TJ301 over GA29144)
        # to avoid picking up internal reference numbers
        drug_codes = [d for d in drug_list if re.match(r'^[A-Z]{2,4}[-]?\d{3,}$', d)]
        if drug_codes:
            # Sort by length - prefer shorter codes (more likely to be actual drug names)
            drug_codes.sort(key=len)
            print(f"[DEBUG] Drug codes found: {drug_codes}, selecting: {drug_codes[0]}")
            return drug_codes[0], drug_list
        elif drug_list:
            return drug_list[0], drug_list

        return None, []

    def _extract_route(self, text: str) -> RouteOfAdministration:
        """Extract route of administration"""
        text_lower = text.lower()

        if re.search(r'\biv\b|intravenous|iv\s+infusion', text_lower):
            return RouteOfAdministration.IV
        elif re.search(r'\bsc\b|subcutaneous|subcutaneously', text_lower):
            return RouteOfAdministration.SC
        elif re.search(r'\bim\b|intramuscular', text_lower):
            return RouteOfAdministration.IM
        elif re.search(r'\boral|orally|tablet|capsule', text_lower):
            return RouteOfAdministration.ORAL
        elif re.search(r'topical|cream|ointment', text_lower):
            return RouteOfAdministration.TOPICAL
        elif re.search(r'inhal|nebuliz', text_lower):
            return RouteOfAdministration.INHALED

        return RouteOfAdministration.OTHER

    def _extract_arms(self, text: str) -> List[TreatmentArm]:
        """Extract treatment arms"""
        arms = []
        seen_arm_ids = set()  # Track unique arm identifiers to avoid duplicates

        # Look for arm/group descriptions
        arm_patterns = [
            r'(?:arm|group)\s*([A-D1-9])[:\s]+([^\n]+)',
            r'(?:treatment\s+)?(?:arm|group)\s+([A-D1-9])[:\s]*([^\n]+)',
            r'-\s*(?:arm|group)\s*([A-D1-9])[:\s]*([^\n]+)',
            r'([A-Za-z0-9-]+)\s+(\d+\s*(?:mg|mcg|g))[^\n]*(?:arm|group)',
        ]

        for pattern in arm_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                arm_id = match[0].upper() if len(match) > 1 else match[0].upper()
                arm_desc = match[1] if len(match) > 1 else ""

                # Skip if we've already seen this arm identifier
                if arm_id in seen_arm_ids:
                    continue
                seen_arm_ids.add(arm_id)

                is_placebo = 'placebo' in arm_desc.lower()

                arm = TreatmentArm(
                    name=arm_desc.strip() if arm_desc else f"Arm {arm_id}",
                    is_placebo=is_placebo
                )

                # Extract dose if present
                dose_match = re.search(r'(\d+\s*(?:mg|mcg|g|ml|mL))', arm_desc)
                if dose_match:
                    arm.dose = dose_match.group(1)

                arms.append(arm)

        # If no arms found, try to extract from randomization description
        if not arms:
            ratio_match = re.search(r'(\d+:\d+(?::\d+)*)', text)
            if ratio_match:
                ratio_parts = ratio_match.group(1).split(':')
                for i, _ in enumerate(ratio_parts):
                    arms.append(TreatmentArm(name=f"Arm {i+1}"))

        return arms

    def _extract_num_arms(self, text: str) -> int:
        """Extract number of treatment arms"""
        # From ratio
        ratio_match = re.search(r'(\d+:\d+(?::\d+)*)', text)
        if ratio_match:
            return len(ratio_match.group(1).split(':'))

        # From explicit statement
        arms_patterns = [
            r'(\d+)\s+(?:treatment\s+)?(?:arms?|groups?)',
            r'(?:randomized?\s+to|assigned\s+to)\s+(\d+)',
        ]
        for pattern in arms_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))

        return 0

    def _extract_randomization_ratio(self, text: str) -> Optional[str]:
        """Extract randomization ratio"""
        match = re.search(r'(\d+:\d+(?::\d+)*)', text)
        return match.group(1) if match else None

    def _extract_stratification_factors(self, text: str) -> List[str]:
        """Extract stratification factors"""
        factors = []

        patterns = [
            r'(?:stratif(?:y|ied|ication)\s+(?:by|factors?)[:\s]+)([^\n.]+)',
            r'(?:randomization\s+stratif(?:y|ied|ication)[:\s]+)([^\n.]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                factor_text = match.group(1)
                # Split by common delimiters
                parts = re.split(r'[,;]|\band\b', factor_text)
                for part in parts:
                    part = part.strip()
                    if len(part) > 3 and len(part) < 100:
                        factors.append(part)

        return factors

    def _extract_sample_size(self, text: str, num_arms: int) -> SampleSizeSpec:
        """Extract sample size specification"""
        spec = SampleSizeSpec(total_n=0)

        # Total sample size
        total_patterns = [
            r'(?:approximately\s+)?(\d+)\s+(?:patients?|subjects?|participants?)\s+(?:will\s+be\s+)?(?:enrolled|randomized|recruited)',
            r'(?:total\s+(?:of\s+)?)?(\d+)\s+(?:patients?|subjects?)\s+(?:planned|expected)',
            r'(?:sample\s+size)[:\s]+(?:approximately\s+)?(\d+)',
            r'(?:enroll|randomize)\s+(?:approximately\s+)?(\d+)',
            r'N\s*[=:]\s*(\d+)',
            # Additional patterns for common phrasings
            r'(\d+)\s+(?:patients?|subjects?|participants?)\s+(?:in\s+a|randomized|across)',
            r'(\d+)\s+(?:patients?|subjects?|participants?)\s+(?:will\s+be\s+)?(?:assigned|allocated)',
        ]

        for pattern in total_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                n = int(match.group(1))
                if 10 <= n <= 100000:  # Reasonable range
                    spec.total_n = n
                    break

        # Per-arm if available
        if spec.total_n > 0 and num_arms > 0:
            per_arm = spec.total_n // num_arms
            for i in range(num_arms):
                spec.per_arm[f"Arm {i+1}"] = per_arm

        # Power
        power_match = re.search(r'(\d{2})\s*%?\s*power', text, re.IGNORECASE)
        if power_match:
            spec.power = float(power_match.group(1)) / 100

        # Dropout rate
        dropout_match = re.search(r'(\d{1,2})\s*%?\s*(?:dropout|discontinuation|withdrawal)', text, re.IGNORECASE)
        if dropout_match:
            spec.dropout_rate = float(dropout_match.group(1)) / 100

        return spec

    def _extract_primary_endpoint(self, text: str) -> Optional[EndpointDefinition]:
        """Extract primary endpoint definition"""
        patterns = [
            r'(?:primary\s+(?:endpoint|efficacy\s+endpoint|outcome))[:\s]+([^\n]+(?:\n(?![A-Z0-9])[^\n]+)*)',
            r'(?:primary\s+objective)[:\s]+([^\n]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                endpoint_text = match.group(1).strip()

                # Extract timepoint if present
                timepoint = None
                time_match = re.search(r'(?:at|by)\s+(?:week|day|month)\s+(\d+)', endpoint_text, re.IGNORECASE)
                if time_match:
                    timepoint = f"Week {time_match.group(1)}"

                # Extract scoring system if present
                scoring = None
                scoring_patterns = ['CDAI', 'Mayo', 'PASI', 'ACR', 'DAS28', 'RECIST', 'ECOG']
                for score in scoring_patterns:
                    if score.lower() in endpoint_text.lower():
                        scoring = score
                        break

                return EndpointDefinition(
                    name="Primary Endpoint",
                    definition=endpoint_text[:500],
                    timepoint=timepoint,
                    scoring_system=scoring
                )

        return None

    def _extract_secondary_endpoints(self, text: str) -> List[EndpointDefinition]:
        """Extract secondary endpoints"""
        endpoints = []

        patterns = [
            r'(?:secondary\s+(?:endpoint|efficacy\s+endpoint|outcome)s?)[:\s]+([^\n]+(?:\n(?![A-Z0-9])[^\n]+)*)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches[:5]:  # Limit to 5
                endpoints.append(EndpointDefinition(
                    name="Secondary Endpoint",
                    definition=match.strip()[:300]
                ))

        return endpoints

    def _extract_alpha(self, text: str) -> AlphaSpecification:
        """Extract alpha/significance level specification"""
        spec = AlphaSpecification()

        # Sidedness
        if re.search(r'one[- ]sided|1[- ]sided', text, re.IGNORECASE):
            spec.sidedness = "one-sided"
        elif re.search(r'two[- ]sided|2[- ]sided', text, re.IGNORECASE):
            spec.sidedness = "two-sided"

        # Alpha level
        alpha_patterns = [
            r'(?:alpha|significance\s+level|type\s+I\s+error)[:\s=]+(\d+\.?\d*)\s*%?',
            r'(\d+\.?\d*)\s*%?\s+(?:alpha|significance)',
            r'p\s*[<≤]\s*(\d+\.?\d*)',
        ]

        for pattern in alpha_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                alpha_val = float(match.group(1))
                if alpha_val > 1:  # Percentage
                    alpha_val = alpha_val / 100
                if 0.001 <= alpha_val <= 0.5:
                    spec.primary_alpha = alpha_val
                    break

        # Additional alpha levels (e.g., 20% for exploratory)
        if re.search(r'20\s*%\s*(?:significance|alpha|level)', text, re.IGNORECASE):
            spec.additional_levels.append(0.20)

        return spec

    def _extract_primary_analysis_method(self, text: str) -> Optional[str]:
        """Extract primary analysis method"""
        method_patterns = [
            (r'logistic\s+regression', 'Logistic Regression'),
            (r'cox\s+(?:proportional\s+)?hazard', 'Cox Proportional Hazards'),
            (r'kaplan[- ]meier', 'Kaplan-Meier'),
            (r'log[- ]rank\s+test', 'Log-Rank Test'),
            (r'CMH\s+test|cochran[- ]mantel[- ]haenszel', 'CMH Test'),
            (r'ANCOVA|analysis\s+of\s+covariance', 'ANCOVA'),
            (r'MMRM|mixed[- ]model\s+repeated\s+measures', 'MMRM'),
            (r"fisher['\u2019]?s?\s+exact", "Fisher's Exact Test"),
            (r'chi[- ]square|χ²', 'Chi-Square Test'),
            (r'wilcoxon', 'Wilcoxon Test'),
            (r't[- ]test', 't-Test'),
        ]

        for pattern, method_name in method_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return method_name

        return None

    def _extract_analysis_population(self, text: str) -> Optional[str]:
        """Extract primary analysis population"""
        patterns = [
            r'(?:primary\s+analysis\s+(?:will\s+be\s+)?(?:performed|conducted)\s+(?:on|using)\s+(?:the\s+)?)(ITT|FAS|PP|mITT)',
            r'(?:primary\s+(?:analysis\s+)?population)[:\s]+(ITT|FAS|PP|mITT|intent[- ]to[- ]treat|full\s+analysis\s+set)',
            # Simpler patterns for common phrasings
            r'(?:primary\s+analysis)\s+(?:on|using)\s+(?:the\s+)?(ITT|FAS|PP|mITT)',
            r'(?:primary\s+efficacy\s+analysis)[^.]*(?:on|using|for)\s+(?:the\s+)?(ITT|FAS|PP|mITT)',
            r'(ITT|FAS|PP|mITT)\s+(?:population\s+)?(?:will\s+be\s+)?(?:used\s+)?(?:for|as)\s+(?:the\s+)?primary',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                pop = match.group(1).upper()
                if 'INTENT' in pop or pop == 'ITT':
                    return 'ITT'
                elif 'FULL' in pop or pop == 'FAS':
                    return 'FAS'
                return pop

        return None

    def _extract_population_definition(self, text: str, pop_type: str) -> Optional[str]:
        """Extract population definition"""
        patterns = {
            'ITT': r'(?:ITT|intent[- ]to[- ]treat)[^.]*(?:defined\s+as|includes?|consists?\s+of)[:\s]+([^.]+)',
            'FAS': r'(?:FAS|full\s+analysis\s+set)[^.]*(?:defined\s+as|includes?|consists?\s+of)[:\s]+([^.]+)',
            'PP': r'(?:PP|per[- ]protocol)[^.]*(?:defined\s+as|includes?|consists?\s+of)[:\s]+([^.]+)',
            'safety': r'(?:safety\s+(?:population|set|analysis\s+set))[^.]*(?:defined\s+as|includes?|consists?\s+of)[:\s]+([^.]+)',
        }

        pattern = patterns.get(pop_type)
        if pattern:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:300]

        return None

    def _extract_primary_timepoint(self, text: str) -> Optional[str]:
        """Extract primary timepoint"""
        patterns = [
            r'(?:primary\s+(?:endpoint|analysis))[^.]*(?:at|by)\s+(week\s+\d+|day\s+\d+|month\s+\d+)',
            r'(?:week\s+\d+|day\s+\d+)\s+(?:primary|endpoint)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1) if match.lastindex else match.group(0)

        return None

    def _extract_study_duration(self, text: str) -> Optional[str]:
        """Extract study duration"""
        patterns = [
            r'(?:study|treatment)\s+(?:duration|period)[:\s]+(\d+\s+(?:weeks?|months?|years?))',
            r'(?:followed\s+for|up\s+to)\s+(\d+\s+(?:weeks?|months?|years?))',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def to_prompt_context(self, facts: ProtocolFacts) -> str:
        """
        Convert facts to a prompt context string for LLM.
        This is what gets injected into the SAP generation prompt.
        """
        lines = [
            "## MANDATORY PROTOCOL FACTS",
            "Use these values EXACTLY. Do NOT change or hallucinate any values.",
            ""
        ]

        if facts.nct_id:
            lines.append(f"- NCT ID: {facts.nct_id}")
        if facts.study_id:
            lines.append(f"- Study ID: {facts.study_id}")
        if facts.drug_name:
            lines.append(f"- Drug/Compound: {facts.drug_name}")
        if facts.route_of_administration != RouteOfAdministration.OTHER:
            lines.append(f"- Route: {facts.route_of_administration.value}")
        if facts.phase != StudyPhase.UNKNOWN:
            lines.append(f"- Phase: {facts.phase.value}")
        if facts.therapeutic_area:
            lines.append(f"- Therapeutic Area: {facts.therapeutic_area}")
        if facts.indication:
            lines.append(f"- Indication: {facts.indication}")

        lines.append("")
        lines.append("### Study Design")
        if facts.design_type:
            lines.append(f"- Design: {facts.design_type}")
        lines.append(f"- Number of Arms: {facts.num_arms}")
        if facts.randomization_ratio:
            lines.append(f"- Randomization Ratio: {facts.randomization_ratio}")
        if facts.arms:
            lines.append("- Treatment Arms:")
            for arm in facts.arms:
                arm_str = f"  - {arm.name}"
                if arm.dose:
                    arm_str += f" ({arm.dose})"
                if arm.is_placebo:
                    arm_str += " [PLACEBO]"
                lines.append(arm_str)
        if facts.stratification_factors:
            lines.append(f"- Stratification Factors: {', '.join(facts.stratification_factors)}")

        lines.append("")
        lines.append("### Sample Size")
        lines.append(f"- Total N: {facts.sample_size.total_n}")
        if facts.sample_size.per_arm:
            for arm, n in facts.sample_size.per_arm.items():
                lines.append(f"  - {arm}: {n}")
        if facts.sample_size.power:
            lines.append(f"- Power: {facts.sample_size.power * 100:.0f}%")

        lines.append("")
        lines.append("### Statistical")
        lines.append(f"- Alpha: {facts.alpha.primary_alpha} ({facts.alpha.sidedness})")
        if facts.alpha.additional_levels:
            lines.append(f"- Additional Alpha Levels: {facts.alpha.additional_levels}")
        if facts.primary_analysis_method:
            lines.append(f"- Primary Analysis Method: {facts.primary_analysis_method}")
        if facts.primary_analysis_population:
            lines.append(f"- Primary Analysis Population: {facts.primary_analysis_population}")

        if facts.primary_endpoint:
            lines.append("")
            lines.append("### Primary Endpoint")
            lines.append(f"- Definition: {facts.primary_endpoint.definition}")
            if facts.primary_endpoint.timepoint:
                lines.append(f"- Timepoint: {facts.primary_endpoint.timepoint}")
            if facts.primary_endpoint.scoring_system:
                lines.append(f"- Scoring System: {facts.primary_endpoint.scoring_system}")

        return "\n".join(lines)


# Convenience function
def extract_protocol_facts(protocol_text: str) -> ProtocolFacts:
    """Extract all facts from protocol text"""
    extractor = StructuredFactExtractor()
    return extractor.extract_all(protocol_text)
