"""
Unit tests for Registry Router and ClinicalTrials.gov Extractor
"""

import unittest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from enterprise_sap_system.core.registries.registry_router import (
    RegistryRouter,
    RegistryType,
    TrialIdentifier,
    get_registry_router
)
from enterprise_sap_system.core.registries.clinicaltrials_gov_extractor import (
    ClinicalTrialsGovExtractor
)


class TestRegistryRouter(unittest.TestCase):
    """Test Registry Router"""

    def setUp(self):
        """Set up test fixture"""
        self.router = RegistryRouter()

    def test_detect_nct_id(self):
        """Test NCT ID detection"""
        identifier = self.router.detect_registry("NCT01234567")

        self.assertEqual(identifier.registry_type, RegistryType.CLINICALTRIALS_GOV)
        self.assertEqual(identifier.normalized_id, "NCT01234567")
        self.assertIn("clinicaltrials.gov", identifier.registry_url)

    def test_detect_nct_case_insensitive(self):
        """Test NCT ID detection is case insensitive"""
        identifier = self.router.detect_registry("nct01234567")

        self.assertEqual(identifier.registry_type, RegistryType.CLINICALTRIALS_GOV)
        self.assertEqual(identifier.normalized_id, "NCT01234567")

    def test_detect_ctis_id(self):
        """Test CTIS ID detection"""
        identifier = self.router.detect_registry("CT-EU-00-001234")

        self.assertEqual(identifier.registry_type, RegistryType.CTIS)
        self.assertEqual(identifier.normalized_id, "CT-EU-00-001234")
        self.assertIn("euclinicaltrials.eu", identifier.registry_url)

    def test_fuzzy_nct_matching(self):
        """Test fuzzy matching for NCT IDs embedded in text"""
        text = "This is a study protocol for NCT01234567 version 2.0"
        identifier = self.router.detect_registry(text)

        self.assertEqual(identifier.registry_type, RegistryType.CLINICALTRIALS_GOV)
        self.assertEqual(identifier.normalized_id, "NCT01234567")

    def test_fuzzy_ctis_matching(self):
        """Test fuzzy matching for CTIS IDs"""
        text = "EU trial CT-EU-22-123456 in oncology"
        identifier = self.router.detect_registry(text)

        self.assertEqual(identifier.registry_type, RegistryType.CTIS)
        self.assertEqual(identifier.normalized_id, "CT-EU-22-123456")

    def test_unknown_id_format(self):
        """Test unknown ID format"""
        identifier = self.router.detect_registry("ABC-123-XYZ")

        self.assertEqual(identifier.registry_type, RegistryType.UNKNOWN)

    def test_empty_string(self):
        """Test empty string"""
        identifier = self.router.detect_registry("")

        self.assertEqual(identifier.registry_type, RegistryType.UNKNOWN)

    def test_is_supported_nct(self):
        """Test if NCT ID is supported"""
        self.assertTrue(self.router.is_supported("NCT01234567"))

    def test_is_not_supported_unknown(self):
        """Test unknown ID is not supported"""
        self.assertFalse(self.router.is_supported("UNKNOWN-123"))

    def test_get_supported_registries(self):
        """Test getting list of supported registries"""
        registries = self.router.get_supported_registries()

        self.assertIsInstance(registries, list)
        self.assertIn("clinicaltrials.gov", registries)

    def test_singleton_pattern(self):
        """Test singleton pattern for router"""
        router1 = get_registry_router()
        router2 = get_registry_router()

        self.assertIs(router1, router2)


