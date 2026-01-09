"""
CTCAE Service
=============

Provides access to CTCAE v5.0 and v6.0 terms for adverse event grading.

Features:
- Search CTCAE terms
- Get grading criteria
- Validate AE coding
- Generate safety tables specifications
"""

from typing import List, Dict, Optional, Set
from pathlib import Path
import logging

from .ctcae_model import (
    CTCAETerm,
    CTCAEGradeDefinition,
    CTCAECategory,
    CTCAEVersion,
    CTCAEGrade,
    CTCAEAdverseEvent,
    CTCAESafetyProfile,
    COMMON_CTCAE_TERMS
)

logger = logging.getLogger(__name__)


class CTCAEService:
    """
    Service for accessing CTCAE terminology and grading criteria.

    Provides standardized AE terminology for oncology trials.
    """

    def __init__(self, version: str = "5.0"):
        """
        Initialize CTCAE service.

        Args:
            version: CTCAE version ("5.0" or "6.0")
        """
        self.version = version
        self._terms_cache: Dict[str, CTCAETerm] = {}
        self._name_index: Dict[str, str] = {}  # term_name -> term_id
        self._category_index: Dict[CTCAECategory, List[str]] = {}  # category -> term_ids

        # Load CTCAE terms
        self._load_ctcae_terms()

    def _load_ctcae_terms(self):
        """Load CTCAE terms into cache"""
        logger.info(f"Loading CTCAE {self.version} terms...")

        # Load common terms from embedded data
        for term_key, term_data in COMMON_CTCAE_TERMS.items():
            term = CTCAETerm(
                term_id=term_data["term_id"],
                term_name=term_data["term_name"],
                category=term_data["category"],
                ctcae_version=self.version
            )

            # Add grade definitions
            for grade, description in term_data["grades"].items():
                grade_def = CTCAEGradeDefinition(
                    grade=grade,
                    description=description
                )
                term.grade_definitions[grade] = grade_def

            # Cache term
            self._terms_cache[term.term_id] = term
            self._name_index[term.term_name.lower()] = term.term_id

            # Index by category
            if term.category not in self._category_index:
                self._category_index[term.category] = []
            self._category_index[term.category].append(term.term_id)

        logger.info(f"Loaded {len(self._terms_cache)} CTCAE terms")

    def get_term(self, term_id: str) -> Optional[CTCAETerm]:
        """
        Get CTCAE term by ID.

        Args:
            term_id: CTCAE term ID

        Returns:
            CTCAETerm or None
        """
        return self._terms_cache.get(term_id)

    def get_term_by_name(self, term_name: str) -> Optional[CTCAETerm]:
        """
        Get CTCAE term by name.

        Args:
            term_name: CTCAE term name (e.g., "Fatigue")

        Returns:
            CTCAETerm or None
        """
        term_id = self._name_index.get(term_name.lower())
        if term_id:
            return self._terms_cache.get(term_id)
        return None

    def search_terms(self, query: str) -> List[CTCAETerm]:
        """
        Search CTCAE terms by keyword.

        Args:
            query: Search keyword

        Returns:
            List of matching terms
        """
        query_lower = query.lower()
        matching_terms = []

        for term in self._terms_cache.values():
            if (query_lower in term.term_name.lower() or
                query_lower in term.definition.lower()):
                matching_terms.append(term)

        return matching_terms

    def get_terms_by_category(self, category: CTCAECategory) -> List[CTCAETerm]:
        """
        Get all terms in a category.

        Args:
            category: CTCAE category

        Returns:
            List of terms in category
        """
        term_ids = self._category_index.get(category, [])
        return [self._terms_cache[tid] for tid in term_ids if tid in self._terms_cache]

    def get_grading_criteria(self, term_name: str) -> Dict[int, str]:
        """
        Get grading criteria for a term.

        Args:
            term_name: CTCAE term name

        Returns:
            Dict mapping grade -> description
        """
        term = self.get_term_by_name(term_name)
        if not term:
            return {}

        return {
            grade: defn.description
            for grade, defn in term.grade_definitions.items()
        }

    def validate_ae_grade(self, term_name: str, grade: int) -> bool:
        """
        Validate that a grade is valid for a term.

        Args:
            term_name: CTCAE term name
            grade: Grade (1-5)

        Returns:
            True if valid, False otherwise
        """
        term = self.get_term_by_name(term_name)
        if not term:
            return False

        return term.has_grade(grade)

    def get_all_categories(self) -> List[CTCAECategory]:
        """Get all CTCAE categories with terms"""
        return list(self._category_index.keys())

    def get_hematologic_terms(self) -> List[CTCAETerm]:
        """Get all hematologic AE terms (labs)"""
        return self.get_terms_by_category(CTCAECategory.BLOOD_LYMPHATIC) + \
               [t for t in self._terms_cache.values()
                if 'count decreased' in t.term_name.lower() or
                   'count increased' in t.term_name.lower()]

    def get_lab_terms(self) -> List[CTCAETerm]:
        """Get all laboratory AE terms"""
        return self.get_terms_by_category(CTCAECategory.INVESTIGATIONS)

    def get_dose_limiting_toxicity_terms(self) -> List[CTCAETerm]:
        """
        Get common dose-limiting toxicity (DLT) terms.

        Returns terms typically used for DLT assessment in Phase 1 trials.
        """
        dlt_term_names = [
            "Anemia",
            "Neutrophil count decreased",
            "Platelet count decreased",
            "Febrile neutropenia",
            "Alanine aminotransferase increased",
            "Aspartate aminotransferase increased",
            "Creatinine increased",
            "Nausea",
            "Vomiting",
            "Diarrhea"
        ]

        dlt_terms = []
        for name in dlt_term_names:
            term = self.get_term_by_name(name)
            if term:
                dlt_terms.append(term)

        return dlt_terms

    def create_safety_table_spec(
        self,
        include_all_grades: bool = True,
        include_grade_3_plus: bool = True,
        include_serious: bool = True,
        by_category: bool = True
    ) -> Dict[str, Any]:
        """
        Generate safety table specifications for SAP.

        Args:
            include_all_grades: Include table with all grades
            include_grade_3_plus: Include table with Grade 3+ only
            include_serious: Include serious AE table
            by_category: Group by CTCAE category

        Returns:
            Dict with table specifications
        """
        spec = {
            "tables": [],
            "grading_system": f"CTCAE {self.version}",
            "categories": [cat.value for cat in self.get_all_categories()]
        }

        if include_all_grades:
            spec["tables"].append({
                "name": "Treatment-Emergent Adverse Events (All Grades)",
                "description": "Summary of all treatment-emergent AEs by preferred term and maximum grade",
                "population": "Safety population",
                "columns": ["Preferred Term", "Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5", "Any Grade"],
                "sort_by": "Frequency descending",
                "grouping": "CTCAE category" if by_category else None
            })

        if include_grade_3_plus:
            spec["tables"].append({
                "name": "Treatment-Emergent Adverse Events (Grade 3+)",
                "description": "Summary of Grade 3, 4, or 5 treatment-emergent AEs",
                "population": "Safety population",
                "columns": ["Preferred Term", "Grade 3", "Grade 4", "Grade 5", "Grade 3+"],
                "sort_by": "Frequency descending",
                "grouping": "CTCAE category" if by_category else None,
                "threshold": "Include terms with >=2 subjects affected"
            })

        if include_serious:
            spec["tables"].append({
                "name": "Serious Adverse Events",
                "description": "Summary of serious adverse events (SAEs)",
                "population": "Safety population",
                "columns": ["Preferred Term", "Number of Subjects", "Percentage"],
                "sort_by": "Frequency descending",
                "note": "An SAE is any AE that results in death, is life-threatening, requires hospitalization, results in persistent disability, or is a congenital anomaly"
            })

        return spec

    def generate_ae_analysis_methods(self) -> str:
        """
        Generate standard text for AE analysis methods in SAP.

        Returns:
            Formatted text for SAP
        """
        methods_text = f"""
## Adverse Event Analysis

### Coding and Grading

Adverse events will be coded using MedDRA version [XX.X] and graded according to the National Cancer Institute (NCI) Common Terminology Criteria for Adverse Events (CTCAE) version {self.version}.

### Analysis Populations

- **Safety Population**: All subjects who received at least one dose of study treatment
- **Treatment-Emergent AEs (TEAEs)**: AEs with onset date on or after the first dose of study treatment and up to 30 days after the last dose

### Adverse Event Summaries

The following adverse event summaries will be provided:

1. **Overall Summary of AEs**: Number and percentage of subjects with:
   - Any TEAE
   - Grade 3-5 TEAEs
   - Serious AEs
   - TEAEs leading to dose modification
   - TEAEs leading to discontinuation
   - Deaths

2. **TEAEs by Preferred Term and Maximum Grade**: Frequency and percentage of subjects experiencing each AE, tabulated by maximum CTCAE grade (Grade 1, 2, 3, 4, 5) and grouped by System Organ Class (SOC).

3. **Grade 3+ TEAEs**: Summary of Grade 3, 4, or 5 TEAEs occurring in ≥2 subjects in any treatment group.

4. **Serious Adverse Events**: Summary of all SAEs by preferred term.

5. **Treatment-Related AEs**: Summary of AEs assessed by the investigator as related to study treatment.

### Analysis Methods

- AEs will be summarized by treatment group using counts and percentages
- Percentages will be based on the number of subjects in the safety population
- Each subject will be counted once per preferred term at the maximum grade experienced
- AE tables will be sorted by descending frequency in the experimental arm
- No formal statistical testing will be performed for AE comparisons
"""
        return methods_text.strip()


# Singleton instance
_ctcae_service: Optional[CTCAEService] = None


def get_ctcae_service(version: str = "5.0") -> CTCAEService:
    """
    Get singleton CTCAE service instance.

    Args:
        version: CTCAE version

    Returns:
        CTCAEService instance
    """
    global _ctcae_service

    if _ctcae_service is None:
        _ctcae_service = CTCAEService(version=version)

    return _ctcae_service
