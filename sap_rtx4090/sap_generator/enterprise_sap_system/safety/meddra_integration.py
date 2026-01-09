"""
MedDRA Integration
==================

Medical Dictionary for Regulatory Activities (MedDRA) integration.

MedDRA is the international medical terminology used by regulatory authorities
for classifying adverse events in clinical trials.

Hierarchical structure:
- SOC (System Organ Class) - 27 categories
- HLGT (High Level Group Term)
- HLT (High Level Term)
- PT (Preferred Term) - Primary level for coding
- LLT (Lowest Level Term) - Verbatim terms

Official site: https://www.meddra.org/
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MedDRALevel(Enum):
    """MedDRA hierarchy levels"""
    SOC = "System Organ Class"
    HLGT = "High Level Group Term"
    HLT = "High Level Term"
    PT = "Preferred Term"
    LLT = "Lowest Level Term"


@dataclass
class MedDRACode:
    """
    MedDRA term at any hierarchy level.

    Each term has a unique 8-digit code.
    """
    code: str                         # 8-digit MedDRA code
    level: MedDRALevel
    term: str                         # Term text
    version: str = "26.1"             # MedDRA version

    # Hierarchical relationships
    parent_codes: List[str] = field(default_factory=list)
    child_codes: List[str] = field(default_factory=list)

    # Primary SOC (PT level only)
    primary_soc_code: str = ""
    primary_soc_name: str = ""

    # Active status
    is_active: bool = True            # Current version active term


@dataclass
class MedDRAPreferredTerm(MedDRACode):
    """
    MedDRA Preferred Term (PT) - primary level for AE coding.

    PTs are the standard terms used in clinical trial reporting.
    """
    # Always PT level
    level: MedDRALevel = field(default=MedDRALevel.PT, init=False)

    # LLT relationships
    lowest_level_terms: List[str] = field(default_factory=list)  # LLT codes

    # Multi-SOC
    all_socs: List[Dict[str, str]] = field(default_factory=list)  # [{code, name}, ...]


@dataclass
class MedDRASystemOrganClass:
    """
    MedDRA System Organ Class (SOC) - top level.

    27 SOCs in MedDRA covering all body systems.
    """
    code: str                         # 8-digit SOC code
    name: str                         # SOC name
    abbreviation: str = ""            # Standard abbreviation

    # Preferred terms in this SOC
    preferred_terms: List[str] = field(default_factory=list)  # PT codes


class MedDRAService:
    """
    Service for MedDRA terminology lookups and coding.

    Provides mapping between verbatim terms, preferred terms, and SOCs.
    """

    # Standard 27 MedDRA SOCs
    STANDARD_SOCS = {
        "10003041": {"name": "Blood and lymphatic system disorders", "abbr": "Blood"},
        "10007541": {"name": "Cardiac disorders", "abbr": "Cardiac"},
        "10010331": {"name": "Congenital, familial and genetic disorders", "abbr": "Congenital"},
        "10013993": {"name": "Ear and labyrinth disorders", "abbr": "Ear"},
        "10014698": {"name": "Endocrine disorders", "abbr": "Endocrine"},
        "10015919": {"name": "Eye disorders", "abbr": "Eye"},
        "10017947": {"name": "Gastrointestinal disorders", "abbr": "GI"},
        "10018065": {"name": "General disorders and administration site conditions", "abbr": "General"},
        "10019805": {"name": "Hepatobiliary disorders", "abbr": "Hepatobiliary"},
        "10021428": {"name": "Immune system disorders", "abbr": "Immune"},
        "10021881": {"name": "Infections and infestations", "abbr": "Infections"},
        "10022117": {"name": "Injury, poisoning and procedural complications", "abbr": "Injury"},
        "10022891": {"name": "Investigations", "abbr": "Investigations"},
        "10027433": {"name": "Metabolism and nutrition disorders", "abbr": "Metabolism"},
        "10028395": {"name": "Musculoskeletal and connective tissue disorders", "abbr": "Musculoskeletal"},
        "10029104": {"name": "Neoplasms benign, malignant and unspecified (incl cysts and polyps)", "abbr": "Neoplasms"},
        "10029205": {"name": "Nervous system disorders", "abbr": "Nervous"},
        "10036585": {"name": "Pregnancy, puerperium and perinatal conditions", "abbr": "Pregnancy"},
        "10037175": {"name": "Psychiatric disorders", "abbr": "Psychiatric"},
        "10038359": {"name": "Renal and urinary disorders", "abbr": "Renal"},
        "10038604": {"name": "Reproductive system and breast disorders", "abbr": "Reproductive"},
        "10038738": {"name": "Respiratory, thoracic and mediastinal disorders", "abbr": "Respiratory"},
        "10040785": {"name": "Skin and subcutaneous tissue disorders", "abbr": "Skin"},
        "10041244": {"name": "Social circumstances", "abbr": "Social"},
        "10042613": {"name": "Surgical and medical procedures", "abbr": "Surgical"},
        "10047065": {"name": "Vascular disorders", "abbr": "Vascular"},
        "10049244": {"name": "Product issues", "abbr": "Product"}
    }

    # Common oncology AE terms (embedded core set)
    COMMON_ONCOLOGY_PTS = {
        "10016256": {"term": "Fatigue", "soc": "10018065"},
        "10028813": {"term": "Nausea", "soc": "10017947"},
        "10047700": {"term": "Vomiting", "soc": "10017947"},
        "10012735": {"term": "Diarrhea", "soc": "10017947"},
        "10010774": {"term": "Constipation", "soc": "10017947"},
        "10002034": {"term": "Anaemia", "soc": "10003041"},
        "10029366": {"term": "Neutropenia", "soc": "10003041"},
        "10043554": {"term": "Thrombocytopenia", "soc": "10003041"},
        "10001551": {"term": "Alanine aminotransferase increased", "soc": "10022891"},
        "10003481": {"term": "Aspartate aminotransferase increased", "soc": "10022891"},
        "10011368": {"term": "Blood creatinine increased", "soc": "10022891"},
        "10034620": {"term": "Peripheral sensory neuropathy", "soc": "10029205"},
        "10068093": {"term": "Peripheral motor neuropathy", "soc": "10029205"},
        "10002556": {"term": "Anorexia", "soc": "10027433"},
        "10048580": {"term": "Weight decreased", "soc": "10022891"},
        "10048580": {"term": "Weight increased", "soc": "10022891"},
        "10061818": {"term": "Hypoalbuminaemia", "soc": "10022891"},
        "10019211": {"term": "Febrile neutropenia", "soc": "10003041"},
        "10048580": {"term": "Dyspnoea", "soc": "10038738"},
        "10048580": {"term": "Cough", "soc": "10038738"},
    }

    def __init__(self, version: str = "26.1"):
        """
        Initialize MedDRA service.

        Args:
            version: MedDRA version (e.g., "26.1")
        """
        self.version = version
        self._pt_cache: Dict[str, MedDRAPreferredTerm] = {}
        self._soc_cache: Dict[str, MedDRASystemOrganClass] = {}
        self._term_index: Dict[str, str] = {}  # term_name -> PT code

        # Load embedded data
        self._load_standard_socs()
        self._load_common_pts()

        logger.info(f"Initialized MedDRA {version} service")

    def _load_standard_socs(self):
        """Load standard 27 MedDRA SOCs"""
        for code, soc_data in self.STANDARD_SOCS.items():
            soc = MedDRASystemOrganClass(
                code=code,
                name=soc_data["name"],
                abbreviation=soc_data["abbr"]
            )
            self._soc_cache[code] = soc

        logger.debug(f"Loaded {len(self._soc_cache)} MedDRA SOCs")

    def _load_common_pts(self):
        """Load common oncology preferred terms"""
        for code, pt_data in self.COMMON_ONCOLOGY_PTS.items():
            pt = MedDRAPreferredTerm(
                code=code,
                term=pt_data["term"],
                version=self.version,
                primary_soc_code=pt_data["soc"]
            )

            # Set SOC name
            if pt_data["soc"] in self._soc_cache:
                pt.primary_soc_name = self._soc_cache[pt_data["soc"]].name

            self._pt_cache[code] = pt
            self._term_index[pt.term.lower()] = code

        logger.debug(f"Loaded {len(self._pt_cache)} common PTs")

    def get_preferred_term(self, pt_code: str) -> Optional[MedDRAPreferredTerm]:
        """
        Get preferred term by code.

        Args:
            pt_code: 8-digit PT code

        Returns:
            MedDRAPreferredTerm or None
        """
        return self._pt_cache.get(pt_code)

    def get_preferred_term_by_name(self, term_name: str) -> Optional[MedDRAPreferredTerm]:
        """
        Get preferred term by name.

        Args:
            term_name: PT name (e.g., "Fatigue")

        Returns:
            MedDRAPreferredTerm or None
        """
        pt_code = self._term_index.get(term_name.lower())
        if pt_code:
            return self._pt_cache.get(pt_code)
        return None

    def get_soc(self, soc_code: str) -> Optional[MedDRASystemOrganClass]:
        """
        Get System Organ Class by code.

        Args:
            soc_code: 8-digit SOC code

        Returns:
            MedDRASystemOrganClass or None
        """
        return self._soc_cache.get(soc_code)

    def get_all_socs(self) -> List[MedDRASystemOrganClass]:
        """Get all 27 standard SOCs"""
        return list(self._soc_cache.values())

    def get_soc_for_pt(self, pt_code: str) -> Optional[MedDRASystemOrganClass]:
        """
        Get primary SOC for a preferred term.

        Args:
            pt_code: PT code

        Returns:
            MedDRASystemOrganClass or None
        """
        pt = self.get_preferred_term(pt_code)
        if pt and pt.primary_soc_code:
            return self.get_soc(pt.primary_soc_code)
        return None

    def search_preferred_terms(self, query: str) -> List[MedDRAPreferredTerm]:
        """
        Search preferred terms by keyword.

        Args:
            query: Search keyword

        Returns:
            List of matching PTs
        """
        query_lower = query.lower()
        matches = []

        for pt in self._pt_cache.values():
            if query_lower in pt.term.lower():
                matches.append(pt)

        return matches

    def map_verbatim_to_pt(self, verbatim_term: str) -> Optional[MedDRAPreferredTerm]:
        """
        Map a verbatim AE term to a MedDRA PT.

        Uses simple keyword matching. In production, would use
        full MedDRA LLT->PT mapping tables.

        Args:
            verbatim_term: Investigator-reported AE term

        Returns:
            Best matching PT or None
        """
        verbatim_lower = verbatim_term.lower()

        # Exact match
        pt = self.get_preferred_term_by_name(verbatim_term)
        if pt:
            return pt

        # Keyword search
        matches = self.search_preferred_terms(verbatim_term)
        if matches:
            return matches[0]  # Return first match

        return None

    def generate_meddra_spec_text(self) -> str:
        """
        Generate MedDRA specification text for SAP.

        Returns:
            Formatted text for SAP
        """
        text = f"""
