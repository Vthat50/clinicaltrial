#!/usr/bin/env python3
"""
ClinicalTrials.gov API Extractor
=================================

Primary source for structured protocol data. 100% accurate because it's the source.

Usage:
    extractor = ClinicalTrialsAPIExtractor()
    facts = extractor.extract("NCT03197467")
"""

import re
import requests
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class APIExtractedFacts:
    """Structured facts from ClinicalTrials.gov API"""
    # Identifiers
    nct_id: str = ""
    org_study_id: str = ""
    brief_title: str = ""
    official_title: str = ""

    # Design
    phase: str = ""
    study_type: str = ""
    design_allocation: str = ""  # RANDOMIZED, NON_RANDOMIZED, NA
    design_intervention_model: str = ""  # SINGLE_GROUP, PARALLEL, CROSSOVER
    design_masking: str = ""  # NONE, SINGLE, DOUBLE, TRIPLE, QUADRUPLE
    design_primary_purpose: str = ""

    # Derived flags
    is_randomized: bool = False
    is_blinded: bool = False
    is_single_arm: bool = False

    # Enrollment
    sample_size: int = 0
    enrollment_type: str = ""  # ACTUAL, ESTIMATED

    # Arms
    arms: List[Dict[str, Any]] = field(default_factory=list)
    num_arms: int = 0

    # Interventions
    interventions: List[Dict[str, Any]] = field(default_factory=list)
    drug_name: str = ""

    # Outcomes
    primary_endpoints: List[Dict[str, str]] = field(default_factory=list)
    secondary_endpoints: List[Dict[str, str]] = field(default_factory=list)

    # Eligibility
    eligibility_criteria: str = ""
    min_age: str = ""
    max_age: str = ""
    sex: str = ""

    # Conditions
    conditions: List[str] = field(default_factory=list)
    therapeutic_area: str = ""

    # Sponsor
    sponsor: str = ""
    collaborators: List[str] = field(default_factory=list)

    # Status
    overall_status: str = ""
    start_date: str = ""
    completion_date: str = ""

    # Source tracking
    source: str = "clinicaltrials.gov_api"
    api_success: bool = False
    api_error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for merging with other extractors"""
        return {
            "nct_id": self.nct_id,
            "org_study_id": self.org_study_id,
            "brief_title": self.brief_title,
            "official_title": self.official_title,
            "phase": self.phase,
            "study_type": self.study_type,
            "design_type": self._get_design_type(),
            "is_randomized": self.is_randomized,
            "is_blinded": self.is_blinded,
            "is_single_arm": self.is_single_arm,
            "sample_size": self.sample_size,
            "num_arms": self.num_arms,
            "arms": self.arms,
            "drug_name": self.drug_name,
            "interventions": self.interventions,
            "primary_endpoint": self.primary_endpoints[0]["measure"] if self.primary_endpoints else "",
            "primary_timepoint": self.primary_endpoints[0].get("timeFrame", "") if self.primary_endpoints else "",
            "primary_endpoints": self.primary_endpoints,
            "secondary_endpoints": self.secondary_endpoints,
            "therapeutic_area": self.therapeutic_area,
            "conditions": self.conditions,
            "eligibility_criteria": self.eligibility_criteria,
            "sponsor": self.sponsor,
            "source": self.source,
            "api_success": self.api_success,
        }

    def _get_design_type(self) -> str:
        """Get human-readable design type"""
        parts = []
        if self.is_randomized:
            parts.append("randomized")
        if self.is_blinded:
            parts.append(self.design_masking.lower().replace("_", "-"))
        if self.is_single_arm:
            parts.append("single-arm")
        if self.design_intervention_model:
            model = self.design_intervention_model.lower().replace("_", "-")
            if model not in ["single-group"]:  # Avoid redundancy with single-arm
                parts.append(model)
        return ", ".join(parts) if parts else "unknown"


class ClinicalTrialsAPIExtractor:
    """
    Extract structured data from ClinicalTrials.gov API.

    This is the PRIMARY source of truth for protocol facts.
    """

    BASE_URL = "https://clinicaltrials.gov/api/v2/studies"

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

        # Reference study patterns - NCT IDs near these are likely NOT the current study
        self._reference_patterns = [
            r'(?:prior|previous|reference|supporting|related)\s+(?:study|studies|trial|trials)',
            r'(?:checkmate|keynote|impower|attraction|javelin)\s*[-\s]?\d+',  # Named trials
            r'(?:in|from)\s+(?:the\s+)?(?:phase|study|trial)',
            r'(?:similar(?:ly)?|consistent|comparable)\s+(?:to|with)',
            r'(?:has|have|was|were)\s+(?:shown|demonstrated|reported)',
            r'(?:nct\d{8})\s*(?:and|,)\s*(?:nct\d{8})',  # Multiple NCT IDs listed together (references)
        ]
        self._reference_regex = re.compile(
            '|'.join(self._reference_patterns),
            re.IGNORECASE
        )

        # Current study patterns - NCT IDs near these are likely THE current study
        self._current_study_patterns = [
            r'(?:this|current|present)\s+(?:study|trial|protocol)',
            r'(?:protocol|study)\s+(?:number|id|identifier)',
            r'ca209[-\s]?\d{3}',  # BMS protocol numbers
            r'(?:sponsor|company)\s+(?:protocol|study)',
            r'statistical\s+analysis\s+plan',
            r'(?:title|name)\s*(?:of|:)\s*(?:the\s+)?(?:study|protocol)',
        ]
        self._current_study_regex = re.compile(
            '|'.join(self._current_study_patterns),
            re.IGNORECASE
        )

    def extract_nct_id(self, text: str) -> Optional[str]:
        """
        Extract NCT ID from text with smart disambiguation.

        The root problem: Protocols often mention OTHER studies as references
        (e.g., "consistent with CheckMate 057" or "similar to NCT01234567").
        This method scores each NCT ID by context to find the ACTUAL study.
        """
        return self.extract_nct_id_smart(text)

    def extract_nct_id_smart(self, text: str) -> Optional[str]:
        """
        Smart NCT ID extraction that distinguishes current study from references.

        Scoring logic:
        - NCT ID near "this study/protocol" -> +10 points
        - NCT ID in first 2000 chars -> +5 points (likely title/header)
        - NCT ID near protocol number (CA209-xxx) -> +8 points
        - NCT ID near "reference/prior study" -> -10 points
        - NCT ID mentioned with other NCT IDs (list of refs) -> -5 points

        Returns the highest-scoring NCT ID.
        """
        if not text:
            return None

        # Find all NCT IDs with their positions
        nct_pattern = re.compile(r'NCT\d{8}', re.IGNORECASE)
        matches = list(nct_pattern.finditer(text))

        if not matches:
            return None

        if len(matches) == 1:
            # Only one NCT ID - return it
            return matches[0].group().upper()

        # Multiple NCT IDs - score each one
        scores = {}
        text_lower = text.lower()

        for match in matches:
            nct_id = match.group().upper()
            pos = match.start()

            # Initialize score
            if nct_id not in scores:
                scores[nct_id] = 0

            # Context window: 500 chars before and after
            context_start = max(0, pos - 500)
            context_end = min(len(text), pos + 500)
            context = text[context_start:context_end].lower()

            # Positive signals: current study indicators
            if self._current_study_regex.search(context):
                scores[nct_id] += 10

            # Positive: Near the beginning of document (likely title page)
            if pos < 2000:
                scores[nct_id] += 5
            elif pos < 5000:
                scores[nct_id] += 2

            # Positive: Near sponsor protocol number (e.g., CA209-078)
            if re.search(r'ca209[-\s]?\d{3}', context, re.IGNORECASE):
                scores[nct_id] += 8

            # Negative signals: reference study indicators
            if self._reference_regex.search(context):
                scores[nct_id] -= 10

            # Negative: Multiple NCT IDs mentioned together (likely a reference list)
            nearby_ncts = len(nct_pattern.findall(context))
            if nearby_ncts > 2:
                scores[nct_id] -= 5 * (nearby_ncts - 1)

            # Negative: Mentioned after "such as", "e.g.", "including" (examples)
            example_pattern = r'(?:such as|e\.g\.|including|for example)[^.]*' + nct_id.lower()
            if re.search(example_pattern, context):
                scores[nct_id] -= 8

        # Return highest-scoring NCT ID
        if scores:
            best_nct = max(scores, key=scores.get)
            # Log for debugging
            print(f"[NCT Extractor] Found {len(scores)} NCT IDs. Scores: {scores}")
            print(f"[NCT Extractor] Selected: {best_nct} (score: {scores[best_nct]})")
            return best_nct

        # Fallback to first match
        return matches[0].group().upper()

    def extract_all_nct_ids(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract all NCT IDs with their scores for debugging.

        Returns:
            List of dicts with nct_id, score, and context
        """
        if not text:
            return []

        nct_pattern = re.compile(r'NCT\d{8}', re.IGNORECASE)
        matches = list(nct_pattern.finditer(text))

        results = []
        for match in matches:
            nct_id = match.group().upper()
            pos = match.start()
            context_start = max(0, pos - 100)
            context_end = min(len(text), pos + 100)
            context = text[context_start:context_end]

            results.append({
                "nct_id": nct_id,
                "position": pos,
                "context": context.replace('\n', ' ')[:200]
            })

        return results

    def fetch(self, nct_id: str) -> APIExtractedFacts:
        """
        Fetch structured data from ClinicalTrials.gov API.

        Args:
            nct_id: NCT identifier (e.g., "NCT03197467")

        Returns:
            APIExtractedFacts with structured data
        """
        facts = APIExtractedFacts(nct_id=nct_id)

        try:
            url = f"{self.BASE_URL}/{nct_id}"
            response = requests.get(url, timeout=self.timeout)

            if response.status_code == 404:
                facts.api_error = f"Study {nct_id} not found"
                return facts

            response.raise_for_status()
            data = response.json()

            facts = self._parse_response(data, facts)
            facts.api_success = True

        except requests.exceptions.Timeout:
            facts.api_error = "API timeout"
        except requests.exceptions.RequestException as e:
            facts.api_error = f"API error: {str(e)}"
        except Exception as e:
            facts.api_error = f"Parse error: {str(e)}"

        return facts

    def extract(self, text_or_nct_id: str) -> APIExtractedFacts:
        """
        Extract facts from NCT ID or text containing NCT ID.

        Args:
            text_or_nct_id: Either an NCT ID or text containing one

        Returns:
            APIExtractedFacts
        """
        # Check if it's already an NCT ID
        if re.match(r'^NCT\d{8}$', text_or_nct_id.strip(), re.IGNORECASE):
            nct_id = text_or_nct_id.strip().upper()
        else:
            # Extract from text
            nct_id = self.extract_nct_id(text_or_nct_id)

        if not nct_id:
            facts = APIExtractedFacts()
            facts.api_error = "No NCT ID found in text"
            return facts

        return self.fetch(nct_id)

    def _parse_response(self, data: Dict[str, Any], facts: APIExtractedFacts) -> APIExtractedFacts:
        """Parse API response into structured facts"""
        protocol = data.get("protocolSection", {})

        # Identification
        id_module = protocol.get("identificationModule", {})
        facts.nct_id = id_module.get("nctId", facts.nct_id)
        facts.org_study_id = id_module.get("orgStudyIdInfo", {}).get("id", "")
        facts.brief_title = id_module.get("briefTitle", "")
        facts.official_title = id_module.get("officialTitle", "")

        # Design
        design_module = protocol.get("designModule", {})
        phases = design_module.get("phases", [])
        facts.phase = phases[0] if phases else ""
        facts.study_type = design_module.get("studyType", "")

        design_info = design_module.get("designInfo", {})
        facts.design_allocation = design_info.get("allocation", "")
        facts.design_intervention_model = design_info.get("interventionModel", "")
        facts.design_primary_purpose = design_info.get("primaryPurpose", "")

        # Masking
        masking_info = design_info.get("maskingInfo", {})
        facts.design_masking = masking_info.get("masking", "NONE")

        # Derived flags
        facts.is_randomized = facts.design_allocation == "RANDOMIZED"
        facts.is_blinded = facts.design_masking not in ["NONE", "", None]
        facts.is_single_arm = facts.design_intervention_model == "SINGLE_GROUP"

        # Enrollment
        enrollment_info = design_module.get("enrollmentInfo", {})
        facts.sample_size = enrollment_info.get("count", 0)
        facts.enrollment_type = enrollment_info.get("type", "")

        # Arms
        arms_module = protocol.get("armsInterventionsModule", {})
        arm_groups = arms_module.get("armGroups", [])
        facts.arms = [
            {
                "name": arm.get("label", ""),
                "type": arm.get("type", ""),
                "description": arm.get("description", ""),
            }
            for arm in arm_groups
        ]
        facts.num_arms = len(facts.arms) if facts.arms else (1 if facts.is_single_arm else 0)

        # Interventions
        interventions = arms_module.get("interventions", [])
        facts.interventions = [
            {
                "name": intv.get("name", ""),
                "type": intv.get("type", ""),
                "description": intv.get("description", ""),
            }
            for intv in interventions
        ]

        # Extract primary drug name (first DRUG type intervention)
        for intv in interventions:
            if intv.get("type") == "DRUG":
                facts.drug_name = intv.get("name", "")
                break

        # If no DRUG type, use first BIOLOGICAL
        if not facts.drug_name:
            for intv in interventions:
                if intv.get("type") == "BIOLOGICAL":
                    facts.drug_name = intv.get("name", "")
                    break

        # Outcomes
        outcomes_module = protocol.get("outcomesModule", {})

        primary_outcomes = outcomes_module.get("primaryOutcomes", [])
        facts.primary_endpoints = [
            {
                "measure": outcome.get("measure", ""),
                "description": outcome.get("description", ""),
                "timeFrame": outcome.get("timeFrame", ""),
            }
            for outcome in primary_outcomes
        ]

        secondary_outcomes = outcomes_module.get("secondaryOutcomes", [])
        facts.secondary_endpoints = [
            {
                "measure": outcome.get("measure", ""),
                "description": outcome.get("description", ""),
                "timeFrame": outcome.get("timeFrame", ""),
            }
            for outcome in secondary_outcomes
        ]

        # Eligibility
        eligibility_module = protocol.get("eligibilityModule", {})
        facts.eligibility_criteria = eligibility_module.get("eligibilityCriteria", "")
        facts.min_age = eligibility_module.get("minimumAge", "")
        facts.max_age = eligibility_module.get("maximumAge", "")
        facts.sex = eligibility_module.get("sex", "")

        # Conditions
        conditions_module = protocol.get("conditionsModule", {})
        facts.conditions = conditions_module.get("conditions", [])

        # Infer therapeutic area from conditions
        facts.therapeutic_area = self._infer_therapeutic_area(facts.conditions)

        # Sponsor
        sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
        lead_sponsor = sponsor_module.get("leadSponsor", {})
        facts.sponsor = lead_sponsor.get("name", "")

        collaborators = sponsor_module.get("collaborators", [])
        facts.collaborators = [c.get("name", "") for c in collaborators]

        # Status
        status_module = protocol.get("statusModule", {})
        facts.overall_status = status_module.get("overallStatus", "")
        facts.start_date = status_module.get("startDateStruct", {}).get("date", "")
        facts.completion_date = status_module.get("completionDateStruct", {}).get("date", "")

        return facts

    def _infer_therapeutic_area(self, conditions: List[str]) -> str:
        """Infer therapeutic area from conditions"""
        conditions_lower = " ".join(conditions).lower()

        therapeutic_areas = {
            "oncology": ["cancer", "tumor", "carcinoma", "lymphoma", "leukemia", "melanoma", "sarcoma", "neoplasm"],
            "immunology": ["rheumatoid", "lupus", "psoriasis", "crohn", "colitis", "inflammatory bowel", "arthritis"],
            "neurology": ["alzheimer", "parkinson", "multiple sclerosis", "epilepsy", "migraine", "stroke"],
            "cardiology": ["heart failure", "hypertension", "atrial fibrillation", "coronary", "myocardial"],
            "infectious disease": ["hiv", "hepatitis", "covid", "influenza", "infection", "bacterial", "viral"],
            "respiratory": ["asthma", "copd", "pulmonary", "lung disease", "respiratory"],
            "endocrinology": ["diabetes", "thyroid", "obesity", "metabolic"],
            "gastroenterology": ["ibd", "ulcerative colitis", "crohn", "liver", "hepatic", "gi ", "gastrointestinal"],
            "dermatology": ["psoriasis", "eczema", "dermatitis", "skin"],
            "hematology": ["anemia", "thrombocytopenia", "hemophilia", "blood disorder"],
        }

        for area, keywords in therapeutic_areas.items():
            if any(kw in conditions_lower for kw in keywords):
                return area

        return "general"

    def validate_nct_id(self, nct_id: str, document_text: str, threshold: float = 0.3) -> Dict[str, Any]:
        """
        Validate NCT ID by cross-checking API data against document.

        This prevents using a reference study's NCT ID by verifying
        the API's protocol info matches the document content.

        Args:
            nct_id: NCT ID to validate
            document_text: Full document text to match against
            threshold: Minimum match score (0-1) to consider valid

        Returns:
            Dict with: valid (bool), confidence (float), reason (str), suggested_nct (str or None)
        """
        result = {
            "valid": False,
            "confidence": 0.0,
            "reason": "",
            "suggested_nct": None
        }

        # Fetch API data
        api_facts = self.fetch(nct_id)
        if not api_facts.api_success:
            result["reason"] = f"API fetch failed: {api_facts.api_error}"
            return result

        doc_lower = document_text.lower()

        # Calculate match score based on key identifiers
        match_signals = []

        # Check if API title appears in document
        if api_facts.brief_title:
            title_words = str(api_facts.brief_title).lower().split()
            title_words = [w for w in title_words if len(w) > 3]  # Skip short words
            if title_words:
                matches = sum(1 for w in title_words if w in doc_lower)
                title_score = matches / len(title_words)
                match_signals.append(("title", title_score))

        # Check if sponsor appears in document
        if api_facts.sponsor:
            sponsor_lower = str(api_facts.sponsor).lower()
            sponsor_in_doc = sponsor_lower in doc_lower
            match_signals.append(("sponsor", 1.0 if sponsor_in_doc else 0.0))

        # Check if drug name appears in document
        if api_facts.drug_name:
            drug_lower = str(api_facts.drug_name).lower()
            drug_in_doc = drug_lower in doc_lower
            match_signals.append(("drug", 1.0 if drug_in_doc else 0.0))

        # Check if indication/conditions appear
        if api_facts.conditions:
            conditions_lower = [str(c).lower() for c in api_facts.conditions]
            condition_matches = sum(1 for c in conditions_lower if c in doc_lower)
            if conditions_lower:
                condition_score = condition_matches / len(conditions_lower)
                match_signals.append(("conditions", condition_score))

        # Check if org_study_id (sponsor protocol number) appears
        if api_facts.org_study_id:
            org_id_lower = str(api_facts.org_study_id).lower()
            org_id_in_doc = org_id_lower in doc_lower
            match_signals.append(("org_study_id", 1.0 if org_id_in_doc else 0.0))

        # Calculate overall confidence
        if match_signals:
            # Weight: org_study_id and drug are most important
            weights = {"org_study_id": 3.0, "drug": 2.0, "sponsor": 1.5, "title": 1.0, "conditions": 1.0}
            weighted_sum = sum(score * weights.get(name, 1.0) for name, score in match_signals)
            total_weight = sum(weights.get(name, 1.0) for name, _ in match_signals)
            result["confidence"] = weighted_sum / total_weight
        else:
            result["confidence"] = 0.0

        # Determine validity
        result["valid"] = result["confidence"] >= threshold

        if result["valid"]:
            result["reason"] = f"NCT ID validated (confidence: {result['confidence']:.1%})"
        else:
            result["reason"] = f"NCT ID may be incorrect (confidence: {result['confidence']:.1%}). " \
                               f"API title '{api_facts.brief_title[:50]}...' may not match document."

            # Try to find a better NCT ID
            all_ncts = self.extract_all_nct_ids(document_text)
            for nct_info in all_ncts:
                candidate = nct_info["nct_id"]
                if candidate != nct_id:
                    candidate_result = self.validate_nct_id(candidate, document_text, threshold)
                    if candidate_result["valid"] and candidate_result["confidence"] > result["confidence"]:
                        result["suggested_nct"] = candidate
                        result["reason"] += f" Consider using {candidate} instead."
                        break

        print(f"[NCT Validator] {nct_id}: valid={result['valid']}, confidence={result['confidence']:.1%}")
        return result

    def extract_and_validate(self, text: str) -> tuple[Optional[str], Dict[str, Any]]:
        """
        Extract NCT ID and validate it against the document.

        Returns:
            Tuple of (nct_id, validation_result)
        """
        nct_id = self.extract_nct_id(text)
        if not nct_id:
            return None, {"valid": False, "confidence": 0.0, "reason": "No NCT ID found"}

        validation = self.validate_nct_id(nct_id, text)
        return nct_id, validation


# Convenience function
def extract_from_api(text_or_nct_id: str) -> APIExtractedFacts:
    """Quick extraction from API"""
    return ClinicalTrialsAPIExtractor().extract(text_or_nct_id)
