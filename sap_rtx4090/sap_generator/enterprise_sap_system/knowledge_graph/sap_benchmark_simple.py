"""
SAP Benchmark - Matches Standard SAP Structure
==============================================
LLM-based validation against reference SAP.
Checks both presence and accuracy vs reference.

Scoring:
- 50% element present in generated
- 50% value matches reference SAP
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import anthropic


# =============================================================================
# SAP STRUCTURE - CRITICAL ELEMENTS BY SECTION
# =============================================================================

CRITICAL_ELEMENTS = {
    # =========================================================================
    # SECTION 1: TITLE PAGE
    # =========================================================================
    "1_title_page": [
        {
            "name": "1.0 Study Title",
            "presence_question": "Does the text include the study title?",
            "extract_prompt": "What is the study title? Return the title. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "1.0 Protocol Number",
            "presence_question": "Does the text include a protocol number or study ID?",
            "extract_prompt": "What is the protocol number? Return the number. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "1.0 Sponsor Name",
            "presence_question": "Does the text include the sponsor name?",
            "extract_prompt": "Who is the sponsor? Return the name. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "1.0 Document Version",
            "presence_question": "Does the text include a document version number?",
            "extract_prompt": "What is the document version? Return version. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "1.0 Document Date",
            "presence_question": "Does the text include a document date?",
            "extract_prompt": "What is the document date? Return date. If not found, return 'NOT FOUND'.",
            "required": True
        }
    ],

    # =========================================================================
    # SECTION 2: OBJECTIVES, ENDPOINTS, AND ESTIMANDS
    # =========================================================================
    "2_objectives_endpoints_estimands": [
        {
            "name": "2.1 Primary Objective",
            "presence_question": "Does the text state the primary objective of the study?",
            "extract_prompt": "What is the primary objective? Return in one sentence. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "2.1.1 Primary Endpoint(s)",
            "presence_question": "Does the text specify the primary endpoint(s) (e.g., PFS, OS, ORR, pCR)?",
            "extract_prompt": "What is the primary endpoint? Return ONLY the endpoint name(s). If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "2.1.1 Primary Endpoint Definition",
            "presence_question": "Does the text define how the primary endpoint is measured?",
            "extract_prompt": "What is the definition of the primary endpoint? Return the definition. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "2.1.1 Assessment Criteria",
            "presence_question": "Does the text specify assessment criteria (e.g., RECIST, Lugano, BICR)?",
            "extract_prompt": "What assessment criteria is used? Return the criteria (e.g., 'RECIST 1.1 by BICR'). If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "2.2 Secondary Objectives",
            "presence_question": "Does the text state secondary objectives?",
            "extract_prompt": "What are the secondary objectives? Return as list. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "2.2.1 Secondary Endpoints",
            "presence_question": "Does the text list secondary endpoints?",
            "extract_prompt": "What are the secondary endpoints? Return as comma-separated list. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "2.3 Exploratory Objectives",
            "presence_question": "Does the text mention exploratory objectives?",
            "extract_prompt": "What are the exploratory objectives? Return as list. If not found, return 'NOT FOUND'.",
            "required": False
        },
        {
            "name": "2.3.1 Exploratory Endpoints",
            "presence_question": "Does the text list exploratory endpoints?",
            "extract_prompt": "What are the exploratory endpoints? Return as comma-separated list. If not found, return 'NOT FOUND'.",
            "required": False
        }
    ],

    # =========================================================================
    # SECTION 3: STUDY DESIGN
    # =========================================================================
    "3_study_design": [
        {
            "name": "3.3 Analysis Populations",
            "presence_question": "Does the text define analysis populations (e.g., ITT, Safety, Per-Protocol, FAS)?",
            "extract_prompt": "What analysis populations are defined? Return as comma-separated list. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "3.3 ITT/FAS Definition",
            "presence_question": "Does the text define who is included in ITT or FAS population?",
            "extract_prompt": "How is ITT/FAS defined? Return the definition. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "3.3 Safety Population Definition",
            "presence_question": "Does the text define the safety population?",
            "extract_prompt": "How is safety population defined? Return the definition. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "3.3 Per-Protocol Definition",
            "presence_question": "Does the text define the per-protocol population?",
            "extract_prompt": "How is per-protocol population defined? Return the definition. If not found, return 'NOT FOUND'.",
            "required": False
        },
        {
            "name": "3.4 Timing of Analysis",
            "presence_question": "Does the text specify when the primary analysis will occur?",
            "extract_prompt": "When will the primary analysis occur? Return timing (e.g., 'after 300 events'). If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "3.4 Interim Analyses",
            "presence_question": "Does the text mention interim analyses?",
            "extract_prompt": "Are interim analyses planned? Return details. If not found, return 'NOT FOUND'.",
            "required": False
        },
        {
            "name": "3.7 Null Hypothesis",
            "presence_question": "Does the text state the null hypothesis (H0)?",
            "extract_prompt": "What is the null hypothesis? Return H0. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "3.7 Alpha Level",
            "presence_question": "Does the text specify the significance level (alpha)?",
            "extract_prompt": "What is the alpha level? Return value (e.g., '0.025 one-sided'). If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "3.7 Test Sidedness",
            "presence_question": "Does the text specify if the test is one-sided or two-sided?",
            "extract_prompt": "Is the test one-sided or two-sided? Return answer. If not found, return 'NOT FOUND'.",
            "required": True
        }
    ],

    # =========================================================================
    # SECTION 4: STATISTICAL ANALYSES
    # =========================================================================
    "4_statistical_analyses": [
        {
            "name": "4.1 General Methodology",
            "presence_question": "Does the text describe the general statistical methodology?",
            "extract_prompt": "What is the general statistical methodology? Return brief summary. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "4.1 Software",
            "presence_question": "Does the text specify statistical software (e.g., SAS)?",
            "extract_prompt": "What statistical software is used? Return name and version. If not found, return 'NOT FOUND'.",
            "required": False
        },
        {
            "name": "4.2 Key Definitions - Baseline",
            "presence_question": "Does the text define baseline?",
            "extract_prompt": "How is baseline defined? Return the definition. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "4.2 Key Definitions - Study Day",
            "presence_question": "Does the text define study day calculation?",
            "extract_prompt": "How is study day calculated? Return the definition. If not found, return 'NOT FOUND'.",
            "required": False
        },
        {
            "name": "4.3 Multiplicity Adjustment",
            "presence_question": "Does the text address multiplicity adjustment?",
            "extract_prompt": "What multiplicity adjustment is used? Return method (e.g., 'Hochberg', 'gatekeeping'). If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "4.4 Covariates",
            "presence_question": "Does the text specify covariates for analysis?",
            "extract_prompt": "What covariates are used? Return as list. If not found, return 'NOT FOUND'.",
            "required": False
        },
        {
            "name": "4.4 Subgroups",
            "presence_question": "Does the text list subgroups for analysis?",
            "extract_prompt": "What subgroups will be analyzed? Return as list. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "4.5 Visit Windows",
            "presence_question": "Does the text define visit windows?",
            "extract_prompt": "How are visit windows defined? Return summary. If not found, return 'NOT FOUND'.",
            "required": False
        },
        {
            "name": "4.6 Intercurrent Events (ICE)",
            "presence_question": "Does the text describe handling of intercurrent events?",
            "extract_prompt": "How are intercurrent events handled? Return strategy. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "4.6 ICE Strategy",
            "presence_question": "Does the text specify ICE strategy (treatment policy, composite, hypothetical)?",
            "extract_prompt": "What ICE strategy is used? Return strategy name. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "4.7 Missing Data Handling",
            "presence_question": "Does the text describe handling of missing data?",
            "extract_prompt": "How is missing data handled? Return method. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "4.8 Duplicate/Unscheduled Data",
            "presence_question": "Does the text describe handling of duplicate or unscheduled data?",
            "extract_prompt": "How is duplicate/unscheduled data handled? Return method. If not found, return 'NOT FOUND'.",
            "required": False
        }
    ],

    # =========================================================================
    # SECTION 6: EFFICACY
    # =========================================================================
    "6_efficacy": [
        {
            "name": "6.1.1 Primary Analysis Method",
            "presence_question": "Does the text specify the statistical method for primary analysis (e.g., log-rank, Cox)?",
            "extract_prompt": "What statistical method is used for primary analysis? Return method. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "6.1.1 Stratification Factors",
            "presence_question": "Does the text mention stratification factors for the primary analysis?",
            "extract_prompt": "What are the stratification factors? Return as list. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "6.1.1 Hazard Ratio / Effect Estimate",
            "presence_question": "Does the text describe how the treatment effect (e.g., HR, OR, RR) will be estimated?",
            "extract_prompt": "How is the treatment effect estimated? Return method. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "6.1.1 Confidence Interval",
            "presence_question": "Does the text specify confidence interval method?",
            "extract_prompt": "What CI method is used? Return method (e.g., '95% CI'). If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "6.1.1 Kaplan-Meier",
            "presence_question": "Does the text mention Kaplan-Meier estimation or survival curves?",
            "extract_prompt": "Is Kaplan-Meier used? Return 'YES' or 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "6.1.1.2 Censoring Rules",
            "presence_question": "Does the text describe censoring rules for time-to-event analysis?",
            "extract_prompt": "What are the censoring rules? Return summary. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "6.1.1.4 Secondary Analyses of Primary Endpoint",
            "presence_question": "Does the text describe secondary analyses of the primary endpoint?",
            "extract_prompt": "What secondary analyses are planned for primary endpoint? Return list. If not found, return 'NOT FOUND'.",
            "required": False
        },
        {
            "name": "6.1.1.5 Sensitivity Analyses",
            "presence_question": "Does the text describe sensitivity analyses?",
            "extract_prompt": "What sensitivity analyses are planned? Return as list. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "6.1.1.6 Subgroup Analyses",
            "presence_question": "Does the text describe subgroup analyses?",
            "extract_prompt": "What subgroup analyses are planned? Return as list. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "6.1.1.6 Forest Plot",
            "presence_question": "Does the text mention forest plots for subgroup analyses?",
            "extract_prompt": "Are forest plots planned? Return 'YES' or 'NOT FOUND'.",
            "required": False
        }
    ],

    # =========================================================================
    # SECTION 7: SAFETY ANALYSES
    # =========================================================================
    "7_safety": [
        {
            "name": "7.1 Safety Population",
            "presence_question": "Does the text define the safety analysis population?",
            "extract_prompt": "How is safety population defined? Return definition. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "7.1 TEAE Definition",
            "presence_question": "Does the text define treatment-emergent adverse events (TEAEs)?",
            "extract_prompt": "How are TEAEs defined? Return definition. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "7.1 AE Coding - MedDRA",
            "presence_question": "Does the text specify MedDRA version for AE coding?",
            "extract_prompt": "What MedDRA version is used? Return version. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "7.1 AE Grading - CTCAE",
            "presence_question": "Does the text specify CTCAE version for AE grading?",
            "extract_prompt": "What CTCAE version is used? Return version. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "7.1 AE Summary by SOC",
            "presence_question": "Does the text describe AE summaries by System Organ Class (SOC)?",
            "extract_prompt": "Are AEs summarized by SOC? Return 'YES' or 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "7.1 AE Summary by Preferred Term",
            "presence_question": "Does the text describe AE summaries by Preferred Term (PT)?",
            "extract_prompt": "Are AEs summarized by PT? Return 'YES' or 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "7.1 Grade ≥3 AEs",
            "presence_question": "Does the text describe reporting of Grade 3 or higher AEs?",
            "extract_prompt": "Are Grade ≥3 AEs reported separately? Return 'YES' or 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "7.1 Serious AEs",
            "presence_question": "Does the text describe reporting of serious adverse events (SAEs)?",
            "extract_prompt": "Are SAEs reported separately? Return 'YES' or 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "7.1 AEs Leading to Discontinuation",
            "presence_question": "Does the text describe reporting of AEs leading to treatment discontinuation?",
            "extract_prompt": "Are AEs leading to discontinuation reported? Return 'YES' or 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "7.1.3 Laboratory Panels",
            "presence_question": "Does the text describe which laboratory panels will be analyzed?",
            "extract_prompt": "What laboratory panels are analyzed? Return list. If not found, return 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "7.1.3 Lab Shift Tables",
            "presence_question": "Does the text mention shift tables for laboratory data?",
            "extract_prompt": "Are lab shift tables planned? Return 'YES' or 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "7.1.3 Lab Markedly Abnormal",
            "presence_question": "Does the text define markedly abnormal laboratory values?",
            "extract_prompt": "How are markedly abnormal labs defined? Return criteria. If not found, return 'NOT FOUND'.",
            "required": False
        }
    ],

    # =========================================================================
    # SECTION 11: APPENDICES
    # =========================================================================
    "11_appendices": [
        {
            "name": "11.1 Schedule of Assessments",
            "presence_question": "Does the text include or reference a Schedule of Assessments (SOA)?",
            "extract_prompt": "Is Schedule of Assessments included? Return 'YES' or 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "11.2 Lab Normal Ranges",
            "presence_question": "Does the text include or reference laboratory normal ranges?",
            "extract_prompt": "Are lab normal ranges included? Return 'YES' or 'NOT FOUND'.",
            "required": False
        },
        {
            "name": "11.3 Questionnaire Samples",
            "presence_question": "Does the text include questionnaire samples or PRO instruments?",
            "extract_prompt": "Are questionnaire samples included? Return 'YES' or 'NOT FOUND'.",
            "required": False
        },
        {
            "name": "11.3 Questionnaire Scoring Methods",
            "presence_question": "Does the text describe questionnaire scoring methods?",
            "extract_prompt": "Are scoring methods described? Return 'YES' or 'NOT FOUND'.",
            "required": False
        },
        {
            "name": "11.5 Index of Tables",
            "presence_question": "Does the text include an index or list of tables?",
            "extract_prompt": "Is there a table index? Return 'YES' or 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "11.5 Index of Listings",
            "presence_question": "Does the text include an index or list of listings?",
            "extract_prompt": "Is there a listings index? Return 'YES' or 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "11.5 Index of Figures",
            "presence_question": "Does the text include an index or list of figures?",
            "extract_prompt": "Is there a figures index? Return 'YES' or 'NOT FOUND'.",
            "required": True
        },
        {
            "name": "11.5 Table Shells",
            "presence_question": "Does the text include table shells or mock tables?",
            "extract_prompt": "Are table shells included? Return 'YES' or 'NOT FOUND'.",
            "required": True
        }
    ]
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ElementResult:
    """Result for a single element check."""
    name: str
    present: bool
    generated_value: str
    reference_value: str
    matches: bool
    required: bool
    score: float  # 0-1


@dataclass
class SectionResult:
    """Result for a section evaluation."""
    section_id: str
    section_name: str
    elements_present: int
    elements_total: int
    elements_matching: int
    required_present: int
    required_total: int
    element_results: List[ElementResult]
    score: float  # 0-10


@dataclass
class BenchmarkResult:
    """Overall benchmark result."""
    trial_id: str
    timestamp: str
    section_results: Dict[str, SectionResult]
    overall_score: float
    critical_pass: bool
    summary: str


# =============================================================================
# BENCHMARK CLASS
# =============================================================================

class SimpleBenchmark:
    """
    SAP benchmark using LLM evaluation.
    Checks presence AND accuracy vs reference.
    """

    def __init__(self):
        self.elements = CRITICAL_ELEMENTS
        self.client = anthropic.Anthropic()

    def _llm_check_presence(self, content: str, question: str) -> bool:
        """Check if element is present using LLM."""
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=10,
                messages=[{
                    "role": "user",
                    "content": f"""Answer YES or NO only.

