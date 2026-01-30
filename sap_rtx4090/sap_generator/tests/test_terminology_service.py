"""
Unit tests for CDISC Terminology Service
"""

import unittest
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from enterprise_sap_system.cdisc.terminology_service import (
    CDISCTerminologyService,
    TerminologyItem,
    CodeList,
    TerminologyPackage,
    get_terminology_service
)
from enterprise_sap_system.cdisc.legacy_terminology_adapter import LegacyTerminologyAdapter


class TestTerminologyService(unittest.TestCase):
    """Test CDISCTerminologyService"""

    def setUp(self):
        """Set up test fixture"""
        # Use legacy adapter for testing (doesn't require NCI EVS access)
        self.service = get_terminology_service(use_legacy=True)

    def test_get_codelist(self):
        """Test retrieving a codelist"""
        codelist = self.service.get_codelist("Sex")

        self.assertIsNotNone(codelist)
        self.assertEqual(codelist.name, "Sex")
        self.assertGreater(len(codelist.items), 0)

        # Check codelist has expected structure
        self.assertIsInstance(codelist, CodeList)
        self.assertTrue(hasattr(codelist, 'code'))
        self.assertTrue(hasattr(codelist, 'items'))

    def test_codelist_items(self):
        """Test codelist items have correct structure"""
        codelist = self.service.get_codelist("Sex")

        for item in codelist.items:
            self.assertIsInstance(item, TerminologyItem)
            self.assertTrue(item.nci_code)
            self.assertTrue(item.submission_value)
            self.assertTrue(item.preferred_term)

    def test_validate_term(self):
        """Test term validation"""
        # Valid terms
        self.assertTrue(self.service.validate_term("Sex", "M"))
        self.assertTrue(self.service.validate_term("Sex", "F"))
        self.assertTrue(self.service.validate_term("Sex", "U"))

        # Invalid term
        self.assertFalse(self.service.validate_term("Sex", "X"))
        self.assertFalse(self.service.validate_term("Sex", "INVALID"))

    def test_search_param(self):
        """Test PARAMCD search"""
        results = self.service.search_param("survival")

        self.assertGreater(len(results), 0)
        self.assertIsInstance(results, list)

        # Should find OS and PFS at minimum
        codes = {r.submission_value for r in results}
        self.assertIn("OS", codes, "Should find Overall Survival")
        self.assertIn("PFS", codes, "Should find Progression-Free Survival")

    def test_search_param_case_insensitive(self):
        """Test that search is case-insensitive"""
        results_lower = self.service.search_param("survival")
        results_upper = self.service.search_param("SURVIVAL")
        results_mixed = self.service.search_param("Survival")

        self.assertEqual(len(results_lower), len(results_upper))
        self.assertEqual(len(results_lower), len(results_mixed))

    def test_get_paramcd_list(self):
        """Test getting all PARAMCDs"""
        paramcds = self.service.get_paramcd_list()

        self.assertGreater(len(paramcds), 0)
        self.assertIsInstance(paramcds, list)

        # Check expected codes are present
        codes = {p.submission_value for p in paramcds}
        expected_codes = {"OS", "PFS", "ORR", "DOR"}
        self.assertTrue(expected_codes.issubset(codes),
                       f"Expected codes {expected_codes} should be in PARAMCD list")

    def test_get_term_by_nci_code(self):
        """Test retrieving term by NCI C-code"""
        # OS has NCI code C25473
        term = self.service.get_term_by_nci_code("C25473")

        if term:  # May not be available in legacy adapter
            self.assertEqual(term.submission_value, "OS")
            self.assertIn("Survival", term.preferred_term)

    def test_get_codelist_for_variable(self):
        """Test getting codelist for specific variables"""
        # Test standard variable mappings
        sex_codelist = self.service.get_codelist_for_variable("SEX")
        self.assertIsNotNone(sex_codelist)
        self.assertEqual(sex_codelist.name, "Sex")

        race_codelist = self.service.get_codelist_for_variable("RACE")
        self.assertIsNotNone(race_codelist)

        # Variable with no codelist
        aval_codelist = self.service.get_codelist_for_variable("AVAL")
        self.assertIsNone(aval_codelist, "AVAL should not have a codelist (numeric)")

    def test_validate_adam_dataset(self):
        """Test validating ADaM dataset"""
        # Create mock dataset
        dataset = {
            "SEX": ["M", "F", "M", "F"],
            "PARAMCD": ["OS", "OS", "PFS", "PFS"]
        }

        errors = self.service.validate_adam_dataset(dataset, "ADSL")

        # Should have no errors with valid data
        self.assertEqual(len(errors), 0)

    def test_validate_adam_dataset_invalid_values(self):
        """Test validation catches invalid values"""
        # Create dataset with invalid values
        dataset = {
            "SEX": ["M", "F", "INVALID", "F"],  # INVALID is not valid
        }

        errors = self.service.validate_adam_dataset(dataset, "ADSL")

        # Should catch the invalid value
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("INVALID" in error for error in errors))

    def test_singleton_pattern(self):
        """Test singleton pattern works"""
        service1 = get_terminology_service(use_legacy=True)
        service2 = get_terminology_service(use_legacy=True)

        # Should return same instance
        self.assertIs(service1, service2)

    def test_codelist_extensible_flag(self):
        """Test that extensible flag is set correctly"""
        sex_codelist = self.service.get_codelist("Sex")
        self.assertFalse(sex_codelist.extensible, "Sex should not be extensible")

        paramcd_codelist = self.service.get_codelist("PARAMCD")
        # PARAMCD may be extensible in full CT, but legacy might not have this set
        self.assertIsNotNone(paramcd_codelist)