class TestClinicalTrialsGovExtractor(unittest.TestCase):
    """Test ClinicalTrials.gov Extractor"""

    def setUp(self):
        """Set up test fixture"""
        self.extractor = ClinicalTrialsGovExtractor()

    def test_extract_nct_single(self):
        """Test extracting single NCT ID"""
        text = "This study NCT01234567 is for cancer treatment"
        nct_id = self.extractor.extract_nct_id(text)

        self.assertEqual(nct_id, "NCT01234567")

    def test_extract_nct_multiple_with_context(self):
        """Test extracting correct NCT ID when multiple are present"""
        text = """
        Statistical Analysis Plan for Protocol CA209-078, NCT02031458

        This document describes the statistical analysis for this study.
        The study is similar to prior study NCT01234567 and NCT09876543.
        """
        nct_id = self.extractor.extract_nct_id(text)

        # Should select NCT02031458 (near "this study" and protocol number)
        # not the reference studies
        self.assertEqual(nct_id, "NCT02031458")

    def test_extract_nct_from_beginning(self):
        """Test extracting NCT ID from beginning of document"""
        text = "NCT02031458: Phase 3 Study of Drug X\n\nThis is a randomized trial..."
        nct_id = self.extractor.extract_nct_id(text)

        self.assertEqual(nct_id, "NCT02031458")

    def test_extract_nct_no_match(self):
        """Test when no NCT ID present"""
        text = "This is a clinical trial without an NCT number"
        nct_id = self.extractor.extract_nct_id(text)

        self.assertIsNone(nct_id)

    def test_extract_nct_case_insensitive(self):
        """Test NCT extraction is case insensitive"""
        text = "Study nct01234567 for diabetes"
        nct_id = self.extractor.extract_nct_id(text)

        self.assertEqual(nct_id, "NCT01234567")

    def test_fetch_real_nct(self):
        """Test fetching real NCT ID from ClinicalTrials.gov"""
        # Use a well-known completed trial
        nct_id = "NCT03197467"  # CheckMate 078 (published study)

        result = self.extractor.fetch(nct_id)

        self.assertTrue(result.get('api_success'), f"API error: {result.get('api_error')}")
        self.assertEqual(result.get('trial_id'), nct_id)
        self.assertIn('title', result)
        self.assertIn('sponsor', result)
        self.assertIn('phase', result)

    def test_fetch_invalid_nct(self):
        """Test fetching invalid NCT ID"""
        result = self.extractor.fetch("NCT00000000")

        self.assertFalse(result.get('api_success'))
        self.assertIn('api_error', result)

    def test_fetch_includes_endpoints(self):
        """Test that fetch includes endpoint data"""
        # Known trial with endpoints
        result = self.extractor.fetch("NCT03197467")

        if result.get('api_success'):
            self.assertIn('primary_endpoints', result)
            self.assertIn('secondary_endpoints', result)
            self.assertIsInstance(result['primary_endpoints'], list)
            self.assertIsInstance(result['secondary_endpoints'], list)

    def test_fetch_includes_design_info(self):
        """Test that fetch includes design information"""
        result = self.extractor.fetch("NCT03197467")

        if result.get('api_success'):
            self.assertIn('is_randomized', result)
            self.assertIn('is_blinded', result)
            self.assertIn('phase', result)
            self.assertIn('allocation', result)

    def test_therapeutic_area_inference(self):
        """Test therapeutic area inference from conditions"""
        # Test with oncology keywords
        conditions = ["Non-Small Cell Lung Cancer", "Advanced Solid Tumors"]
        area = self.extractor._infer_therapeutic_area(conditions)

        self.assertEqual(area, "oncology")

    def test_therapeutic_area_inference_immunology(self):
        """Test therapeutic area inference for immunology"""
        conditions = ["Rheumatoid Arthritis", "Psoriasis"]
        area = self.extractor._infer_therapeutic_area(conditions)

        self.assertEqual(area, "immunology")

    def test_drug_name_extraction(self):
        """Test drug name extraction from interventions"""
        interventions = [
            {"name": "Nivolumab", "type": "DRUG"},
            {"name": "Docetaxel", "type": "DRUG"},
        ]
        drug_name = self.extractor._extract_drug_name(interventions)

        self.assertEqual(drug_name, "Nivolumab")

    def test_drug_name_extraction_biological(self):
        """Test drug name extraction with BIOLOGICAL type"""
        interventions = [
            {"name": "Pembrolizumab", "type": "BIOLOGICAL"},
        ]
        drug_name = self.extractor._extract_drug_name(interventions)

        self.assertEqual(drug_name, "Pembrolizumab")

    def test_validate_nct_id_valid(self):
        """Test NCT ID validation with matching document"""
        # Use a real NCT ID
        nct_id = "NCT03197467"

        # Fetch real data
        api_data = self.extractor.fetch(nct_id)

        # Create document text with matching info
        if api_data.get('api_success'):
            document_text = f"""
            Statistical Analysis Plan for {nct_id}
            Sponsor: {api_data.get('sponsor', '')}
            Drug: {api_data.get('drug_name', '')}
            Title: {api_data.get('title', '')}
            """

            result = self.extractor.validate_nct_id(nct_id, document_text, threshold=0.3)

            self.assertTrue(result['valid'])
            self.assertGreater(result['confidence'], 0.3)

    def test_validate_nct_id_invalid(self):
        """Test NCT ID validation with non-matching document"""
        nct_id = "NCT03197467"
        document_text = "This is about a completely different study with no matching info"

        result = self.extractor.validate_nct_id(nct_id, document_text, threshold=0.3)

        # Should have low confidence
        self.assertLess(result['confidence'], 0.3)


class TestRegistryRouterIntegration(unittest.TestCase):
    """Integration tests for Registry Router"""

    def setUp(self):
        """Set up test fixture"""
        self.router = RegistryRouter()

    def test_fetch_nct_through_router(self):
        """Test fetching NCT ID through router"""
        result = self.router.fetch("NCT03197467")

        if result:
            self.assertTrue(result.get('api_success'), f"Error: {result.get('api_error')}")
            self.assertEqual(result.get('registry'), 'ClinicalTrials.gov')
            self.assertIn('_registry_info', result)

    def test_registry_info_metadata(self):
        """Test that router adds registry metadata"""
        result = self.router.fetch("NCT03197467")

        if result and result.get('api_success'):
            self.assertIn('_registry_info', result)
            registry_info = result['_registry_info']

            self.assertIn('registry', registry_info)
            self.assertIn('original_id', registry_info)
            self.assertIn('normalized_id', registry_info)
            self.assertIn('registry_url', registry_info)

    def test_fetch_unknown_returns_none(self):
        """Test that unknown ID format returns None"""
        result = self.router.fetch("UNKNOWN-123-ABC")

        self.assertIsNone(result)


def run_tests():
    """Run all tests"""
    # Run tests with verbosity
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestRegistryRouter))
    suite.addTests(loader.loadTestsFromTestCase(TestClinicalTrialsGovExtractor))
    suite.addTests(loader.loadTestsFromTestCase(TestRegistryRouterIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