{question}

TEXT:
{content[:6000]}

Answer:"""
                }]
            )
            answer = response.content[0].text.strip().upper()
            return answer.startswith("YES")
        except Exception as e:
            print(f"      Presence check error: {e}")
            return False

    def _llm_extract_value(self, content: str, prompt: str) -> str:
        """Extract specific value from content using LLM."""
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                messages=[{
                    "role": "user",
                    "content": f"""Extract the requested information. Be concise.

{prompt}

TEXT:
{content[:6000]}

Answer:"""
                }]
            )
            return response.content[0].text.strip()
        except Exception as e:
            print(f"      Extract error: {e}")
            return "NOT FOUND"

    def _llm_compare_values(self, generated_value: str, reference_value: str, element_name: str) -> bool:
        """Compare if generated value matches reference using LLM."""
        if "NOT FOUND" in generated_value or "NOT FOUND" in reference_value:
            return False

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=10,
                messages=[{
                    "role": "user",
                    "content": f"""Do these two values for "{element_name}" mean the same thing? Answer YES or NO only.

GENERATED: {generated_value}

REFERENCE: {reference_value}

Answer:"""
                }]
            )
            answer = response.content[0].text.strip().upper()
            return answer.startswith("YES")
        except Exception as e:
            print(f"      Compare error: {e}")
            return False

    def check_element(
        self,
        element: Dict,
        generated_content: str,
        reference_content: str
    ) -> ElementResult:
        """Check single element for presence and accuracy."""

        name = element["name"]
        required = element.get("required", True)

        # Step 1: Check presence in generated
        present = self._llm_check_presence(generated_content, element["presence_question"])

        # Step 2: Extract values from both
        generated_value = "NOT FOUND"
        reference_value = "NOT FOUND"
        matches = False

        if present:
            generated_value = self._llm_extract_value(generated_content, element["extract_prompt"])

        if reference_content:
            reference_value = self._llm_extract_value(reference_content, element["extract_prompt"])

        # Step 3: Compare values
        if present and "NOT FOUND" not in generated_value and "NOT FOUND" not in reference_value:
            matches = self._llm_compare_values(generated_value, reference_value, name)

        # Calculate score: 50% presence + 50% match
        if reference_content:
            score = (0.5 if present else 0) + (0.5 if matches else 0)
        else:
            # No reference - only check presence
            score = 1.0 if present else 0.0

        return ElementResult(
            name=name,
            present=present,
            generated_value=generated_value,
            reference_value=reference_value,
            matches=matches,
            required=required,
            score=score
        )

    def evaluate_section(
        self,
        section_id: str,
        generated_content: str,
        reference_content: str = ""
    ) -> SectionResult:
        """Evaluate a single section."""

        if section_id not in self.elements:
            return SectionResult(
                section_id=section_id,
                section_name=section_id,
                elements_present=0,
                elements_total=0,
                elements_matching=0,
                required_present=0,
                required_total=0,
                element_results=[],
                score=5.0
            )

        section_elements = self.elements[section_id]
        results = []

        print(f"    Checking {len(section_elements)} elements...")

        for elem in section_elements:
            print(f"      - {elem['name']}...", end=" ", flush=True)
            result = self.check_element(elem, generated_content, reference_content)
            results.append(result)

            status = "✓" if result.present else "✗"
            match_status = f" (match: {'✓' if result.matches else '✗'})" if reference_content else ""
            print(f"{status}{match_status}")

        # Calculate counts
        total = len(results)
        present = sum(1 for r in results if r.present)
        matching = sum(1 for r in results if r.matches)
        required = [r for r in results if r.required]
        required_present = sum(1 for r in required if r.present)
        required_total = len(required)

        # Calculate score (average of element scores, scaled to 10)
        avg_score = sum(r.score for r in results) / total if total > 0 else 0
        section_score = round(avg_score * 10, 1)

        # Section names
        section_names = {
            "1_title_page": "1. Title Page",
            "2_objectives_endpoints_estimands": "2. Objectives, Endpoints & Estimands",
            "3_study_design": "3. Study Design",
            "4_statistical_analyses": "4. Statistical Analyses",
            "6_efficacy": "6. Efficacy",
            "7_safety": "7. Safety",
            "11_appendices": "11. Appendices"
        }

        return SectionResult(
            section_id=section_id,
            section_name=section_names.get(section_id, section_id),
            elements_present=present,
            elements_total=total,
            elements_matching=matching,
            required_present=required_present,
            required_total=required_total,
            element_results=results,
            score=section_score
        )

    def evaluate_full_sap(
        self,
        generated_sections: Dict[str, str],
        reference_sections: Dict[str, str] = None,
        trial_id: str = "Unknown"
    ) -> BenchmarkResult:
        """Evaluate full SAP."""

        reference_sections = reference_sections or {}
        section_results = {}

        print(f"\n  Evaluating {len(self.elements)} sections...")

        for section_id in self.elements.keys():
            gen_content = generated_sections.get(section_id, "")
            ref_content = reference_sections.get(section_id, "")

            if gen_content:
                print(f"\n  [{section_id}]")
                result = self.evaluate_section(section_id, gen_content, ref_content)
                section_results[section_id] = result
                print(f"    Score: {result.score}/10 ({result.elements_present}/{result.elements_total} present, {result.elements_matching} match)")

        # Calculate overall score (weighted average)
        weights = {
            "1_title_page": 0.05,
            "2_objectives_endpoints_estimands": 0.18,
            "3_study_design": 0.14,
            "4_statistical_analyses": 0.18,
            "6_efficacy": 0.23,
            "7_safety": 0.14,
            "11_appendices": 0.08
        }

        total_weight = 0
        weighted_score = 0

        for section_id, result in section_results.items():
            weight = weights.get(section_id, 0.1)
            weighted_score += result.score * weight
            total_weight += weight

        overall_score = round(weighted_score / total_weight, 1) if total_weight > 0 else 0

        # Critical pass = all required elements present
        critical_pass = all(
            r.required_present == r.required_total
            for r in section_results.values()
        )

        # Summary
        missing = []
        mismatched = []
        for section_id, result in section_results.items():
            for elem in result.element_results:
                if elem.required and not elem.present:
                    missing.append(f"{elem.name}")
                elif elem.present and not elem.matches and reference_sections:
                    mismatched.append(f"{elem.name}")

        summary_parts = []
        if missing:
            summary_parts.append(f"Missing: {', '.join(missing[:3])}")
            if len(missing) > 3:
                summary_parts.append(f"(+{len(missing)-3} more)")
        if mismatched:
            summary_parts.append(f"Mismatched: {', '.join(mismatched[:3])}")
            if len(mismatched) > 3:
                summary_parts.append(f"(+{len(mismatched)-3} more)")
        if not summary_parts:
            summary_parts.append("All elements present and matching")

        return BenchmarkResult(
            trial_id=trial_id,
            timestamp=datetime.now().isoformat(),
            section_results=section_results,
            overall_score=overall_score,
            critical_pass=critical_pass,
            summary=" | ".join(summary_parts)
        )

    def generate_report(self, result: BenchmarkResult) -> str:
        """Generate readable report."""

        lines = [
            "=" * 70,
            "SAP BENCHMARK REPORT",
            "=" * 70,
            f"Trial: {result.trial_id}",
            f"Date: {result.timestamp}",
            f"Overall Score: {result.overall_score}/10",
            f"Critical Pass: {'✓ YES' if result.critical_pass else '✗ NO'}",
            "",
            "-" * 70,
            "SECTION SCORES",
            "-" * 70,
        ]

        for section_id, sr in result.section_results.items():
            lines.append(f"\n{sr.section_name} ({sr.score}/10)")
            lines.append(f"  Present: {sr.elements_present}/{sr.elements_total}")
            lines.append(f"  Matching: {sr.elements_matching}/{sr.elements_total}")
            lines.append(f"  Required: {sr.required_present}/{sr.required_total}")

            # Show element details
            for elem in sr.element_results:
                present_icon = "✓" if elem.present else "✗"
                match_icon = "=" if elem.matches else "≠" if elem.present else " "
                req = "[REQ]" if elem.required else "[OPT]"
                lines.append(f"    {present_icon} {match_icon} {elem.name} {req} (score: {elem.score:.1f})")

                if elem.present and elem.generated_value and "NOT FOUND" not in elem.generated_value:
                    gen_display = elem.generated_value[:50] + "..." if len(elem.generated_value) > 50 else elem.generated_value
                    lines.append(f"         Generated: {gen_display}")
                if elem.reference_value and "NOT FOUND" not in elem.reference_value:
                    ref_display = elem.reference_value[:50] + "..." if len(elem.reference_value) > 50 else elem.reference_value
                    lines.append(f"         Reference: {ref_display}")

        lines.extend([
            "",
            "-" * 70,
            "SUMMARY",
            "-" * 70,
            result.summary,
            "=" * 70
        ])

        return "\n".join(lines)


# =============================================================================
# SECTION MAPPING (Workbench sections to benchmark sections)
# =============================================================================

WORKBENCH_TO_BENCHMARK = {
    "1": "1_title_page",                      # Title Page
    "2": "2_objectives_endpoints_estimands",  # Introduction/Objectives
    "6": "2_objectives_endpoints_estimands",  # Endpoints/Estimands
    "3": "3_study_design",                    # Study Design
    "5": "3_study_design",                    # Analysis Populations
    "7": "6_efficacy",                        # Statistical Methods -> Efficacy
    "8": "6_efficacy",                        # Censoring Rules -> Efficacy
    "9": "4_statistical_analyses",            # Missing Data
    "10": "4_statistical_analyses",           # Sensitivity Analyses
    "11": "4_statistical_analyses",           # Subgroup Analyses
    "12": "7_safety",                         # Safety Analysis
    "18": "11_appendices",                    # TFL Shells
    "14": "11_appendices"                     # Table Shells
}


def map_workbench_sections(workbench_sections: Dict[str, str]) -> Dict[str, str]:
    """Map workbench section IDs to benchmark section IDs."""
    benchmark_sections = {}

    for wb_id, content in workbench_sections.items():
        bench_id = WORKBENCH_TO_BENCHMARK.get(wb_id)
        if bench_id:
            if bench_id in benchmark_sections:
                benchmark_sections[bench_id] += "\n\n" + content
            else:
                benchmark_sections[bench_id] = content

    return benchmark_sections


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # Count elements
    total = sum(len(elems) for elems in CRITICAL_ELEMENTS.values())
    required = sum(1 for elems in CRITICAL_ELEMENTS.values() for e in elems if e.get("required", True))
    print(f"SAP Benchmark: {total} elements ({required} required)")
    for section_id, elems in CRITICAL_ELEMENTS.items():
        req = sum(1 for e in elems if e.get("required", True))
        print(f"  {section_id}: {len(elems)} elements ({req} required)")