### MedDRA Coding

Adverse events will be coded using the Medical Dictionary for Regulatory Activities (MedDRA) version {self.version}.

**MedDRA Hierarchy:**
- Adverse event verbatim terms reported by investigators will be mapped to MedDRA Preferred Terms (PT)
- Each PT is classified into a System Organ Class (SOC) based on anatomy, pathology, physiology, etiology, or function
- The primary SOC will be used for analysis and presentation

**Standard MedDRA SOCs:**
The following 27 System Organ Classes will be used for AE categorization:

"""
        for soc in sorted(self._soc_cache.values(), key=lambda x: x.name):
            text += f"- {soc.name}\n"

        text += """
**Coding Conventions:**
- Each AE will be coded to the most specific PT available
- If multiple PTs could apply, the most clinically relevant PT will be selected
- Coding will be performed by trained medical coders
- All coding decisions will be documented
"""
        return text.strip()

    def get_ae_table_structure(self) -> Dict:
        """
        Get standard structure for AE tables with MedDRA.

        Returns:
            Dict with table structure spec
        """
        return {
            "primary_grouping": "System Organ Class (SOC)",
            "secondary_level": "Preferred Term (PT)",
            "sort_order": {
                "soc_level": "Alphabetical",
                "pt_level": "Descending frequency within SOC"
            },
            "display_columns": [
                "System Organ Class",
                "Preferred Term",
                "Number of Subjects",
                "Percentage (%)",
                "Number of Events"
            ],
            "coding_version": f"MedDRA {self.version}",
            "note": "Subjects with multiple AEs within the same PT are counted once at that PT"
        }


# Singleton instance
_meddra_service: Optional[MedDRAService] = None


def get_meddra_service(version: str = "26.1") -> MedDRAService:
    """
    Get singleton MedDRA service instance.

    Args:
        version: MedDRA version

    Returns:
        MedDRAService instance
    """
    global _meddra_service

    if _meddra_service is None:
        _meddra_service = MedDRAService(version=version)

    return _meddra_service
