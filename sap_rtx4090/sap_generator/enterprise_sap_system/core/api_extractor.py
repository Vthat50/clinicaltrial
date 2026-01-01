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

    def extract_nct_id(self, text: str) -> Optional[str]:
        """Extract NCT ID from text"""
        match = re.search(r'NCT\d{8}', text, re.IGNORECASE)
        return match.group().upper() if match else None

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


# Convenience function
def extract_from_api(text_or_nct_id: str) -> APIExtractedFacts:
    """Quick extraction from API"""
    return ClinicalTrialsAPIExtractor().extract(text_or_nct_id)
