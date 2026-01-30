"""
NCI EVS REST API Client
Interfaces with https://api-evsrest.nci.nih.gov/api/v1
"""

import requests
from typing import Dict, List, Optional
from pathlib import Path
import json
import logging
from dataclasses import dataclass
from .terminology_service import TerminologyPackage, CodeList, TerminologyItem

logger = logging.getLogger(__name__)


class NCIEVSClient:
    """
    Client for NCI EVS REST API.
    API Documentation: https://api-evsrest.nci.nih.gov/swagger-ui.html
    """

    BASE_URL = "https://api-evsrest.nci.nih.gov/api/v1"
    TERMINOLOGY = "ncit"  # NCI Thesaurus

    # CDISC subset codes
    CDISC_SUBSETS = {
        "SDTM": "C81222",
        "ADaM": "C81223",
        "CDASH": "C81224",
        "Define-XML": "C81225",
        "Protocol": "C81226",
    }

    def __init__(self, cache_dir: Path = None, timeout: int = 30):
        self.cache_dir = cache_dir
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'SAP-Generator-Enterprise/1.0'
        })

    def get_latest_version(self) -> str:
        """Get latest CDISC CT version from NCI EVS"""
        try:
            # NCI EVS versions endpoint
            response = self.session.get(
                f"{self.BASE_URL}/metadata/{self.TERMINOLOGY}/versions",
                timeout=self.timeout
            )
            response.raise_for_status()
            versions = response.json()

            # Return latest version
            if versions:
                return versions[0]['version']

            return "2024-09-27"  # Fallback

        except Exception as e:
            logger.error(f"Error fetching latest version: {e}")
            return "2024-09-27"

    def download_package(
        self,
        version: str,
        package_type: str
    ) -> TerminologyPackage:
        """
        Download complete CT package for a specific version and type.

        Args:
            version: CT version (e.g., "2024-09-27")
            package_type: "SDTM", "ADaM", "Protocol", "Define-XML"

        Returns:
            TerminologyPackage with all codelists
        """
        logger.info(f"Downloading {package_type} CT package version {version}")

        subset_code = self.CDISC_SUBSETS.get(package_type)
        if not subset_code:
            raise ValueError(f"Unknown package type: {package_type}")

        # Get all codelists in subset
        codelists = self._get_codelists_in_subset(subset_code)

        package = TerminologyPackage(
            package_name=f"{package_type.lower()}-terminology-{version}",
            version=version,
            effective_date=version,
            package_type=package_type
        )

        # Download each codelist
        for codelist_code in codelists:
            try:
                codelist = self._download_codelist(codelist_code)
                if codelist:
                    package.codelists[codelist.name] = codelist
                    logger.info(f"  Downloaded codelist: {codelist.name} ({len(codelist.items)} items)")
            except Exception as e:
                logger.error(f"  Failed to download codelist {codelist_code}: {e}")

        logger.info(f"Downloaded {len(package.codelists)} codelists")
        return package

    def _get_codelists_in_subset(self, subset_code: str) -> List[str]:
        """Get all codelist codes in a CDISC subset"""
        try:
            # Get concept children (codelists are children of subset)
            response = self.session.get(
                f"{self.BASE_URL}/concept/{self.TERMINOLOGY}/{subset_code}/descendants",
                params={"fromRecord": 0, "pageSize": 1000},
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            # Extract codelist codes
            codelists = [item['code'] for item in data]
            return codelists

        except Exception as e:
            logger.error(f"Error getting codelists for subset {subset_code}: {e}")
            return []

    def _download_codelist(self, codelist_code: str) -> Optional[CodeList]:
        """Download a single codelist with all items"""
        try:
            # Get codelist concept details
            response = self.session.get(
                f"{self.BASE_URL}/concept/{self.TERMINOLOGY}/{codelist_code}",
                params={
                    "include": "minimal,definitions,synonyms,children,properties"
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            concept = response.json()

            # Parse codelist metadata
            codelist = CodeList(
                code=codelist_code,
                name=concept.get('name', ''),
                submission_value=self._get_property(concept, 'CDISC Submission Value'),
                extensible=self._get_property(concept, 'Extensible List') == "Yes",
                definition=self._get_definition(concept)
            )

            # Get codelist items (children)
            children = concept.get('children', [])
            for child_ref in children:
                item = self._download_codelist_item(child_ref['code'])
                if item:
                    item.codelist_code = codelist_code
                    item.extensible = codelist.extensible
                    codelist.items.append(item)

            return codelist

        except Exception as e:
            logger.error(f"Error downloading codelist {codelist_code}: {e}")
            return None

    def _download_codelist_item(self, item_code: str) -> Optional[TerminologyItem]:
        """Download a single codelist item"""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/concept/{self.TERMINOLOGY}/{item_code}",
                params={"include": "minimal,definitions,synonyms,properties"},
                timeout=self.timeout
            )
            response.raise_for_status()
            concept = response.json()

            item = TerminologyItem(
                nci_code=item_code,
                submission_value=self._get_property(concept, 'CDISC Submission Value'),
                preferred_term=concept.get('name', ''),
                definition=self._get_definition(concept),
                synonyms=self._get_synonyms(concept)
            )

            return item

        except Exception as e:
            logger.error(f"Error downloading item {item_code}: {e}")
            return None

    def search_cdisc_terms(
        self,
        query: str,
        package_type: str = "SDTM"
    ) -> List[Dict]:
        """
        Search CDISC terminology.

        Args:
            query: Search term
            package_type: Subset to search within

        Returns:
            List of matching concepts
        """
        try:
            subset_code = self.CDISC_SUBSETS.get(package_type)

            response = self.session.get(
                f"{self.BASE_URL}/concept/{self.TERMINOLOGY}/search",
                params={
                    "term": query,
                    "subset": subset_code,
                    "include": "minimal",
                    "fromRecord": 0,
                    "pageSize": 100
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json().get('concepts', [])

        except Exception as e:
            logger.error(f"Error searching for '{query}': {e}")
            return []

    # Helper methods

    def _get_property(self, concept: Dict, property_name: str) -> str:
        """Extract property value from concept"""
        properties = concept.get('properties', [])
        for prop in properties:
            if prop.get('type') == property_name:
                return prop.get('value', '')
        return ''

    def _get_definition(self, concept: Dict) -> str:
        """Extract definition from concept"""
        definitions = concept.get('definitions', [])
        for defn in definitions:
            if defn.get('type') == 'DEFINITION':
                return defn.get('definition', '')
        return ''

    def _get_synonyms(self, concept: Dict) -> List[str]:
        """Extract synonyms from concept"""
        synonyms = concept.get('synonyms', [])
        return [syn.get('name', '') for syn in synonyms if syn.get('name')]
