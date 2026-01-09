"""
NCI EVS CDISC Controlled Terminology Service
Provides centralized access to CDISC CT with version management
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from pathlib import Path
import json
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TerminologySource(Enum):
    NCI_EVS_API = "nci_evs_api"
    LOCAL_CACHE = "local_cache"
    EMBEDDED = "embedded"


@dataclass
class NCICode:
    """NCI Concept Code"""
    code: str              # e.g., "C25473"
    preferred_term: str    # e.g., "Overall Survival"
    definition: str
    synonyms: List[str] = field(default_factory=list)


@dataclass
class TerminologyItem:
    """Single CT entry"""
    nci_code: str                    # NCI C-code
    submission_value: str            # CDISC code (e.g., "OS")
    preferred_term: str              # Decode text
    definition: str
    synonyms: List[str] = field(default_factory=list)
    extensible: bool = False
    codelist_code: str = ""          # Parent codelist


@dataclass
class CodeList:
    """Complete codelist with items"""
    code: str                        # NCI C-code for codelist
    name: str                        # e.g., "Sex"
    submission_value: str            # CDISC codelist code
    extensible: bool
    definition: str
    items: List[TerminologyItem] = field(default_factory=list)


@dataclass
class TerminologyPackage:
    """Version-specific CT package"""
    package_name: str                # e.g., "sdtm-terminology-2024-09-27"
    version: str                     # e.g., "2024-09-27"
    effective_date: str
    package_type: str                # SDTM, ADaM, Protocol, Define-XML
    codelists: Dict[str, CodeList] = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)


class CDISCTerminologyService:
    """
    Centralized CDISC CT management with NCI EVS integration.
    Supports multiple versions, local caching, and validation.
    """

    def __init__(
        self,
        cache_dir: Path = None,
        default_version: str = "2024-09-27",
        source: TerminologySource = TerminologySource.LOCAL_CACHE
    ):
        self.cache_dir = cache_dir or (Path(__file__).parent.parent / "data" / "terminology")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.default_version = default_version
        self.source = source

        # In-memory cache
        self._packages: Dict[str, TerminologyPackage] = {}
        self._codelist_index: Dict[str, Dict[str, CodeList]] = {}  # version -> name -> codelist

        # Initialize default package
        self._load_default_package()

    def _load_default_package(self):
        """Load default CT version on initialization"""
        try:
            self.load_package(self.default_version, "SDTM")
            self.load_package(self.default_version, "ADaM")
        except Exception as e:
            logger.warning(f"Could not load default CT package: {e}")

    def load_package(
        self,
        version: str,
        package_type: str
    ) -> TerminologyPackage:
        """
        Load CT package from cache or download from NCI EVS.

        Args:
            version: CT version (e.g., "2024-09-27")
            package_type: "SDTM", "ADaM", "Protocol", "Define-XML"

        Returns:
            TerminologyPackage with all codelists
        """
        package_key = f"{package_type.lower()}-{version}"

        # Check in-memory cache
        if package_key in self._packages:
            return self._packages[package_key]

        # Try loading from disk cache
        cache_file = self.cache_dir / version / f"{package_type.lower()}_codelists.json"
        if cache_file.exists():
            package = self._load_from_cache(cache_file, version, package_type)
            self._packages[package_key] = package
            self._index_package(package, version)
            return package

        # Download from NCI EVS if source is API
        if self.source == TerminologySource.NCI_EVS_API:
            package = self._download_from_nci_evs(version, package_type)
            self._save_to_cache(package, cache_file)
            self._packages[package_key] = package
            self._index_package(package, version)
            return package

        raise ValueError(f"CT package not found: {package_type} {version}")

    def get_codelist(
        self,
        codelist_name: str,
        version: str = None
    ) -> Optional[CodeList]:
        """
        Get a specific codelist by name.

        Args:
            codelist_name: Codelist name (e.g., "Sex", "PARAMCD")
            version: CT version (default: self.default_version)

        Returns:
            CodeList object or None
        """
        version = version or self.default_version

        if version not in self._codelist_index:
            # Try loading package
            try:
                self.load_package(version, "SDTM")
                self.load_package(version, "ADaM")
            except:
                return None

        return self._codelist_index.get(version, {}).get(codelist_name)

    def validate_term(
        self,
        codelist_name: str,
        value: str,
        version: str = None
    ) -> bool:
        """
        Validate if a term exists in a codelist.

        Args:
            codelist_name: Codelist name
            value: Submission value to check
            version: CT version

        Returns:
            True if valid, False otherwise
        """
        codelist = self.get_codelist(codelist_name, version)
        if not codelist:
            return False

        # Check submission values
        valid_values = {item.submission_value for item in codelist.items}
        return value in valid_values

    def get_paramcd_list(
        self,
        version: str = None
    ) -> List[TerminologyItem]:
        """Get all valid PARAMCD values"""
        codelist = self.get_codelist("PARAMCD", version)
        if not codelist:
            return []
        return codelist.items

    def search_param(
        self,
        keyword: str,
        version: str = None
    ) -> List[TerminologyItem]:
        """
        Search PARAMCD by keyword.

        Args:
            keyword: Search term (e.g., "survival", "response")
            version: CT version

        Returns:
            List of matching TerminologyItem
        """
        paramcd_list = self.get_paramcd_list(version)
        keyword_lower = keyword.lower()

        results = []
        for item in paramcd_list:
            # Search in preferred term, definition, synonyms
            if (keyword_lower in item.preferred_term.lower() or
                keyword_lower in item.definition.lower() or
                any(keyword_lower in s.lower() for s in item.synonyms)):
                results.append(item)

        return results

    def get_term_by_nci_code(
        self,
        nci_code: str,
        version: str = None
    ) -> Optional[TerminologyItem]:
        """Get term by NCI C-code"""
        version = version or self.default_version

        # Search all codelists
        for codelist in self._codelist_index.get(version, {}).values():
            for item in codelist.items:
                if item.nci_code == nci_code:
                    return item
        return None

    def get_codelist_for_variable(
        self,
        variable_name: str,
        domain: str = None,
        version: str = None
    ) -> Optional[CodeList]:
        """
        Get appropriate codelist for a variable.

        Args:
            variable_name: SDTM/ADaM variable (e.g., "SEX", "AESEV")
            domain: Domain context (e.g., "DM", "AE")
            version: CT version

        Returns:
            CodeList or None
        """
        # Map variables to codelists
        VARIABLE_CODELIST_MAP = {
            "SEX": "Sex",
            "RACE": "Race",
            "ETHNIC": "Ethnicity",
            "AESEV": "Severity/Intensity Scale for Adverse Events",
            "AESER": "Yes/No Response",
            "AEREL": "Causality",
            "NRIND": "Reference Range Indicator",
            "PARAMCD": "Parameter Code",
            "AVAL": None,  # Numeric, no codelist
            "TRTA": "Treatment",
        }

        codelist_name = VARIABLE_CODELIST_MAP.get(variable_name)
        if codelist_name:
            return self.get_codelist(codelist_name, version)
        return None

    def validate_adam_dataset(
        self,
        dataset_data: Dict,
        dataset_name: str,
        version: str = None
    ) -> List[str]:
        """
        Validate ADaM dataset against CT.

        Args:
            dataset_data: Dataset as dict with variable columns
            dataset_name: "ADSL", "ADTTE", etc.
            version: CT version

        Returns:
            List of validation errors
        """
        errors = []

        # Define variables to validate per dataset
        VALIDATION_MAP = {
            "ADSL": ["SEX", "RACE", "ETHNIC"],
            "ADTTE": ["PARAMCD"],
            "ADEFF": ["PARAMCD"],
            "ADAE": ["AESEV", "AESER", "AEREL"],
        }

        variables_to_check = VALIDATION_MAP.get(dataset_name, [])

        for var in variables_to_check:
            if var in dataset_data:
                codelist = self.get_codelist_for_variable(var, version=version)
                if codelist:
                    valid_values = {item.submission_value for item in codelist.items}

                    # Check each value
                    for value in dataset_data[var]:
                        if value and value not in valid_values:
                            errors.append(
                                f"{dataset_name}.{var}: Invalid value '{value}' "
                                f"(not in codelist '{codelist.name}')"
                            )

        return errors

    # Private helper methods

    def _load_from_cache(
        self,
        cache_file: Path,
        version: str,
        package_type: str
    ) -> TerminologyPackage:
        """Load package from JSON cache"""
        with open(cache_file, 'r') as f:
            data = json.load(f)

        package = TerminologyPackage(
            package_name=data['metadata']['package_name'],
            version=version,
            effective_date=data['metadata']['effective_date'],
            package_type=package_type,
            metadata=data['metadata']
        )

        # Parse codelists
        for cl_code, cl_data in data['codelists'].items():
            codelist = CodeList(
                code=cl_code,
                name=cl_data['name'],
                submission_value=cl_data.get('submission_value', cl_data['name']),
                extensible=cl_data['extensible'] == "Yes",
                definition=cl_data['definition']
            )

            # Parse items
            for item_data in cl_data['items']:
                item = TerminologyItem(
                    nci_code=item_data['code'],
                    submission_value=item_data['submission_value'],
                    preferred_term=item_data['preferred_term'],
                    definition=item_data.get('definition', ''),
                    synonyms=item_data.get('synonyms', []),
                    extensible=codelist.extensible,
                    codelist_code=cl_code
                )
                codelist.items.append(item)

            package.codelists[cl_data['name']] = codelist

        return package

    def _save_to_cache(self, package: TerminologyPackage, cache_file: Path):
        """Save package to JSON cache"""
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            'metadata': {
                'package_name': package.package_name,
                'version': package.version,
                'effective_date': package.effective_date,
                'package_type': package.package_type,
                'cached_at': datetime.now().isoformat(),
            },
            'codelists': {}
        }

        for name, codelist in package.codelists.items():
            data['codelists'][codelist.code] = {
                'name': name,
                'submission_value': codelist.submission_value,
                'extensible': "Yes" if codelist.extensible else "No",
                'definition': codelist.definition,
                'items': [
                    {
                        'code': item.nci_code,
                        'submission_value': item.submission_value,
                        'preferred_term': item.preferred_term,
                        'definition': item.definition,
                        'synonyms': item.synonyms
                    }
                    for item in codelist.items
                ]
            }

        with open(cache_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _download_from_nci_evs(
        self,
        version: str,
        package_type: str
    ) -> TerminologyPackage:
        """Download CT package from NCI EVS API"""
        from .nci_evs_client import NCIEVSClient

        client = NCIEVSClient(cache_dir=self.cache_dir)
        return client.download_package(version, package_type)

    def _index_package(self, package: TerminologyPackage, version: str):
        """Index package for fast lookup"""
        if version not in self._codelist_index:
            self._codelist_index[version] = {}

        for name, codelist in package.codelists.items():
            self._codelist_index[version][name] = codelist


# Singleton instance
_terminology_service: Optional[CDISCTerminologyService] = None


def get_terminology_service(
    cache_dir: Path = None,
    version: str = "2024-09-27",
    use_legacy: bool = False
) -> CDISCTerminologyService:
    """
    Factory function for terminology service.

    Args:
        cache_dir: Directory for cached CT files
        version: Default CT version
        use_legacy: If True, returns legacy hardcoded adapter

    Returns:
        CDISCTerminologyService instance
    """
    global _terminology_service

    if use_legacy:
        from .legacy_terminology_adapter import LegacyTerminologyAdapter
        return LegacyTerminologyAdapter()

    if _terminology_service is None:
        _terminology_service = CDISCTerminologyService(
            cache_dir=cache_dir,
            default_version=version
        )

    return _terminology_service
