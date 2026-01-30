"""
Trial Registry Router
Auto-detects trial ID format and routes to appropriate registry extractor
Supports: ClinicalTrials.gov, EU CTIS, EU CTR, WHO ICTRP
"""

import re
from typing import Optional, Dict, List
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RegistryType(Enum):
    """Supported trial registry types"""
    CLINICALTRIALS_GOV = "clinicaltrials.gov"
    CTIS = "ctis"                    # EU Clinical Trials Information System
    EUCTR = "euctr"                  # EU Clinical Trials Register (legacy)
    ICTRP = "ictrp"                  # WHO International Clinical Trials Registry Platform
    UNKNOWN = "unknown"


@dataclass
class TrialIdentifier:
    """Parsed trial identifier with registry information"""
    original_id: str              # Original ID as provided
    registry_type: RegistryType   # Detected registry
    normalized_id: str            # Normalized/cleaned ID
    registry_url: str             # Direct URL to trial page
    country_code: Optional[str] = None  # For EU CTR country-specific URLs


class RegistryRouter:
    """
    Routes trial IDs to appropriate registry extractors.
    Auto-detects registry from ID format and provides unified interface.
    """

    # ID Format patterns for each registry
    PATTERNS = {
        RegistryType.CLINICALTRIALS_GOV: r'^NCT\d{8}$',
        RegistryType.CTIS: r'^CT-EU-\d{2}-\d{6}$',
        RegistryType.EUCTR: r'^\d{4}-\d{6}-\d{2}(-[A-Z]{2})?$',  # Optional country code
        RegistryType.ICTRP: r'^[A-Z]{2,}-\d{4}-\d+$',
    }

    # Registry base URLs
    REGISTRY_URLS = {
        RegistryType.CLINICALTRIALS_GOV: "https://clinicaltrials.gov/study/",
        RegistryType.CTIS: "https://euclinicaltrials.eu/ctis-public/view/",
        RegistryType.EUCTR: "https://www.clinicaltrialsregister.eu/ctr-search/trial/",
        RegistryType.ICTRP: "https://trialsearch.who.int/Trial2.aspx?TrialID=",
    }

    def __init__(self):
        self.extractors = {}
        self._init_extractors()

    def _init_extractors(self):
        """Initialize registry extractors (lazy import to avoid circular dependencies)"""
        try:
            from .clinicaltrials_gov_extractor import ClinicalTrialsGovExtractor

            # Start with US-focused extractor only
            self.extractors = {
                RegistryType.CLINICALTRIALS_GOV: ClinicalTrialsGovExtractor(),
            }

            # Try to load additional registries (optional)
            try:
                from .ctis_extractor import CTISExtractor
                self.extractors[RegistryType.CTIS] = CTISExtractor()
            except ImportError:
                logger.debug("CTIS extractor not available (EU registry)")

            logger.info(f"Initialized {len(self.extractors)} registry extractors")
        except ImportError as e:
            logger.warning(f"Registry extractors not available: {e}")
            self.extractors = {}

    def detect_registry(self, trial_id: str) -> TrialIdentifier:
        """
        Detect registry type from trial ID format.

        Args:
            trial_id: Raw trial ID string

        Returns:
            TrialIdentifier with parsed information
        """
        trial_id_clean = trial_id.strip().upper()

        # Check each pattern
        for registry_type, pattern in self.PATTERNS.items():
            if re.match(pattern, trial_id_clean):
                identifier = TrialIdentifier(
                    original_id=trial_id,
                    registry_type=registry_type,
                    normalized_id=trial_id_clean,
                    registry_url=self.REGISTRY_URLS[registry_type] + trial_id_clean
                )

                # Extract country code for EU CTR
                if registry_type == RegistryType.EUCTR:
                    match = re.match(r'^\d{4}-\d{6}-\d{2}-([A-Z]{2})$', trial_id_clean)
                    if match:
                        identifier.country_code = match.group(1)

                logger.debug(f"Detected registry: {registry_type.value} for ID: {trial_id}")
                return identifier

        # Try fuzzy matching for common variations
        identifier = self._fuzzy_match(trial_id)
        if identifier:
            return identifier

        # Unknown format
        logger.warning(f"Could not detect registry for trial ID: {trial_id}")
        return TrialIdentifier(
            original_id=trial_id,
            registry_type=RegistryType.UNKNOWN,
            normalized_id=trial_id,
            registry_url=""
        )

    def _fuzzy_match(self, trial_id: str) -> Optional[TrialIdentifier]:
        """
        Attempt fuzzy matching for trial IDs embedded in text.

        Args:
            trial_id: Trial ID string (may contain extra text)

        Returns:
            TrialIdentifier if match found, None otherwise
        """
        # NCT IDs are most common - try to extract
        nct_match = re.search(r'NCT\d{8}', trial_id.upper())
        if nct_match:
            nct_id = nct_match.group(0)
            logger.info(f"Fuzzy matched NCT ID: {nct_id} from '{trial_id}'")
            return TrialIdentifier(
                original_id=trial_id,
                registry_type=RegistryType.CLINICALTRIALS_GOV,
                normalized_id=nct_id,
                registry_url=self.REGISTRY_URLS[RegistryType.CLINICALTRIALS_GOV] + nct_id
            )

        # CTIS IDs
        ctis_match = re.search(r'CT-EU-\d{2}-\d{6}', trial_id.upper())
        if ctis_match:
            ctis_id = ctis_match.group(0)
            logger.info(f"Fuzzy matched CTIS ID: {ctis_id} from '{trial_id}'")
            return TrialIdentifier(
                original_id=trial_id,
                registry_type=RegistryType.CTIS,
                normalized_id=ctis_id,
                registry_url=self.REGISTRY_URLS[RegistryType.CTIS] + ctis_id
            )

        # EudraCT numbers
        euctr_match = re.search(r'\d{4}-\d{6}-\d{2}', trial_id)
        if euctr_match:
            euctr_id = euctr_match.group(0)
            logger.info(f"Fuzzy matched EudraCT number: {euctr_id} from '{trial_id}'")
            return TrialIdentifier(
                original_id=trial_id,
                registry_type=RegistryType.EUCTR,
                normalized_id=euctr_id,
                registry_url=self.REGISTRY_URLS[RegistryType.EUCTR] + euctr_id
            )

        return None

    def fetch(self, trial_id: str) -> Optional[Dict]:
        """
        Fetch trial data from appropriate registry.

        Args:
            trial_id: Trial identifier (any format)

        Returns:
            Dict with extracted trial data, or None if failed
        """
        identifier = self.detect_registry(trial_id)

        if identifier.registry_type == RegistryType.UNKNOWN:
            logger.warning(f"Cannot fetch from unknown registry: {trial_id}")
            return None

        # Get appropriate extractor
        extractor = self.extractors.get(identifier.registry_type)
        if not extractor:
            logger.warning(f"No extractor available for {identifier.registry_type.value}")
            return None

        # Fetch data
        try:
            logger.info(f"Fetching {identifier.normalized_id} from {identifier.registry_type.value}")
            data = extractor.fetch(identifier.normalized_id)

            # Add registry metadata
            if data:
                data['_registry_info'] = {
                    'registry': identifier.registry_type.value,
                    'original_id': identifier.original_id,
                    'normalized_id': identifier.normalized_id,
                    'registry_url': identifier.registry_url
                }

            return data

        except Exception as e:
            logger.error(f"Error fetching from {identifier.registry_type.value}: {e}")
            return None

    def fetch_multi_registry(self, trial_ids: List[str]) -> Dict[str, Dict]:
        """
        Fetch from multiple registries in batch.
        Groups IDs by registry and fetches efficiently.

        Args:
            trial_ids: List of trial IDs (can be from different registries)

        Returns:
            Dict mapping trial_id -> extracted data
        """
        results = {}

        # Group by registry
        by_registry = {}
        for trial_id in trial_ids:
            identifier = self.detect_registry(trial_id)
            if identifier.registry_type not in by_registry:
                by_registry[identifier.registry_type] = []
            by_registry[identifier.registry_type].append(identifier)

        logger.info(f"Fetching {len(trial_ids)} trials from {len(by_registry)} registries")

        # Fetch from each registry
        for registry_type, identifiers in by_registry.items():
            if registry_type == RegistryType.UNKNOWN:
                logger.warning(f"Skipping {len(identifiers)} unknown registry IDs")
                continue

            extractor = self.extractors.get(registry_type)
            if not extractor:
                logger.warning(f"No extractor for {registry_type.value}, skipping {len(identifiers)} trials")
                continue

            logger.info(f"Fetching {len(identifiers)} trials from {registry_type.value}")

            for identifier in identifiers:
                try:
                    data = extractor.fetch(identifier.normalized_id)
                    if data:
                        data['_registry_info'] = {
                            'registry': identifier.registry_type.value,
                            'original_id': identifier.original_id,
                            'normalized_id': identifier.normalized_id,
                            'registry_url': identifier.registry_url
                        }
                        results[identifier.original_id] = data
                    else:
                        logger.warning(f"No data returned for {identifier.original_id}")
                except Exception as e:
                    logger.error(f"Error fetching {identifier.original_id}: {e}")

        logger.info(f"Successfully fetched {len(results)}/{len(trial_ids)} trials")
        return results

    def is_supported(self, trial_id: str) -> bool:
        """
        Check if trial ID format is supported.

        Args:
            trial_id: Trial identifier

        Returns:
            True if registry is supported and extractor available
        """
        identifier = self.detect_registry(trial_id)

        if identifier.registry_type == RegistryType.UNKNOWN:
            return False

        return identifier.registry_type in self.extractors

    def get_supported_registries(self) -> List[str]:
        """
        Get list of supported registry types.

        Returns:
            List of registry type names
        """
        return [rt.value for rt in self.extractors.keys()]

    def get_registry_stats(self) -> Dict[str, int]:
        """
        Get statistics about available registries.

        Returns:
            Dict with registry counts and status
        """
        return {
            'total_registries': len(RegistryType) - 1,  # Exclude UNKNOWN
            'available_extractors': len(self.extractors),
            'registries': self.get_supported_registries()
        }


# Singleton instance
_registry_router: Optional[RegistryRouter] = None


def get_registry_router() -> RegistryRouter:
    """
    Get singleton registry router instance.

    Returns:
        RegistryRouter instance
    """
    global _registry_router

    if _registry_router is None:
        _registry_router = RegistryRouter()
        logger.info("Registry router initialized")

    return _registry_router