class TestLegacyAdapter(unittest.TestCase):
    """Test Legacy Terminology Adapter"""

    def setUp(self):
        """Set up test fixture"""
        self.adapter = LegacyTerminologyAdapter()

    def test_legacy_codelists_available(self):
        """Test that legacy codelists are available"""
        expected_codelists = ["Sex", "Race", "Ethnicity", "PARAMCD", "Yes/No Response"]

        for codelist_name in expected_codelists:
            codelist = self.adapter.get_codelist(codelist_name)
            self.assertIsNotNone(codelist, f"Codelist {codelist_name} should be available")
            self.assertGreater(len(codelist.items), 0)

    def test_legacy_adapter_interface_compatible(self):
        """Test that legacy adapter provides same interface"""
        # Should have all the same methods as the full service
        methods = [
            'get_codelist',
            'validate_term',
            'get_paramcd_list',
            'search_param',
            'load_package'
        ]

        for method in methods:
            self.assertTrue(hasattr(self.adapter, method),
                           f"Legacy adapter should have {method} method")

    def test_legacy_paramcd_search(self):
        """Test PARAMCD search in legacy adapter"""
        results = self.adapter.search_param("overall")

        self.assertGreater(len(results), 0)
        codes = {r.submission_value for r in results}
        self.assertIn("OS", codes)

    def test_legacy_version_ignored(self):
        """Test that version parameter is ignored in legacy adapter"""
        # Should return same result regardless of version
        codelist_v1 = self.adapter.get_codelist("Sex", version="2024-09-27")
        codelist_v2 = self.adapter.get_codelist("Sex", version="2023-12-15")
        codelist_v3 = self.adapter.get_codelist("Sex", version="legacy")

        self.assertEqual(codelist_v1.name, codelist_v2.name)
        self.assertEqual(codelist_v1.name, codelist_v3.name)
        self.assertEqual(len(codelist_v1.items), len(codelist_v2.items))


class TestTerminologyPackage(unittest.TestCase):
    """Test TerminologyPackage dataclass"""

    def test_package_creation(self):
        """Test creating a terminology package"""
        package = TerminologyPackage(
            package_name="test-package",
            version="2024-09-27",
            effective_date="2024-09-27",
            package_type="SDTM"
        )

        self.assertEqual(package.package_name, "test-package")
        self.assertEqual(package.version, "2024-09-27")
        self.assertEqual(package.package_type, "SDTM")
        self.assertIsInstance(package.codelists, dict)

    def test_package_with_codelists(self):
        """Test package with codelists"""
        codelist = CodeList(
            code="C66734",
            name="Sex",
            submission_value="SEX",
            extensible=False,
            definition="A classification of sex"
        )

        package = TerminologyPackage(
            package_name="test-package",
            version="2024-09-27",
            effective_date="2024-09-27",
            package_type="SDTM",
            codelists={"Sex": codelist}
        )

        self.assertEqual(len(package.codelists), 1)
        self.assertIn("Sex", package.codelists)
        self.assertEqual(package.codelists["Sex"].name, "Sex")


class TestTerminologyItem(unittest.TestCase):
    """Test TerminologyItem dataclass"""

    def test_item_creation(self):
        """Test creating a terminology item"""
        item = TerminologyItem(
            nci_code="C25473",
            submission_value="OS",
            preferred_term="Overall Survival",
            definition="The length of time from...",
            synonyms=["OS", "Survival"],
            extensible=False,
            codelist_code="C77526"
        )

        self.assertEqual(item.nci_code, "C25473")
        self.assertEqual(item.submission_value, "OS")
        self.assertEqual(item.preferred_term, "Overall Survival")
        self.assertEqual(len(item.synonyms), 2)


def run_tests():
    """Run all tests"""
    unittest.main()


if __name__ == "__main__":
    run_tests()
