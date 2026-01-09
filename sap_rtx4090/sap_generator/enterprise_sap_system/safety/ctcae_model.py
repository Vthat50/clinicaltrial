"""
CTCAE (Common Terminology Criteria for Adverse Events) Data Models
===================================================================

Implements CTCAE v5.0 and v6.0 for adverse event grading in oncology trials.

CTCAE is the FDA standard for grading severity of adverse events.
Published by NCI: https://ctep.cancer.gov/protocoldevelopment/electronic_applications/ctc.htm
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from enum import Enum


class CTCAEVersion(Enum):
    """CTCAE versions"""
    V5_0 = "5.0"
    V6_0 = "6.0"


class CTCAEGrade(Enum):
    """CTCAE severity grades"""
    GRADE_1 = 1  # Mild; asymptomatic or mild symptoms; clinical or diagnostic observations only; intervention not indicated
    GRADE_2 = 2  # Moderate; minimal, local or noninvasive intervention indicated; limiting age-appropriate instrumental ADL
    GRADE_3 = 3  # Severe or medically significant but not immediately life-threatening; hospitalization or prolongation of hospitalization indicated; disabling; limiting self care ADL
    GRADE_4 = 4  # Life-threatening consequences; urgent intervention indicated
    GRADE_5 = 5  # Death related to adverse event


class CTCAECategory(Enum):
    """CTCAE system organ classes"""
    BLOOD_LYMPHATIC = "Blood and lymphatic system disorders"
    CARDIAC = "Cardiac disorders"
    CONGENITAL = "Congenital, familial and genetic disorders"
    EAR_LABYRINTH = "Ear and labyrinth disorders"
    ENDOCRINE = "Endocrine disorders"
    EYE = "Eye disorders"
    GASTROINTESTINAL = "Gastrointestinal disorders"
    GENERAL = "General disorders and administration site conditions"
    HEPATOBILIARY = "Hepatobiliary disorders"
    IMMUNE = "Immune system disorders"
    INFECTIONS = "Infections and infestations"
    INJURY_POISONING = "Injury, poisoning and procedural complications"
    INVESTIGATIONS = "Investigations"
    METABOLISM = "Metabolism and nutrition disorders"
    MUSCULOSKELETAL = "Musculoskeletal and connective tissue disorders"
    NEOPLASMS = "Neoplasms benign, malignant and unspecified"
    NERVOUS = "Nervous system disorders"
    PREGNANCY = "Pregnancy, puerperium and perinatal conditions"
    PSYCHIATRIC = "Psychiatric disorders"
    RENAL_URINARY = "Renal and urinary disorders"
    REPRODUCTIVE = "Reproductive system and breast disorders"
    RESPIRATORY = "Respiratory, thoracic and mediastinal disorders"
    SKIN = "Skin and subcutaneous tissue disorders"
    SURGICAL = "Surgical and medical procedures"
    VASCULAR = "Vascular disorders"


@dataclass
class CTCAEGradeDefinition:
    """Definition for a specific grade of an adverse event"""
    grade: int
    description: str
    clinical_criteria: str = ""
    lab_criteria: str = ""


@dataclass
class CTCAETerm:
    """
    Individual CTCAE term (adverse event).

    Each term has grade definitions 1-5 and belongs to a category.
    """
    term_id: str                      # e.g., "10019211" (MedDRA code)
    term_name: str                    # e.g., "Fatigue"
    category: CTCAECategory

    # Grade definitions
    grade_definitions: Dict[int, CTCAEGradeDefinition] = field(default_factory=dict)

    # Additional metadata
    definition: str = ""              # Overall term definition

    # MedDRA mapping
    meddra_code: str = ""             # MedDRA LLT code
    meddra_pt: str = ""               # MedDRA Preferred Term
    meddra_soc: str = ""              # MedDRA System Organ Class

    # Version info
    ctcae_version: str = "5.0"

    # Navigation
    see_also: List[str] = field(default_factory=list)  # Related terms

    def get_grade_description(self, grade: int) -> str:
        """Get description for a specific grade"""
        if grade in self.grade_definitions:
            return self.grade_definitions[grade].description
        return ""

    def has_grade(self, grade: int) -> bool:
        """Check if term has a specific grade"""
        return grade in self.grade_definitions

    def get_max_grade(self) -> int:
        """Get maximum grade defined for this term"""
        if self.grade_definitions:
            return max(self.grade_definitions.keys())
        return 0


@dataclass
class CTCAEAdverseEvent:
    """
    Recorded adverse event with CTCAE grading.

    Represents an actual AE occurrence in a trial.
    """
    term: CTCAETerm
    grade: int
    subject_id: str

    # Timing
    onset_date: str = ""
    resolution_date: str = ""
    ongoing: bool = False

    # Classification
    serious: bool = False             # Serious adverse event (SAE)
    treatment_related: bool = False   # Relationship to study treatment
    action_taken: str = ""            # e.g., "Dose reduced", "Drug interrupted"
    outcome: str = ""                 # e.g., "Resolved", "Ongoing", "Fatal"

    # Details
    verbatim_term: str = ""           # Original investigator term
    body_system: str = ""             # Body system affected

    def is_ctcae_grade_3_or_higher(self) -> bool:
        """Check if AE is Grade 3+"""
        return self.grade >= 3

    def is_treatment_emergent(self, treatment_start_date: str) -> bool:
        """Check if AE is treatment-emergent (occurred after treatment start)"""
        if not self.onset_date or not treatment_start_date:
            return False
        return self.onset_date >= treatment_start_date


@dataclass
class CTCAESafetyProfile:
    """
    Summary safety profile for a subject or cohort.

    Aggregates AEs by grade, category, and severity.
    """
    subject_id: str = ""
    cohort: str = ""

    # Adverse events
    adverse_events: List[CTCAEAdverseEvent] = field(default_factory=list)

    # Summary counts
    total_aes: int = 0
    grade_1_2_count: int = 0
    grade_3_4_5_count: int = 0
    serious_ae_count: int = 0

    # Most common AEs
    most_common_aes: Dict[str, int] = field(default_factory=dict)  # term -> count

    def add_adverse_event(self, ae: CTCAEAdverseEvent):
        """Add an adverse event to the profile"""
        self.adverse_events.append(ae)
        self.total_aes += 1

        if ae.grade in [1, 2]:
            self.grade_1_2_count += 1
        elif ae.grade in [3, 4, 5]:
            self.grade_3_4_5_count += 1

        if ae.serious:
            self.serious_ae_count += 1

        # Update most common
        term_name = ae.term.term_name
        self.most_common_aes[term_name] = self.most_common_aes.get(term_name, 0) + 1

    def get_grade_distribution(self) -> Dict[int, int]:
        """Get distribution of AEs by grade"""
        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for ae in self.adverse_events:
            if ae.grade in distribution:
                distribution[ae.grade] += 1
        return distribution

    def get_category_distribution(self) -> Dict[str, int]:
        """Get distribution of AEs by CTCAE category"""
        distribution = {}
        for ae in self.adverse_events:
            cat_name = ae.term.category.value
            distribution[cat_name] = distribution.get(cat_name, 0) + 1
        return distribution

    def get_treatment_related_aes(self) -> List[CTCAEAdverseEvent]:
        """Get only treatment-related AEs"""
        return [ae for ae in self.adverse_events if ae.treatment_related]


@dataclass
class CTCAEGradingRules:
    """
    Grading rules and guidance for specific scenarios.

    Provides standardized rules for AE grading.
    """
    rule_id: str
    rule_name: str
    description: str

    # Applicability
    applies_to_terms: List[str] = field(default_factory=list)
    applies_to_categories: List[CTCAECategory] = field(default_factory=list)

    # Grading guidance
    grading_criteria: Dict[int, str] = field(default_factory=dict)  # grade -> criteria

    # Special cases
    dose_modification_threshold: int = 3  # Grade at which dose modification typically considered
    hospitalization_threshold: int = 3    # Grade typically requiring hospitalization

    # Examples
    examples: List[Dict] = field(default_factory=list)


# Common CTCAE Terms (embedded core set)
COMMON_CTCAE_TERMS = {
    # Hematologic
    "anemia": {
        "term_id": "10002034",
        "term_name": "Anemia",
        "category": CTCAECategory.BLOOD_LYMPHATIC,
        "grades": {
            1: "Hemoglobin (Hgb) <LLN - 10.0 g/dL; <LLN - 6.2 mmol/L; <LLN - 100 g/L",
            2: "Hgb <10.0 - 8.0 g/dL; <6.2 - 4.9 mmol/L; <100 - 80 g/L",
            3: "Hgb <8.0 g/dL; <4.9 mmol/L; <80 g/L; transfusion indicated",
            4: "Life-threatening consequences; urgent intervention indicated",
            5: "Death"
        }
    },
    "neutropenia": {
        "term_id": "10029354",
        "term_name": "Neutrophil count decreased",
        "category": CTCAECategory.INVESTIGATIONS,
        "grades": {
            1: "<LLN - 1500/mm3; <LLN - 1.5 x 10^9/L",
            2: "<1500 - 1000/mm3; <1.5 - 1.0 x 10^9/L",
            3: "<1000 - 500/mm3; <1.0 - 0.5 x 10^9/L",
            4: "<500/mm3; <0.5 x 10^9/L",
            5: "Death"
        }
    },
    "thrombocytopenia": {
        "term_id": "10043554",
        "term_name": "Platelet count decreased",
        "category": CTCAECategory.INVESTIGATIONS,
        "grades": {
            1: "<LLN - 75,000/mm3; <LLN - 75.0 x 10^9/L",
            2: "<75,000 - 50,000/mm3; <75.0 - 50.0 x 10^9/L",
            3: "<50,000 - 25,000/mm3; <50.0 - 25.0 x 10^9/L",
            4: "<25,000/mm3; <25.0 x 10^9/L",
            5: "Death"
        }
    },

    # Constitutional
    "fatigue": {
        "term_id": "10016256",
        "term_name": "Fatigue",
        "category": CTCAECategory.GENERAL,
        "grades": {
            1: "Fatigue relieved by rest",
            2: "Fatigue not relieved by rest; limiting instrumental ADL",
            3: "Fatigue not relieved by rest; limiting self care ADL",
            4: "-",
            5: "-"
        }
    },

    # Gastrointestinal
    "nausea": {
        "term_id": "10028813",
        "term_name": "Nausea",
        "category": CTCAECategory.GASTROINTESTINAL,
        "grades": {
            1: "Loss of appetite without alteration in eating habits",
            2: "Oral intake decreased without significant weight loss, dehydration or malnutrition",
            3: "Inadequate oral caloric or fluid intake; tube feeding, TPN, or hospitalization indicated",
            4: "-",
            5: "-"
        }
    },
    "diarrhea": {
        "term_id": "10012735",
        "term_name": "Diarrhea",
        "category": CTCAECategory.GASTROINTESTINAL,
        "grades": {
            1: "Increase of <4 stools per day over baseline; mild increase in ostomy output compared to baseline",
            2: "Increase of 4-6 stools per day over baseline; moderate increase in ostomy output compared to baseline",
            3: "Increase of >=7 stools per day over baseline; incontinence; hospitalization indicated; severe increase in ostomy output compared to baseline; limiting self care ADL",
            4: "Life-threatening consequences; urgent intervention indicated",
            5: "Death"
        }
    },

    # Hepatic
    "alt_increased": {
        "term_id": "10001551",
        "term_name": "Alanine aminotransferase increased",
        "category": CTCAECategory.INVESTIGATIONS,
        "grades": {
            1: ">ULN - 3.0 x ULN",
            2: ">3.0 - 5.0 x ULN",
            3: ">5.0 - 20.0 x ULN",
            4: ">20.0 x ULN",
            5: "Death"
        }
    },
    "ast_increased": {
        "term_id": "10003481",
        "term_name": "Aspartate aminotransferase increased",
        "category": CTCAECategory.INVESTIGATIONS,
        "grades": {
            1: ">ULN - 3.0 x ULN",
            2: ">3.0 - 5.0 x ULN",
            3: ">5.0 - 20.0 x ULN",
            4: ">20.0 x ULN",
            5: "Death"
        }
    },

    # Renal
    "creatinine_increased": {
        "term_id": "10011368",
        "term_name": "Creatinine increased",
        "category": CTCAECategory.INVESTIGATIONS,
        "grades": {
            1: ">ULN - 1.5 x ULN",
            2: ">1.5 - 3.0 x ULN",
            3: ">3.0 - 6.0 x ULN",
            4: ">6.0 x ULN",
            5: "Death"
        }
    },

    # Neurologic
    "peripheral_neuropathy": {
        "term_id": "10034620",
        "term_name": "Peripheral sensory neuropathy",
        "category": CTCAECategory.NERVOUS,
        "grades": {
            1: "Asymptomatic; loss of deep tendon reflexes or paresthesia",
            2: "Moderate symptoms; limiting instrumental ADL",
            3: "Severe symptoms; limiting self care ADL",
            4: "Life-threatening consequences; urgent intervention indicated",
            5: "Death"
        }
    },
}
