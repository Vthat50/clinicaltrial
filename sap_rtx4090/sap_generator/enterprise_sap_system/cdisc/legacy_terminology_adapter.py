"""
Legacy Terminology Adapter
Provides backward compatibility by wrapping hardcoded codelists in the new terminology service interface.
Enables gradual migration without breaking existing code.
"""

from typing import Dict, List, Optional
from .terminology_service import CDISCTerminologyService, CodeList, TerminologyItem, TerminologyPackage
from dataclasses import field


class LegacyTerminologyAdapter(CDISCTerminologyService):
    """
    Adapter that provides the new interface but uses legacy hardcoded values.
    Enables gradual migration without breaking existing code.
    """

    # Legacy hardcoded codelists (minimal set for backward compatibility)
    LEGACY_CODELISTS = {
        "Sex": {
            "code": "C66734",
            "items": [
                {"code": "C16576", "value": "F", "term": "Female"},
                {"code": "C20197", "value": "M", "term": "Male"},
                {"code": "C17998", "value": "U", "term": "Unknown"},
                {"code": "C45908", "value": "UNDIFFERENTIATED", "term": "Undifferentiated"},
            ]
        },
        "Race": {
            "code": "C74457",
            "items": [
                {"code": "C41219", "value": "WHITE", "term": "White"},
                {"code": "C16352", "value": "BLACK OR AFRICAN AMERICAN", "term": "Black or African American"},
                {"code": "C41260", "value": "ASIAN", "term": "Asian"},
                {"code": "C41261", "value": "AMERICAN INDIAN OR ALASKA NATIVE", "term": "American Indian or Alaska Native"},
                {"code": "C41219", "value": "NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER", "term": "Native Hawaiian or Other Pacific Islander"},
                {"code": "C17998", "value": "UNKNOWN", "term": "Unknown"},
            ]
        },
        "Ethnicity": {
            "code": "C66790",
            "items": [
                {"code": "C41237", "value": "HISPANIC OR LATINO", "term": "Hispanic or Latino"},
                {"code": "C41222", "value": "NOT HISPANIC OR LATINO", "term": "Not Hispanic or Latino"},
                {"code": "C17998", "value": "UNKNOWN", "term": "Unknown"},
            ]
        },
        "Yes/No Response": {
            "code": "C66742",
            "items": [
                {"code": "C49488", "value": "Y", "term": "Yes"},
                {"code": "C49487", "value": "N", "term": "No"},
            ]
        },
        "PARAMCD": {
            "code": "C77526",
            "items": [
                {"code": "C25473", "value": "OS", "term": "Overall Survival"},
                {"code": "C16929", "value": "PFS", "term": "Progression-Free Survival"},
                {"code": "C49501", "value": "DFS", "term": "Disease-Free Survival"},
                {"code": "C114465", "value": "EFS", "term": "Event-Free Survival"},
                {"code": "C18060", "value": "ORR", "term": "Objective Response Rate"},
                {"code": "C49501", "value": "DOR", "term": "Duration of Response"},
                {"code": "C49555", "value": "DCR", "term": "Disease Control Rate"},
                {"code": "C49501", "value": "TTP", "term": "Time to Progression"},
                {"code": "C70969", "value": "TTF", "term": "Time to Treatment Failure"},
                {"code": "C100447", "value": "PCR", "term": "Pathologic Complete Response"},
                {"code": "C15313", "value": "BOR", "term": "Best Overall Response"},
            ]
        },
        "Severity/Intensity Scale for Adverse Events": {
            "code": "C66769",
            "items": [
                {"code": "C41334", "value": "MILD", "term": "Mild"},
                {"code": "C41337", "value": "MODERATE", "term": "Moderate"},
                {"code": "C41339", "value": "SEVERE", "term": "Severe"},
            ]
        },
        "Causality": {
            "code": "C66737",
            "items": [
                {"code": "C53258", "value": "RELATED", "term": "Related"},
                {"code": "C53257", "value": "NOT RELATED", "term": "Not Related"},
                {"code": "C48660", "value": "UNLIKELY RELATED", "term": "Unlikely Related"},
                {"code": "C48661", "value": "POSSIBLY RELATED", "term": "Possibly Related"},
                {"code": "C48662", "value": "PROBABLY RELATED", "term": "Probably Related"},
            ]
        },
        "Reference Range Indicator": {
            "code": "C66788",
            "items": [
                {"code": "C78802", "value": "LOW", "term": "Low"},
                {"code": "C78800", "value": "HIGH", "term": "High"},
                {"code": "C78802", "value": "NORMAL", "term": "Normal"},
            ]
        },
    }

    def __init__(self):
        # Don't call super().__init__ to avoid cache directory setup
        self.default_version = "legacy"
        self._packages = {}
        self._codelist_index = {}

        # Build legacy package
        self._build_legacy_package()

    def _build_legacy_package(self):
        """Build legacy package from hardcoded values"""
        package = TerminologyPackage(
            package_name="legacy-terminology",
            version="legacy",
            effective_date="legacy",
            package_type="SDTM"
        )

        for name, data in self.LEGACY_CODELISTS.items():
            codelist = CodeList(
                code=data["code"],
                name=name,
                submission_value=name,
                extensible=False,
                definition=f"Legacy codelist: {name}"
            )

            for item_data in data["items"]:
                item = TerminologyItem(
                    nci_code=item_data["code"],
                    submission_value=item_data["value"],
                    preferred_term=item_data["term"],
                    definition="",
                    codelist_code=data["code"]
                )
                codelist.items.append(item)

            package.codelists[name] = codelist

        self._packages["legacy"] = package
        self._codelist_index["legacy"] = package.codelists

    def load_package(self, version: str, package_type: str) -> TerminologyPackage:
        """Return legacy package (ignores version)"""
        return self._packages["legacy"]

    def get_codelist(self, codelist_name: str, version: str = None) -> Optional[CodeList]:
        """Get from legacy codelists (ignores version)"""
        return self._codelist_index.get("legacy", {}).get(codelist_name)

    def validate_term(self, codelist_name: str, value: str, version: str = None) -> bool:
        """Validate using legacy codelists"""
        codelist = self.get_codelist(codelist_name)
        if not codelist:
            return False

        valid_values = {item.submission_value for item in codelist.items}
        return value in valid_values

    def get_paramcd_list(self, version: str = None) -> List[TerminologyItem]:
        """Get PARAMCD list from legacy data"""
        codelist = self.get_codelist("PARAMCD")
        if not codelist:
            return []
        return codelist.items

    def search_param(self, keyword: str, version: str = None) -> List[TerminologyItem]:
        """Search PARAMCDs in legacy data"""
        paramcd_list = self.get_paramcd_list()
        keyword_lower = keyword.lower()

        results = []
        for item in paramcd_list:
            if (keyword_lower in item.preferred_term.lower() or
                keyword_lower in item.submission_value.lower()):
                results.append(item)

        return results
