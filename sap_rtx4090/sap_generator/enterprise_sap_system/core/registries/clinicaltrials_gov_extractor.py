#!/usr/bin/env python3
"""
ClinicalTrials.gov API Extractor
=================================

US National Library of Medicine Clinical Trials Registry
API: https://clinicaltrials.gov/api/v2/
Primary source for US-based trials (NCT numbers)

This is the PRIMARY source of truth for US protocol data.
"""

import re
import requests
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class ClinicalTrialsGovExtractor:
    """
    Extract structured data from ClinicalTrials.gov API v2.

    Covers all US trials registered in ClinicalTrials.gov (NCT numbers).
    This is the authoritative source for US clinical trials under FDAAA 801.
    """

    BASE_URL = "https://clinicaltrials.gov/api/v2/studies"

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'SAP-Generator-Enterprise/1.0'
        })

        # Reference study patterns - NCT IDs near these are likely NOT the current study
        self._reference_patterns = [
            r'(?:prior|previous|reference|supporting|related)\s+(?:study|studies|trial|trials)',
            r'(?:checkmate|keynote|impower|attraction|javelin)\s*[-\s]?\d+',  # Named trials
            r'(?:in|from)\s+(?:the\s+)?(?:phase|study|trial)',
            r'(?:similar(?:ly)?|consistent|comparable)\s+(?:to|with)',
            r'(?:has|have|was|were)\s+(?:shown|demonstrated|reported)',
            r'(?:nct\d{8})\s*(?:and|,)\s*(?:nct\d{8})',  # Multiple NCT IDs listed together
        ]
        self._reference_regex = re.compile(
            '|'.join(self._reference_patterns),
            re.IGNORECASE
        )

        # Current study patterns
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

        Args:
            text: Protocol text containing NCT ID

        Returns:
            Most likely NCT ID for THIS study, or None
        """
        if not text:
            return None

        # Find all NCT IDs with their positions
        nct_pattern = re.compile(r'NCT\d{8}', re.IGNORECASE)
        matches = list(nct_pattern.finditer(text))

        if not matches:
            return None

        if len(matches) == 1:
            return matches[0].group().upper()

        # Multiple NCT IDs - score each one
        scores = {}
        text_lower = text.lower()

        for match in matches:
            nct_id = match.group().upper()
            pos = match.start()

            if nct_id not in scores:
                scores[nct_id] = 0

            # Context window: 500 chars before and after
            context_start = max(0, pos - 500)
            context_end = min(len(text), pos + 500)
            context = text[context_start:context_end].lower()

            # Positive signals: current study indicators
            if self._current_study_regex.search(context):
                scores[nct_id] += 10

            # Positive: Near the beginning of document
            if pos < 2000:
                scores[nct_id] += 5
            elif pos < 5000:
                scores[nct_id] += 2

            # Positive: Near sponsor protocol number
            if re.search(r'ca209[-\s]?\d{3}', context, re.IGNORECASE):
                scores[nct_id] += 8

            # Negative signals: reference study indicators
            if self._reference_regex.search(context):
                scores[nct_id] -= 10

            # Negative: Multiple NCT IDs mentioned together
            nearby_ncts = len(nct_pattern.findall(context))
            if nearby_ncts > 2:
                scores[nct_id] -= 5 * (nearby_ncts - 1)

            # Negative: Mentioned after "such as", "e.g.", "including"
            example_pattern = r'(?:such as|e\.g\.|including|for example)[^.]*' + nct_id.lower()
            if re.search(example_pattern, context):
                scores[nct_id] -= 8

        # Return highest-scoring NCT ID
        if scores:
            best_nct = max(scores, key=scores.get)
            logger.debug(f"Found {len(scores)} NCT IDs. Selected: {best_nct} (score: {scores[best_nct]})")
            return best_nct

        return matches[0].group().upper()

    def fetch(self, nct_id: str) -> Dict:
        """
        Fetch trial data from ClinicalTrials.gov API.

        Args:
            nct_id: NCT identifier (e.g., "NCT03197467")

        Returns:
            Dict with extracted trial data
        """
        facts = {
            'registry': 'ClinicalTrials.gov',
            'trial_id': nct_id,
            'api_success': False,
            'api_error': None
        }

        try:
            url = f"{self.BASE_URL}/{nct_id}"
            logger.debug(f"Fetching ClinicalTrials.gov: {url}")

            response = self.session.get(url, timeout=self.timeout)

            if response.status_code == 404:
                facts['api_error'] = f"Study {nct_id} not found"
                logger.warning(f"ClinicalTrials.gov trial not found: {nct_id}")
                return facts

            response.raise_for_status()
            data = response.json()

            # Parse API response
            facts.update(self._parse_response(data))
            facts['api_success'] = True

            logger.info(f"Successfully fetched ClinicalTrials.gov trial: {nct_id}")

        except requests.exceptions.Timeout:
            facts['api_error'] = "API timeout"
            logger.error(f"ClinicalTrials.gov API timeout for {nct_id}")
        except requests.exceptions.RequestException as e:
            facts['api_error'] = f"API error: {str(e)}"
            logger.error(f"ClinicalTrials.gov API error for {nct_id}: {e}")
        except Exception as e:
            facts['api_error'] = f"Parse error: {str(e)}"
            logger.error(f"ClinicalTrials.gov parse error for {nct_id}: {e}")

        return facts

    def _parse_response(self, data: Dict[str, Any]) -> Dict:
        """Parse ClinicalTrials.gov API response into standardized facts"""
        facts = {}
        protocol = data.get("protocolSection", {})

        # Identification
        id_module = protocol.get("identificationModule", {})
        facts['nct_id'] = id_module.get("nctId", "")
        facts['org_study_id'] = id_module.get("orgStudyIdInfo", {}).get("id", "")
        facts['title'] = id_module.get("officialTitle") or id_module.get("briefTitle", "")
        facts['brief_title'] = id_module.get("briefTitle", "")

        # Design
        design_module = protocol.get("designModule", {})
        phases = design_module.get("phases", [])
        facts['phase'] = phases[0] if phases else ""
        facts['study_type'] = design_module.get("studyType", "")

        design_info = design_module.get("designInfo", {})
        facts['allocation'] = design_info.get("allocation", "")
        facts['intervention_model'] = design_info.get("interventionModel", "")
        facts['primary_purpose'] = design_info.get("primaryPurpose", "")

        # Masking
        masking_info = design_info.get("maskingInfo", {})
        facts['masking'] = masking_info.get("masking", "NONE")

        # Derived flags
        facts['is_randomized'] = facts['allocation'] == "RANDOMIZED"
        facts['is_blinded'] = facts['masking'] not in ["NONE", "", None]
        facts['is_single_arm'] = facts['intervention_model'] == "SINGLE_GROUP"

        # Enrollment
        enrollment_info = design_module.get("enrollmentInfo", {})
        facts['sample_size'] = enrollment_info.get("count", 0)
        facts['enrollment_type'] = enrollment_info.get("type", "")

        # Arms
        arms_module = protocol.get("armsInterventionsModule", {})
        arm_groups = arms_module.get("armGroups", [])
        facts['arms'] = [
            {
                "name": arm.get("label", ""),
                "type": arm.get("type", ""),
                "description": arm.get("description", ""),
            }
            for arm in arm_groups
        ]
        facts['num_arms'] = len(facts['arms']) if facts['arms'] else (1 if facts['is_single_arm'] else 0)

        # Interventions
        interventions = arms_module.get("interventions", [])
        facts['interventions'] = [
            {
                "name": intv.get("name", ""),
                "type": intv.get("type", ""),
                "description": intv.get("description", ""),
            }
            for intv in interventions
        ]

        # Extract primary drug name
        facts['drug_name'] = self._extract_drug_name(interventions)

        # Outcomes (Endpoints)
        outcomes_module = protocol.get("outcomesModule", {})

        primary_outcomes = outcomes_module.get("primaryOutcomes", [])
        facts['primary_endpoints'] = [
            {
                "name": outcome.get("measure", ""),
                "description": outcome.get("description", ""),
                "timeframe": outcome.get("timeFrame", ""),
            }
            for outcome in primary_outcomes
        ]

        secondary_outcomes = outcomes_module.get("secondaryOutcomes", [])
        facts['secondary_endpoints'] = [
            {
                "name": outcome.get("measure", ""),
                "description": outcome.get("description", ""),
                "timeframe": outcome.get("timeFrame", ""),
            }
            for outcome in secondary_outcomes
        ]

        # Eligibility
        eligibility_module = protocol.get("eligibilityModule", {})
        facts['eligibility_criteria'] = eligibility_module.get("eligibilityCriteria", "")
        facts['min_age'] = eligibility_module.get("minimumAge", "")
        facts['max_age'] = eligibility_module.get("maximumAge", "")
        facts['sex'] = eligibility_module.get("sex", "")

        # Conditions
        conditions_module = protocol.get("conditionsModule", {})
        facts['conditions'] = conditions_module.get("conditions", [])
        facts['condition'] = facts['conditions'][0] if facts['conditions'] else ""

        # Infer therapeutic area
        facts['therapeutic_area'] = self._infer_therapeutic_area(facts['conditions'])

        # Sponsor
        sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
        lead_sponsor = sponsor_module.get("leadSponsor", {})
        facts['sponsor'] = lead_sponsor.get("name", "")

        collaborators = sponsor_module.get("collaborators", [])
        facts['collaborators'] = [c.get("name", "") for c in collaborators]

        # Status
        status_module = protocol.get("statusModule", {})
        facts['status'] = status_module.get("overallStatus", "")
        facts['start_date'] = status_module.get("startDateStruct", {}).get("date", "")
        facts['completion_date'] = status_module.get("completionDateStruct", {}).get("date", "")

        # Locations (US-specific)
        locations_module = protocol.get("contactsLocationsModule", {})
        locations = locations_module.get("locations", [])
        facts['countries'] = list(set([loc.get("country", "United States") for loc in locations]))
        facts['us_states'] = list(set([loc.get("state", "") for loc in locations if loc.get("country") in ["United States", "", None]]))

        return facts

    def _extract_drug_name(self, interventions: List[Dict]) -> str:
        """Extract primary drug name from interventions"""
        # First DRUG type intervention
        for intv in interventions:
            if intv.get("type") == "DRUG":
                return intv.get("name", "")

        # If no DRUG type, use first BIOLOGICAL
        for intv in interventions:
            if intv.get("type") == "BIOLOGICAL":
                return intv.get("name", "")

        # Fallback to first intervention
        if interventions:
            return interventions[0].get("name", "")

        return ""

    def _infer_therapeutic_area(self, conditions: List[str]) -> str:
        """Infer therapeutic area from conditions"""
        conditions_lower = " ".join(conditions).lower()

        therapeutic_areas = {
            "oncology": ["cancer", "tumor", "carcinoma", "lymphoma", "leukemia", "melanoma", "sarcoma", "neoplasm", "malignancy"],
            "immunology": ["rheumatoid", "lupus", "psoriasis", "crohn", "colitis", "inflammatory bowel", "arthritis"],
            "neurology": ["alzheimer", "parkinson", "multiple sclerosis", "epilepsy", "migraine", "stroke"],
            "cardiology": ["heart failure", "hypertension", "atrial fibrillation", "coronary", "myocardial"],
            "infectious disease": ["hiv", "hepatitis", "covid", "influenza", "infection", "bacterial", "viral"],
            "respiratory": ["asthma", "copd", "pulmonary", "lung disease", "respiratory"],
            "endocrinology": ["diabetes", "thyroid", "obesity", "metabolic"],
            "gastroenterology": ["ibd", "ulcerative colitis", "liver", "hepatic", "gi ", "gastrointestinal"],
            "dermatology": ["psoriasis", "eczema", "dermatitis", "skin"],
            "hematology": ["anemia", "thrombocytopenia", "hemophilia", "blood disorder"],
        }

        for area, keywords in therapeutic_areas.items():
            if any(kw in conditions_lower for kw in keywords):
                return area

        return "general"

    def search_trials(
        self,
        condition: str = None,
        intervention: str = None,
        sponsor: str = None,
        phase: str = None,
        status: str = None
    ) -> List[Dict]:
        """
        Search ClinicalTrials.gov for trials.

        Args:
            condition: Medical condition
            intervention: Drug/intervention name
            sponsor: Sponsor name
            phase: Trial phase
            status: Recruitment status

        Returns:
            List of matching trials
        """
        try:
            params = {
                "format": "json",
                "pageSize": 100
            }

            # Build query
            query_parts = []
            if condition:
                query_parts.append(f"AREA[Condition]{condition}")
            if intervention:
                query_parts.append(f"AREA[Intervention]{intervention}")
            if sponsor:
                query_parts.append(f"AREA[Sponsor]{sponsor}")
            if phase:
                query_parts.append(f"AREA[Phase]{phase}")
            if status:
                query_parts.append(f"AREA[OverallStatus]{status}")

            if query_parts:
                params["query.cond"] = " AND ".join(query_parts)

            response = self.session.get(
                f"{self.BASE_URL}",
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()
            studies = data.get("studies", [])

            # Extract basic info for each study
            results = []
            for study in studies:
                protocol = study.get("protocolSection", {})
                id_module = protocol.get("identificationModule", {})

                results.append({
                    "nct_id": id_module.get("nctId", ""),
                    "title": id_module.get("briefTitle", ""),
                    "status": protocol.get("statusModule", {}).get("overallStatus", "")
                })

            return results

        except Exception as e:
            logger.error(f"ClinicalTrials.gov search error: {e}")
            return []

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
            Dict with: valid (bool), confidence (float), reason (str)
        """
        result = {
            "valid": False,
            "confidence": 0.0,
            "reason": ""
        }

        # Fetch API data
        api_facts = self.fetch(nct_id)
        if not api_facts.get('api_success'):
            result["reason"] = f"API fetch failed: {api_facts.get('api_error')}"
            return result

        doc_lower = document_text.lower()

        # Calculate match score based on key identifiers
        match_signals = []

        # Check if API title appears in document
        if api_facts.get('title'):
            title_words = str(api_facts['title']).lower().split()
            title_words = [w for w in title_words if len(w) > 3]
            if title_words:
                matches = sum(1 for w in title_words if w in doc_lower)
                title_score = matches / len(title_words)
                match_signals.append(("title", title_score))

        # Check if sponsor appears in document
        if api_facts.get('sponsor'):
            sponsor_lower = str(api_facts['sponsor']).lower()
            sponsor_in_doc = sponsor_lower in doc_lower
            match_signals.append(("sponsor", 1.0 if sponsor_in_doc else 0.0))

        # Check if drug name appears
        if api_facts.get('drug_name'):
            drug_lower = str(api_facts['drug_name']).lower()
            drug_in_doc = drug_lower in doc_lower
            match_signals.append(("drug", 1.0 if drug_in_doc else 0.0))

        # Check if org_study_id (sponsor protocol number) appears
        if api_facts.get('org_study_id'):
            org_id_lower = str(api_facts['org_study_id']).lower()
            org_id_in_doc = org_id_lower in doc_lower
            match_signals.append(("org_study_id", 1.0 if org_id_in_doc else 0.0))

        # Calculate overall confidence
        if match_signals:
            weights = {"org_study_id": 3.0, "drug": 2.0, "sponsor": 1.5, "title": 1.0}
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
            result["reason"] = f"NCT ID may be incorrect (confidence: {result['confidence']:.1%})"

        logger.debug(f"NCT Validator: {nct_id} valid={result['valid']}, confidence={result['confidence']:.1%}")
        return result
