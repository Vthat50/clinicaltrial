"""
Regulatory Standards Knowledge Base
====================================

Authoritative reference for SAP regulatory requirements:
- Coding dictionaries (MedDRA, WHO-DD, CTCAE)
- Standard TEAE summary types
- ICH E9 R1 estimand framework
- Therapeutic area-specific requirements

Sources:
- ICH E9 (R1): Statistical Principles for Clinical Trials
- FDA Guidance: Safety Assessment for IND Safety Reporting
- CDISC Standards
- Industry best practices from 300+ SAPs

Last Updated: 2025-01
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


# =============================================================================
# CODING DICTIONARY STANDARDS
# =============================================================================

class CodingStandards:
    """Current versions of standard coding dictionaries."""

    # Adverse Event Coding
    MEDDRA = {
        "name": "Medical Dictionary for Regulatory Activities",
        "abbreviation": "MedDRA",
        "current_version": "26.1",
        "release_date": "September 2023",
        "organization": "ICH",
        "usage": "Coding of adverse events, medical history, indications",
        "hierarchy": ["SOC", "HLGT", "HLT", "PT", "LLT"],
        "note": "Version should match sponsor's standard at time of database lock"
    }

    # Medication Coding
    WHO_DRUG = {
        "name": "WHO Drug Dictionary Enhanced",
        "abbreviation": "WHO-DDE",
        "current_version": "March 2024",
        "organization": "Uppsala Monitoring Centre",
        "usage": "Coding of concomitant and prior medications",
        "classification": "ATC (Anatomical Therapeutic Chemical)",
        "note": "Version typically specified as month/year of release"
    }

    # Adverse Event Grading
    CTCAE = {
        "name": "Common Terminology Criteria for Adverse Events",
        "abbreviation": "NCI-CTCAE",
        "current_version": "5.0",
        "release_date": "November 27, 2017",
        "organization": "National Cancer Institute",
        "usage": "Grading severity of adverse events (Grade 1-5)",
        "grades": {
            1: "Mild; asymptomatic or mild symptoms",
            2: "Moderate; minimal, local or noninvasive intervention",
            3: "Severe or medically significant but not life-threatening",
            4: "Life-threatening consequences; urgent intervention indicated",
            5: "Death related to AE"
        },
        "note": "CTCAE v5.0 is current standard; v4.03 still used in ongoing trials"
    }


# =============================================================================
# STANDARD TEAE SUMMARY TYPES
# =============================================================================

class TEAESummaryTypes:
    """Standard TEAE summary table types per industry conventions."""

    # Core TEAE Tables (Required)
    CORE_TABLES = [
        {
            "id": "TEAE_OVERVIEW",
            "title": "Overview of Adverse Events",
            "description": "High-level summary of AE categories",
            "columns": ["Category", "n (%)", "Events"],
            "rows": [
                "Any TEAE",
                "Any treatment-related AE",
                "Any serious AE",
                "Any Grade ≥3 AE",
                "Any AE leading to discontinuation",
                "Any AE leading to dose modification",
                "Deaths"
            ]
        },
        {
            "id": "TEAE_SOC_PT",
            "title": "TEAEs by System Organ Class and Preferred Term",
            "description": "Detailed TEAE listing by MedDRA hierarchy",
            "columns": ["SOC / Preferred Term", "Any Grade n (%)", "Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5"],
            "sorting": "SOC alphabetical or by frequency; PT by frequency within SOC"
        },
        {
            "id": "TEAE_PT_FREQUENCY",
            "title": "TEAEs by Preferred Term (≥X% incidence)",
            "description": "Most common TEAEs",
            "threshold": "Typically ≥5% or ≥10% in any arm",
            "columns": ["Preferred Term", "Treatment A n (%)", "Treatment B n (%)", "Total n (%)"]
        }
    ]

    # Relationship Tables
    RELATIONSHIP_TABLES = [
        {
            "id": "TRAE_SOC_PT",
            "title": "Treatment-Related Adverse Events by SOC and PT",
            "description": "TEAEs assessed as related to study treatment",
            "relationship": ["Related", "Possibly related"],
            "columns": ["SOC / Preferred Term", "Any Grade n (%)", "Grade ≥3 n (%)"]
        },
        {
            "id": "TRAE_PT_FREQUENCY",
            "title": "Treatment-Related AEs by PT (≥X% incidence)",
            "description": "Most common treatment-related TEAEs"
        }
    ]

    # Severity Tables
    SEVERITY_TABLES = [
        {
            "id": "TEAE_GRADE3_PLUS",
            "title": "Grade 3 or Higher TEAEs by SOC and PT",
            "description": "Severe and life-threatening TEAEs",
            "grades": [3, 4, 5]
        },
        {
            "id": "TRAE_GRADE3_PLUS",
            "title": "Grade 3 or Higher Treatment-Related AEs by SOC and PT",
            "description": "Severe treatment-related TEAEs"
        }
    ]

    # Outcome Tables
    OUTCOME_TABLES = [
        {
            "id": "SAE_SOC_PT",
            "title": "Serious Adverse Events by SOC and PT",
            "description": "All serious TEAEs",
            "columns": ["SOC / Preferred Term", "n (%)", "Grade"]
        },
        {
            "id": "TEAE_DISCONTINUATION",
            "title": "TEAEs Leading to Study Drug Discontinuation",
            "description": "AEs resulting in permanent treatment discontinuation",
            "columns": ["SOC / Preferred Term", "n (%)", "Worst Grade"]
        },
        {
            "id": "TEAE_DOSE_MODIFICATION",
            "title": "TEAEs Leading to Dose Modification",
            "description": "AEs resulting in dose reduction, interruption, or delay",
            "subtypes": ["Dose reduction", "Dose interruption", "Dose delay"]
        },
        {
            "id": "DEATHS",
            "title": "Deaths",
            "description": "All deaths with cause and relationship",
            "columns": ["Subject", "Cause of Death", "Days on Study", "Relationship"]
        }
    ]

    # Special Interest Tables
    SPECIAL_INTEREST_TABLES = [
        {
            "id": "AESI",
            "title": "Adverse Events of Special Interest",
            "description": "Protocol-defined AESIs (e.g., infusion reactions, immune-related AEs)",
            "note": "Categories defined in protocol"
        },
        {
            "id": "INFUSION_REACTIONS",
            "title": "Infusion-Related Reactions",
            "description": "AEs identified as part of infusion reaction",
            "applicable_to": ["IV infusion drugs", "biologics"]
        }
    ]

    @classmethod
    def get_all_tables(cls) -> List[Dict]:
        """Return all standard TEAE table types."""
        all_tables = []
        all_tables.extend(cls.CORE_TABLES)
        all_tables.extend(cls.RELATIONSHIP_TABLES)
        all_tables.extend(cls.SEVERITY_TABLES)
        all_tables.extend(cls.OUTCOME_TABLES)
        all_tables.extend(cls.SPECIAL_INTEREST_TABLES)
        return all_tables

    @classmethod
    def get_table_ids(cls) -> List[str]:
        """Return list of all table IDs."""
        return [t["id"] for t in cls.get_all_tables()]


# =============================================================================
# ICH E9 R1 ESTIMAND FRAMEWORK
# =============================================================================

class EstimandFramework:
    """ICH E9 R1 Estimand Framework components."""

    COMPONENTS = {
        "population": {
            "description": "The patients targeted by the clinical question",
            "examples": ["All randomized patients", "Patients with confirmed diagnosis",
                        "Patients who received at least one dose"]
        },
        "treatment": {
            "description": "The treatment condition(s) of interest",
            "examples": ["Treatment as randomized", "Treatment as received",
                        "Treatment regimen including rescue medication"]
        },
        "endpoint": {
            "description": "The variable that reflects patient outcomes",
            "examples": ["Overall survival", "Change from baseline in tumor size",
                        "Proportion with response"]
        },
        "intercurrent_events": {
            "description": "Events occurring after treatment initiation that affect interpretation",
            "examples": ["Treatment discontinuation", "Use of rescue medication",
                        "Death from other causes"],
            "strategies": {
                "treatment_policy": "Occurrence is irrelevant; use all data regardless",
                "composite": "Event is incorporated into the endpoint definition",
                "hypothetical": "Scenario where event would not occur",
                "principal_stratum": "Subpopulation where event does not occur",
                "while_on_treatment": "Response while on treatment, before event"
            }
        },
        "population_summary": {
            "description": "The summary measure for the population",
            "examples": ["Difference in means", "Hazard ratio", "Odds ratio",
                        "Difference in proportions"]
        }
    }

    STANDARD_ESTIMANDS = {
        "efficacy_itt": {
            "name": "ITT Efficacy Estimand",
            "population": "All randomized patients",
            "treatment": "Treatment as assigned",
            "intercurrent_event_strategy": "treatment_policy",
            "description": "Estimates treatment effect in all randomized patients regardless of adherence"
        },
        "efficacy_per_protocol": {
            "name": "Per-Protocol Efficacy Estimand",
            "population": "Patients without major protocol deviations",
            "treatment": "Treatment as received per protocol",
            "intercurrent_event_strategy": "principal_stratum",
            "description": "Estimates treatment effect under ideal protocol adherence"
        },
        "safety": {
            "name": "Safety Estimand",
            "population": "All patients who received at least one dose",
            "treatment": "Treatment as received",
            "intercurrent_event_strategy": "while_on_treatment",
            "description": "Estimates safety profile while on treatment"
        }
    }


# =============================================================================
# THERAPEUTIC AREA SPECIFIC STANDARDS
# =============================================================================

class OncologyStandards:
    """Oncology-specific SAP standards."""

    RESPONSE_CRITERIA = {
        "RECIST_1.1": {
            "name": "Response Evaluation Criteria in Solid Tumors v1.1",
            "reference": "Eisenhauer et al. Eur J Cancer 2009;45:228-247",
            "categories": ["CR", "PR", "SD", "PD", "NE"],
            "applicable_to": "Solid tumors"
        },
        "iRECIST": {
            "name": "Immune RECIST",
            "reference": "Seymour et al. Lancet Oncol 2017;18:e143-52",
            "categories": ["iCR", "iPR", "iSD", "iUPD", "iCPD"],
            "applicable_to": "Immunotherapy trials"
        },
        "RANO": {
            "name": "Response Assessment in Neuro-Oncology",
            "applicable_to": "CNS tumors"
        },
        "Lugano": {
            "name": "Lugano Classification",
            "reference": "Cheson et al. J Clin Oncol 2014",
            "applicable_to": "Lymphoma"
        },
        "GCIG": {
            "name": "Gynecologic Cancer InterGroup Criteria",
            "reference": "Rustin et al. Int J Gynecol Cancer 2011",
            "applicable_to": "Ovarian cancer",
            "includes_CA125": True
        },
        "IWG": {
            "name": "International Working Group Criteria",
            "applicable_to": "Hematologic malignancies"
        }
    }

    SURVIVAL_ENDPOINTS = {
        "OS": {
            "name": "Overall Survival",
            "definition": "Time from randomization to death from any cause",
            "analysis_method": "Kaplan-Meier, Log-rank test, Cox regression",
            "censoring": "Last known alive date"
        },
        "PFS": {
            "name": "Progression-Free Survival",
            "definition": "Time from randomization to progression or death",
            "analysis_method": "Kaplan-Meier, Log-rank test, Cox regression",
            "censoring": "Last adequate tumor assessment"
        },
        "DFS": {
            "name": "Disease-Free Survival",
            "definition": "Time from randomization to recurrence or death",
            "applicable_to": "Adjuvant setting"
        },
        "EFS": {
            "name": "Event-Free Survival",
            "definition": "Time from randomization to defined event(s)",
            "events": "Protocol-specific composite"
        },
        "TTP": {
            "name": "Time to Progression",
            "definition": "Time from randomization to progression",
            "note": "Deaths censored; less preferred than PFS"
        },
        "DOR": {
            "name": "Duration of Response",
            "definition": "Time from first response to progression",
            "population": "Responders only"
        },
        "TTR": {
            "name": "Time to Response",
            "definition": "Time from randomization to first response"
        }
    }

    SAFETY_AESI = {
        "immunotherapy": [
            "Immune-related adverse events (irAEs)",
            "Infusion-related reactions",
            "Cytokine release syndrome",
            "Pneumonitis",
            "Colitis",
            "Hepatitis",
            "Endocrinopathies"
        ],
        "chemotherapy": [
            "Febrile neutropenia",
            "Myelosuppression",
            "Nausea/vomiting",
            "Neuropathy",
            "Cardiotoxicity"
        ],
        "targeted_therapy": [
            "QT prolongation",
            "Hypertension",
            "Skin toxicity",
            "Diarrhea"
        ]
    }


class Phase1Standards:
    """Phase 1 trial-specific standards."""

    DOSE_ESCALATION_DESIGNS = {
        "3+3": {
            "name": "Traditional 3+3 Design",
            "description": "Rule-based design enrolling 3-6 patients per dose level",
            "dlt_threshold": "≤1/6 DLTs to escalate",
            "sample_size": "Typically 18-36 patients",
            "mtd_definition": "Highest dose with <33% DLT rate"
        },
        "BOIN": {
            "name": "Bayesian Optimal Interval Design",
            "description": "Model-assisted design using optimal intervals",
            "reference": "Liu & Yuan, Clin Cancer Res 2015"
        },
        "CRM": {
            "name": "Continual Reassessment Method",
            "description": "Model-based Bayesian design",
            "reference": "O'Quigley et al. Biometrics 1990"
        },
        "mTPI": {
            "name": "Modified Toxicity Probability Interval",
            "description": "Model-assisted design"
        }
    }

    DLT_ASSESSMENT = {
        "period": "Typically Cycle 1 (21-35 days)",
        "grading": "NCI-CTCAE",
        "typical_dlt_definition": [
            "Grade 4 hematologic toxicity lasting >7 days",
            "Grade 3-4 non-hematologic toxicity (with exceptions)",
            "Grade 3-4 nausea/vomiting/diarrhea despite supportive care",
            "Any toxicity resulting in >2 week treatment delay",
            "Any treatment-related death"
        ],
        "exceptions": [
            "Alopecia",
            "Grade 3 fatigue lasting <7 days",
            "Grade 3 nausea/vomiting controlled with antiemetics"
        ]
    }


# =============================================================================
# LABORATORY STANDARDS
# =============================================================================

class LaboratoryStandards:
    """Standard laboratory safety assessments."""

    HEMATOLOGY = [
        "Hemoglobin",
        "Hematocrit",
        "Red blood cell count",
        "White blood cell count",
        "Neutrophils (absolute)",
        "Lymphocytes (absolute)",
        "Monocytes (absolute)",
        "Eosinophils (absolute)",
        "Basophils (absolute)",
        "Platelet count"
    ]

    CHEMISTRY = [
        "Sodium",
        "Potassium",
        "Chloride",
        "Bicarbonate",
        "BUN/Urea",
        "Creatinine",
        "Glucose",
        "Calcium",
        "Phosphorus",
        "Magnesium",
        "Total protein",
        "Albumin",
        "Total bilirubin",
        "Direct bilirubin",
        "AST (SGOT)",
        "ALT (SGPT)",
        "Alkaline phosphatase",
        "GGT",
        "LDH",
        "Uric acid"
    ]

    COAGULATION = [
        "PT/INR",
        "aPTT",
        "Fibrinogen"
    ]

    URINALYSIS = [
        "pH",
        "Specific gravity",
        "Protein",
        "Glucose",
        "Blood",
        "Leukocyte esterase"
    ]

    SHIFT_TABLE_CATEGORIES = {
        "CTCAE": ["Grade 0 (Normal)", "Grade 1", "Grade 2", "Grade 3", "Grade 4"],
        "Low_Normal_High": ["Low", "Normal", "High"],
        "Clinical_Significance": ["Not clinically significant", "Clinically significant"]
    }


# =============================================================================
# COMPLETE REGULATORY KNOWLEDGE BASE
# =============================================================================

class RegulatoryKnowledgeBase:
    """
    Complete regulatory knowledge base for SAP generation.

    Usage:
        kb = RegulatoryKnowledgeBase()

        # Get current coding standards
        meddra_version = kb.get_meddra_version()
        ctcae_version = kb.get_ctcae_version()

        # Get TEAE table specifications
        teae_tables = kb.get_teae_tables()

        # Get therapeutic area standards
        oncology = kb.get_oncology_standards()
    """

    def __init__(self):
        self.coding = CodingStandards()
        self.teae = TEAESummaryTypes()
        self.estimands = EstimandFramework()
        self.oncology = OncologyStandards()
        self.phase1 = Phase1Standards()
        self.labs = LaboratoryStandards()

    def get_meddra_version(self) -> str:
        """Get current MedDRA version."""
        return self.coding.MEDDRA["current_version"]

    def get_ctcae_version(self) -> str:
        """Get current CTCAE version."""
        return self.coding.CTCAE["current_version"]

    def get_who_drug_version(self) -> str:
        """Get current WHO Drug Dictionary version."""
        return self.coding.WHO_DRUG["current_version"]

    def get_teae_tables(self, phase: str = None, therapeutic_area: str = None) -> List[Dict]:
        """Get standard TEAE table specifications."""
        tables = self.teae.get_all_tables()

        # Add infusion reactions for IV drugs
        if therapeutic_area == "oncology":
            tables = [t for t in tables]  # Include all for oncology

        return tables

    def get_teae_table_count(self) -> int:
        """Get number of standard TEAE tables."""
        return len(self.teae.get_all_tables())

    def get_oncology_standards(self) -> Dict:
        """Get oncology-specific standards."""
        return {
            "response_criteria": self.oncology.RESPONSE_CRITERIA,
            "survival_endpoints": self.oncology.SURVIVAL_ENDPOINTS,
            "safety_aesi": self.oncology.SAFETY_AESI
        }

    def get_phase1_standards(self) -> Dict:
        """Get Phase 1 specific standards."""
        return {
            "dose_escalation": self.phase1.DOSE_ESCALATION_DESIGNS,
            "dlt_assessment": self.phase1.DLT_ASSESSMENT
        }

    def get_estimand_framework(self) -> Dict:
        """Get ICH E9 R1 estimand framework."""
        return {
            "components": self.estimands.COMPONENTS,
            "standard_estimands": self.estimands.STANDARD_ESTIMANDS
        }

    def get_lab_parameters(self) -> Dict:
        """Get standard laboratory parameters."""
        return {
            "hematology": self.labs.HEMATOLOGY,
            "chemistry": self.labs.CHEMISTRY,
            "coagulation": self.labs.COAGULATION,
            "urinalysis": self.labs.URINALYSIS,
            "shift_categories": self.labs.SHIFT_TABLE_CATEGORIES
        }

    def format_for_prompt(self, phase: str, therapeutic_area: str = "oncology") -> str:
        """Format regulatory standards for inclusion in Claude prompt."""

        lines = ["## REGULATORY STANDARDS (Authoritative Reference)"]
        lines.append("")

        # Coding dictionaries
        lines.append("### Coding Dictionaries")
        lines.append(f"- **MedDRA Version:** {self.get_meddra_version()} (for AE/MH coding)")
        lines.append(f"- **NCI-CTCAE Version:** {self.get_ctcae_version()} (for AE severity grading)")
        lines.append(f"- **WHO Drug Dictionary:** {self.get_who_drug_version()} (for medication coding)")
        lines.append("")

        # CTCAE grades
        lines.append("### CTCAE Severity Grades")
        for grade, desc in self.coding.CTCAE["grades"].items():
            lines.append(f"- Grade {grade}: {desc}")
        lines.append("")

        # TEAE tables
        lines.append(f"### Standard TEAE Summary Tables ({self.get_teae_table_count()} types)")
        for table in self.teae.CORE_TABLES:
            lines.append(f"- **{table['title']}**: {table['description']}")
        for table in self.teae.RELATIONSHIP_TABLES:
            lines.append(f"- **{table['title']}**: {table.get('description', '')}")
        for table in self.teae.SEVERITY_TABLES:
            lines.append(f"- **{table['title']}**: {table.get('description', '')}")
        for table in self.teae.OUTCOME_TABLES:
            lines.append(f"- **{table['title']}**: {table.get('description', '')}")
        lines.append("")

        # Phase-specific
        if "1" in phase.lower():
            lines.append("### Phase 1 Standards")
            lines.append(f"- **DLT Assessment Period:** {self.phase1.DLT_ASSESSMENT['period']}")
            lines.append(f"- **MTD Definition:** {self.phase1.DOSE_ESCALATION_DESIGNS['3+3']['mtd_definition']}")
            lines.append("- **Typical DLT Definitions:**")
            for dlt in self.phase1.DLT_ASSESSMENT["typical_dlt_definition"][:4]:
                lines.append(f"  - {dlt}")
            lines.append("")

        # Therapeutic area specific
        if therapeutic_area == "oncology":
            lines.append("### Oncology-Specific Standards")
            lines.append("- **Response Criteria:** RECIST 1.1, iRECIST, GCIG (ovarian)")
            lines.append("- **Survival Endpoints:** OS, PFS, DFS, EFS, DOR, TTR")
            lines.append("- **AESIs for Immunotherapy:** irAEs, infusion reactions, CRS, pneumonitis")
            lines.append("")

        return "\n".join(lines)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_regulatory_context(phase: str, therapeutic_area: str = "oncology") -> str:
    """
    Get formatted regulatory context for SAP generation.

    Args:
        phase: Trial phase (e.g., "Phase 1", "Phase 1b", "Phase 3")
        therapeutic_area: Therapeutic area (e.g., "oncology", "cardiovascular")

    Returns:
        Formatted string for inclusion in Claude prompt
    """
    kb = RegulatoryKnowledgeBase()
    return kb.format_for_prompt(phase, therapeutic_area)


def get_standard_versions() -> Dict[str, str]:
    """Get current standard versions for coding dictionaries."""
    kb = RegulatoryKnowledgeBase()
    return {
        "MedDRA": kb.get_meddra_version(),
        "CTCAE": kb.get_ctcae_version(),
        "WHO_Drug": kb.get_who_drug_version()
    }


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    kb = RegulatoryKnowledgeBase()

    print("=" * 60)
    print("REGULATORY KNOWLEDGE BASE")
    print("=" * 60)

    print(f"\n📋 Coding Standards:")
    print(f"   • MedDRA: {kb.get_meddra_version()}")
    print(f"   • CTCAE: {kb.get_ctcae_version()}")
    print(f"   • WHO Drug: {kb.get_who_drug_version()}")

    print(f"\n📋 TEAE Table Types: {kb.get_teae_table_count()}")
    for table in kb.get_teae_tables()[:5]:
        print(f"   • {table['title']}")
    print("   ... and more")

    print(f"\n📋 Phase 1 Standards:")
    p1 = kb.get_phase1_standards()
    print(f"   • Designs: {list(p1['dose_escalation'].keys())}")

    print(f"\n📋 Oncology Standards:")
    onc = kb.get_oncology_standards()
    print(f"   • Response criteria: {list(onc['response_criteria'].keys())}")
    print(f"   • Survival endpoints: {list(onc['survival_endpoints'].keys())}")

    print("\n" + "=" * 60)
    print("FORMATTED FOR PROMPT (Phase 1b Oncology)")
    print("=" * 60)
    print(kb.format_for_prompt("Phase 1b", "oncology"))
