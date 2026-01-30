"""
EU Clinical Trials Information System (CTIS) Extractor
Extracts trial data from CTIS public API (EU trials from Jan 31, 2022 onwards)
API: https://euclinicaltrials.eu/ctis-public-api/
"""

import requests
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)


class CTISExtractor:
    """
    Extract trial data from EU CTIS public API.
    CTIS covers trials under EU CTR (Regulation 536/2014) from Jan 31, 2022 onwards.
    """

    BASE_URL = "https://euclinicaltrials.eu/ctis-public-api/v1"

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'SAP-Generator-Enterprise/1.0'
        })

    def fetch(self, ctis_id: str) -> Dict:
        """
        Fetch trial data from CTIS.

        Args:
            ctis_id: CTIS ID (format: CT-EU-YY-NNNNNN)

        Returns:
            Dict with extracted trial data
        """
        facts = {
            'registry': 'CTIS',
            'trial_id': ctis_id,
            'api_success': False,
            'api_error': None
        }

        try:
            # Get trial details
            url = f"{self.BASE_URL}/clinical-trials/{ctis_id}"
            logger.debug(f"Fetching CTIS trial: {url}")

            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            # Extract key fields
            facts.update(self._parse_trial_data(data))
            facts['api_success'] = True

            logger.info(f"Successfully fetched CTIS trial: {ctis_id}")

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                facts['api_error'] = f"Trial not found: {ctis_id}"
                logger.warning(f"CTIS trial not found: {ctis_id}")
            else:
                facts['api_error'] = f"HTTP error: {e.response.status_code}"
                logger.error(f"CTIS HTTP error for {ctis_id}: {e}")
        except requests.exceptions.RequestException as e:
            facts['api_error'] = str(e)
            logger.error(f"CTIS API error for {ctis_id}: {e}")
        except Exception as e:
            facts['api_error'] = f"Unexpected error: {str(e)}"
            logger.error(f"CTIS parsing error for {ctis_id}: {e}")

        return facts

    def _parse_trial_data(self, data: Dict) -> Dict:
        """Parse CTIS JSON response into standardized facts"""
        facts = {}

        # Basic information
        facts['title'] = self._get_nested(data, 'protocolTitle', 'en', default='')
        facts['sponsor'] = self._extract_sponsor(data.get('sponsorDetails', {}))

        # Phase
        phase_code = self._get_nested(data, 'phase', 'code')
        facts['phase'] = self._map_phase(phase_code)

        # Study design
        design = data.get('trialInformation', {}).get('trialDesign', {})
        facts['allocation'] = self._get_nested(design, 'randomisation', 'label', default='')
        facts['masking'] = self._get_nested(design, 'blinding', 'label', default='')
        facts['intervention_model'] = self._get_nested(design, 'studyType', 'label', default='')

        # Sample size
        facts['sample_size'] = self._get_nested(data, 'trialInformation', 'sampleSize', default=0)

        # Therapeutic area
        conditions = data.get('medicalConditions', [])
        if conditions:
            facts['condition'] = self._get_nested(conditions[0], 'name', 'en', default='')

        # Status and dates
        status_info = data.get('trialStatus', {})
        facts['status'] = self._get_nested(status_info, 'status', 'label', default='')
        facts['start_date'] = status_info.get('startDate', '')

        # Countries
        countries = data.get('memberStatesInvolved', [])
        facts['countries'] = [c.get('countryCode') for c in countries if c.get('countryCode')]

        # Endpoints (if available in public data)
        endpoints = data.get('endpoints', {})
        facts['primary_endpoints'] = self._extract_endpoints(endpoints.get('primary', []))
        facts['secondary_endpoints'] = self._extract_endpoints(endpoints.get('secondary', []))

        # Interventions
        interventions = data.get('interventions', [])
        facts['interventions'] = self._extract_interventions(interventions)

        return facts

    def _extract_sponsor(self, sponsor_details: Dict) -> str:
        """Extract sponsor name from nested structure"""
        if not sponsor_details:
            return ""

        name = sponsor_details.get('name', {})
        if isinstance(name, dict):
            return name.get('en', name.get('value', ''))
        return str(name) if name else ""

    def _map_phase(self, phase_code: str) -> str:
        """Map CTIS phase codes to standard phases"""
        if not phase_code:
            return "Unknown"

        PHASE_MAP = {
            'human-pharmacology': 'Phase 1',
            'therapeutic-exploratory': 'Phase 2',
            'therapeutic-confirmatory': 'Phase 3',
            'therapeutic-use': 'Phase 4',
            'phase-1': 'Phase 1',
            'phase-2': 'Phase 2',
            'phase-3': 'Phase 3',
            'phase-4': 'Phase 4',
        }
        return PHASE_MAP.get(phase_code.lower(), phase_code)

    def _extract_endpoints(self, endpoints_list: List[Dict]) -> List[Dict]:
        """Extract endpoint information"""
        extracted = []

        for ep in endpoints_list:
            endpoint = {
                'name': self._get_nested(ep, 'endpointDescription', 'en', default=''),
                'timeframe': self._get_nested(ep, 'timeframe', 'en', default=''),
            }
            if endpoint['name']:  # Only add if we got a name
                extracted.append(endpoint)

        return extracted

    def _extract_interventions(self, interventions_list: List[Dict]) -> List[Dict]:
        """Extract intervention information"""
        extracted = []

        for interv in interventions_list:
            intervention = {
                'name': self._get_nested(interv, 'name', 'en', default=''),
                'type': self._get_nested(interv, 'type', 'label', default=''),
            }
            if intervention['name']:
                extracted.append(intervention)

        return extracted

    def _get_nested(self, data: Dict, *keys, default=None):
        """
        Safely get nested dictionary values.

        Args:
            data: Dictionary to traverse
            *keys: Keys to traverse
            default: Default value if key path doesn't exist

        Returns:
            Value at key path or default
        """
        result = data
        for key in keys:
            if isinstance(result, dict):
                result = result.get(key)
                if result is None:
                    return default
            else:
                return default
        return result if result is not None else default

    def search_trials(
        self,
        condition: str = None,
        sponsor: str = None,
        phase: str = None,
        country: str = None
    ) -> List[Dict]:
        """
        Search CTIS trials.

        Args:
            condition: Medical condition
            sponsor: Sponsor name
            phase: Trial phase
            country: Country code (e.g., "DE", "FR")

        Returns:
            List of matching trials
        """
        try:
            params = {}
            if condition:
                params['medicalCondition'] = condition
            if sponsor:
                params['sponsor'] = sponsor
            if phase:
                params['phase'] = phase
            if country:
                params['memberState'] = country

            response = self.session.get(
                f"{self.BASE_URL}/clinical-trials/search",
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()
            return data.get('clinicalTrials', [])

        except Exception as e:
            logger.error(f"CTIS search error: {e}")
            return []

    def get_trial_status(self, ctis_id: str) -> Optional[str]:
        """
        Get current status of a trial.

        Args:
            ctis_id: CTIS trial ID

        Returns:
            Status string or None
        """
        data = self.fetch(ctis_id)
        if data and data.get('api_success'):
            return data.get('status')
        return None
