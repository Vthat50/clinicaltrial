"""
Protocol-Specific Variable Extractor
=====================================

Extracts ACTUAL protocol variables instead of using generic templates.

This fixes the core issue: generic templates don't match specific protocols.

Key extractions:
1. Study type (adjuvant vs metastatic vs treatment)
2. Actual baseline variables from protocol/CRF
3. Actual endpoints with proper statistical methods
4. Protocol-specific populations
5. Country/region-specific requirements

Author: SAP Generation System
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum


class StudyType(Enum):
    """Clinical trial study types - determines table structure."""
    ADJUVANT = "adjuvant"  # Post-surgery prevention (DFS, TTR) - NO tumor response
    NEOADJUVANT = "neoadjuvant"  # Pre-surgery (pCR, tumor shrinkage)
    METASTATIC = "metastatic"  # Treatment of existing tumors (ORR, CR/PR/SD/PD)
    MAINTENANCE = "maintenance"  # After initial treatment
    FIRST_LINE = "first_line"  # First treatment for advanced disease
    DOSE_FINDING = "dose_finding"  # Phase 1 (DLT, MTD, RP2D)
    PREVENTION = "prevention"  # Primary prevention
    SUPPORTIVE = "supportive"  # Supportive care


class EndpointType(Enum):
    """Endpoint analysis types - determines statistical method."""
    TIME_TO_EVENT = "time_to_event"  # Cox model, HR, KM curves
    BINARY = "binary"  # Logistic, OR or RR
    CONTINUOUS = "continuous"  # t-test, ANCOVA
    COUNT = "count"  # Poisson, negative binomial
    ORDINAL = "ordinal"  # Proportional odds
    RECURRENT = "recurrent"  # Andersen-Gill, LWYY


class StatisticalMethod(Enum):
    """Statistical methods matched to endpoint types."""
    COX_REGRESSION = "cox_regression"  # HR
    LOGISTIC_REGRESSION = "logistic_regression"  # OR
    LOG_BINOMIAL = "log_binomial"  # RR
    KAPLAN_MEIER = "kaplan_meier"  # Survival curves
    AALEN_JOHANSEN = "aalen_johansen"  # Competing risks
    ANCOVA = "ancova"  # Continuous with baseline
    MIXED_MODEL = "mixed_model"  # Repeated measures
    POISSON = "poisson"  # Count data


@dataclass
class ProtocolVariable:
    """A variable extracted from the protocol."""
    name: str
    label: str
    type: str  # "categorical", "continuous", "date", "text"
    categories: List[str] = field(default_factory=list)
    unit: Optional[str] = None
    source: str = ""  # Where found in protocol
    is_baseline: bool = False
    is_stratification: bool = False
    summary_statistic: str = ""  # "n (%)", "median (IQR)", "mean (SD)"


@dataclass
class ProtocolEndpoint:
    """An endpoint extracted from the protocol."""
    name: str
    type: EndpointType
    definition: str
    primary: bool = False
    method: StatisticalMethod = StatisticalMethod.COX_REGRESSION
    measure: str = ""  # "HR", "OR", "RR", "difference"
    source: str = ""


@dataclass
class ProtocolPopulation:
    """A population definition from the protocol."""
    name: str
    abbreviation: str
    definition: str
    source: str = ""


@dataclass
class ProtocolExtraction:
    """Complete extraction from a protocol."""
    study_id: str
    study_type: StudyType
    therapeutic_area: str
    countries: List[str]

    # Extracted content
    baseline_variables: List[ProtocolVariable]
    endpoints: List[ProtocolEndpoint]
    populations: List[ProtocolPopulation]
    stratification_factors: List[str]

    # What NOT to include (study-specific exclusions)
    excluded_variables: List[str] = field(default_factory=list)
    excluded_tables: List[str] = field(default_factory=list)

    # Protocol-specific notes
    notes: List[str] = field(default_factory=list)


class ProtocolSpecificExtractor:
    """
    Extracts protocol-specific variables and structures.

    Key principle: Read the protocol, don't assume generic templates.
    """

    # Patterns to detect study type
    STUDY_TYPE_PATTERNS = {
        StudyType.ADJUVANT: [
            r"adjuvant\s+(?:treatment|therapy|setting)",
            r"post[\-\s]?(?:operative|surgical|resection)",
            r"after\s+(?:complete\s+)?(?:surgical\s+)?resection",
            r"curative\s+(?:surgery|resection|intent)",
            r"disease[\-\s]?free\s+survival",
            r"prevent(?:ion)?\s+of\s+recurrence",
            r"recurrence[\-\s]?free",
        ],
        StudyType.NEOADJUVANT: [
            r"neoadjuvant",
            r"pre[\-\s]?operative",
            r"before\s+surgery",
            r"pathological\s+(?:complete\s+)?response",
            r"tumor\s+(?:shrinkage|downstaging)",
        ],
        StudyType.METASTATIC: [
            r"metastatic",
            r"advanced\s+(?:or\s+metastatic)?",
            r"unresectable",
            r"stage\s+IV",
            r"(?:best\s+)?(?:overall\s+)?response",
            r"objective\s+response\s+rate",
            r"RECIST",
        ],
        StudyType.DOSE_FINDING: [
            r"phase\s+(?:1|I)\b",
            r"dose[\-\s]?(?:finding|escalation|ranging)",
            r"maximum\s+tolerated\s+dose",
            r"MTD",
            r"recommended\s+phase\s+(?:2|II)\s+dose",
            r"RP2D",
            r"DLT",
            r"dose[\-\s]?limiting\s+toxicit",
        ],
    }

    # Variables to EXCLUDE based on study type/region
    EXCLUSION_RULES = {
        "nordic_trial": {
            "exclude_variables": ["RACE", "ETHNICITY"],
            "reason": "Race/ethnicity typically not collected in Nordic trials"
        },
        "adjuvant_study": {
            "exclude_tables": ["tumor_response", "best_overall_response", "waterfall_plot"],
            "reason": "No measurable disease in adjuvant setting"
        },
        "non_performance_status": {
            "exclude_variables": ["ECOG"],
            "replacement": "ASA_SCORE",
            "reason": "Study uses ASA Score instead of ECOG"
        }
    }

    # Common Nordic trial variables
    NORDIC_BASELINE_VARIABLES = [
        ProtocolVariable("COUNTRY", "Country", "categorical",
                        ["Sweden", "Norway", "Denmark", "Finland", "Iceland"],
                        is_baseline=True, summary_statistic="n (%)"),
        ProtocolVariable("ASA_SCORE", "ASA Physical Status Score", "categorical",
                        ["1", "2", "3", "4", "5"],
                        is_baseline=True, summary_statistic="n (%)"),
        ProtocolVariable("BMI", "Body Mass Index", "continuous",
                        unit="kg/m²", is_baseline=True,
                        summary_statistic="median (IQR, min-max)"),
    ]

    # Colorectal cancer specific variables
    CRC_BASELINE_VARIABLES = [
        ProtocolVariable("TUMOR_LOCATION", "Tumor Location", "categorical",
                        ["Colon", "Rectum", "Rectosigmoid"],
                        is_baseline=True, is_stratification=True),
        ProtocolVariable("TUMOR_SUBSITE", "Tumor Subsite", "categorical",
                        ["Cecum", "Ascending colon", "Hepatic flexure",
                         "Transverse colon", "Splenic flexure", "Descending colon",
                         "Sigmoid colon", "Rectum"],
                        is_baseline=True),
        ProtocolVariable("PTNM_STAGE", "pTNM Stage", "categorical",
                        ["Stage I", "Stage II", "Stage III"],
                        is_baseline=True, is_stratification=True),
        ProtocolVariable("MSI_STATUS", "MSI Status", "categorical",
                        ["MSI-high", "MSI-low/MSS", "Uncertain"],
                        is_baseline=True),
        ProtocolVariable("BRAF_STATUS", "BRAF Mutation Status", "categorical",
                        ["BRAF mutant", "BRAF wild-type", "Uncertain"],
                        is_baseline=True),
        ProtocolVariable("KRAS_STATUS", "KRAS Mutation Status", "categorical",
                        ["KRAS mutant", "KRAS wild-type", "Uncertain"],
                        is_baseline=True),
        ProtocolVariable("NRAS_STATUS", "NRAS Mutation Status", "categorical",
                        ["NRAS mutant", "NRAS wild-type", "Uncertain"],
                        is_baseline=True),
        ProtocolVariable("PIK3CA_MUTATION", "PIK3CA Mutation Type", "categorical",
                        ["Exon 9/20", "Other exon", "Wild-type"],
                        is_baseline=True),
        ProtocolVariable("DIFFERENTIATION", "Tumor Differentiation", "categorical",
                        ["Well differentiated", "Moderately differentiated",
                         "Poorly differentiated", "Undifferentiated"],
                        is_baseline=True),
        ProtocolVariable("SURGERY_TYPE", "Type of Surgery", "categorical",
                        ["Elective", "Emergency"],
                        is_baseline=True),
        ProtocolVariable("ADJUVANT_CHEMO", "Adjuvant Chemotherapy", "categorical",
                        ["Yes", "No"],
                        is_baseline=True),
        ProtocolVariable("NEOADJUVANT_THERAPY", "Neoadjuvant Therapy", "categorical",
                        ["None", "Radiotherapy only", "Chemoradiotherapy", "Chemotherapy only"],
                        is_baseline=True),
        ProtocolVariable("CEA", "CEA at Baseline", "continuous",
                        unit="µg/L", is_baseline=True,
                        summary_statistic="median (IQR, min-max)"),
        ProtocolVariable("PLATELET_COUNT", "Platelet Count at Baseline", "continuous",
                        unit="×10⁹/L", is_baseline=True,
                        summary_statistic="median (IQR, min-max)"),
    ]

    def __init__(self):
        """Initialize the extractor."""
        pass

    def detect_study_type(self, protocol_text: str) -> StudyType:
        """Detect the study type from protocol text."""
        text_lower = protocol_text.lower()

        scores = {st: 0 for st in StudyType}

        for study_type, patterns in self.STUDY_TYPE_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, text_lower)
                scores[study_type] += len(matches) * 2

        # Return highest scoring type
        best_type = max(scores, key=scores.get)
        if scores[best_type] > 0:
            return best_type

        # Default to metastatic if unclear
        return StudyType.METASTATIC

    def detect_countries(self, protocol_text: str) -> List[str]:
        """Detect countries/regions from protocol."""
        countries = []

        nordic = ["sweden", "norway", "denmark", "finland", "iceland"]
        for country in nordic:
            if country in protocol_text.lower():
                countries.append(country.title())

        # Check for explicit country mentions
        country_patterns = [
            r"conducted\s+in\s+([A-Z][a-z]+(?:\s*,\s*[A-Z][a-z]+)*)",
            r"sites?\s+in\s+([A-Z][a-z]+(?:\s*,\s*[A-Z][a-z]+)*)",
            r"(?:country|countries):\s*([A-Z][a-z]+(?:\s*,\s*[A-Z][a-z]+)*)",
        ]

        for pattern in country_patterns:
            matches = re.findall(pattern, protocol_text)
            for match in matches:
                for c in match.split(","):
                    c = c.strip()
                    if c and c not in countries:
                        countries.append(c)

        return countries

    def detect_severity_scale(self, protocol_text: str) -> str:
        """Detect which severity grading scale the study uses."""
        text_lower = protocol_text.lower()

        if "ctcae" in text_lower or "common terminology criteria" in text_lower:
            return "CTCAE"
        elif "mild" in text_lower and "moderate" in text_lower and "severe" in text_lower:
            # Check if using descriptive scale
            if "grade 1" not in text_lower and "grade 2" not in text_lower:
                return "DESCRIPTIVE"  # Mild/Moderate/Severe

        return "CTCAE"  # Default

    def detect_performance_status(self, protocol_text: str) -> str:
        """Detect which performance status scale is used."""
        text_lower = protocol_text.lower()

        if "asa score" in text_lower or "asa physical status" in text_lower:
            return "ASA"
        elif "who performance" in text_lower:
            return "WHO"
        elif "karnofsky" in text_lower:
            return "KARNOFSKY"
        else:
            return "ECOG"  # Default

    def extract_endpoints(self, protocol_text: str, study_type: StudyType) -> List[ProtocolEndpoint]:
        """Extract endpoints with proper statistical methods."""
        endpoints = []

        # Time-to-event patterns (use Cox/HR)
        tte_patterns = [
            (r"disease[\-\s]?free\s+survival", "Disease-Free Survival", True),
            (r"(?:time\s+to\s+)?recurrence", "Time to Recurrence", True),
            (r"overall\s+survival", "Overall Survival", False),
            (r"progression[\-\s]?free\s+survival", "Progression-Free Survival", True),
            (r"event[\-\s]?free\s+survival", "Event-Free Survival", True),
            (r"relapse[\-\s]?free", "Relapse-Free Survival", False),
        ]

        for pattern, name, is_primary in tte_patterns:
            if re.search(pattern, protocol_text.lower()):
                endpoints.append(ProtocolEndpoint(
                    name=name,
                    type=EndpointType.TIME_TO_EVENT,
                    definition=f"{name} from randomization",
                    primary=is_primary and study_type == StudyType.ADJUVANT,
                    method=StatisticalMethod.COX_REGRESSION,
                    measure="HR"
                ))

        # Binary endpoints (logistic/OR) - but NOT for adjuvant studies
        if study_type == StudyType.METASTATIC:
            binary_patterns = [
                (r"(?:objective\s+)?response\s+rate", "Objective Response Rate"),
                (r"complete\s+response", "Complete Response Rate"),
                (r"disease\s+control\s+rate", "Disease Control Rate"),
            ]

            for pattern, name in binary_patterns:
                if re.search(pattern, protocol_text.lower()):
                    endpoints.append(ProtocolEndpoint(
                        name=name,
                        type=EndpointType.BINARY,
                        definition=f"{name} per RECIST 1.1",
                        primary=True,
                        method=StatisticalMethod.LOGISTIC_REGRESSION,
                        measure="OR"
                    ))

        return endpoints

    def get_excluded_content(
        self,
        study_type: StudyType,
        countries: List[str],
        protocol_text: str
    ) -> Tuple[List[str], List[str], List[str]]:
        """
        Determine what to EXCLUDE from the SAP.

        Returns:
            - excluded_variables: Variables NOT to include
            - excluded_tables: Table types NOT to include
            - notes: Explanatory notes
        """
        excluded_vars = []
        excluded_tables = []
        notes = []

        # Nordic trial exclusions
        nordic_countries = {"Sweden", "Norway", "Denmark", "Finland", "Iceland"}
        if set(countries) & nordic_countries:
            excluded_vars.extend(["RACE", "ETHNICITY"])
            notes.append("Race/Ethnicity not collected (Nordic trial)")

        # Adjuvant study exclusions
        if study_type == StudyType.ADJUVANT:
            excluded_tables.extend([
                "tumor_response_table",
                "best_overall_response",
                "waterfall_plot",
                "spider_plot",
                "response_duration_responders"
            ])
            notes.append("No tumor response tables (adjuvant study - no measurable disease)")

        # Performance status check
        perf_status = self.detect_performance_status(protocol_text)
        if perf_status == "ASA":
            excluded_vars.append("ECOG")
            notes.append("Uses ASA Physical Status Score instead of ECOG")

        # Severity scale check
        severity = self.detect_severity_scale(protocol_text)
        if severity == "DESCRIPTIVE":
            notes.append("Uses Mild/Moderate/Severe grading (not CTCAE grades 1-5)")

        return excluded_vars, excluded_tables, notes

    def extract(self, protocol_text: str, study_id: str) -> ProtocolExtraction:
        """
        Full extraction from protocol text.

        Args:
            protocol_text: Full protocol document text
            study_id: Study identifier

        Returns:
            ProtocolExtraction with all extracted content
        """
        # Detect study type
        study_type = self.detect_study_type(protocol_text)

        # Detect countries
        countries = self.detect_countries(protocol_text)

        # Detect therapeutic area
        therapeutic_area = self._detect_therapeutic_area(protocol_text)

        # Get exclusions
        excluded_vars, excluded_tables, notes = self.get_excluded_content(
            study_type, countries, protocol_text
        )

        # Build baseline variables
        baseline_vars = self._build_baseline_variables(
            study_type, countries, therapeutic_area, excluded_vars, protocol_text
        )

        # Extract endpoints
        endpoints = self.extract_endpoints(protocol_text, study_type)

        # Extract populations
        populations = self._extract_populations(protocol_text)

        # Extract stratification factors
        strat_factors = self._extract_stratification(protocol_text)

        return ProtocolExtraction(
            study_id=study_id,
            study_type=study_type,
            therapeutic_area=therapeutic_area,
            countries=countries,
            baseline_variables=baseline_vars,
            endpoints=endpoints,
            populations=populations,
            stratification_factors=strat_factors,
            excluded_variables=excluded_vars,
            excluded_tables=excluded_tables,
            notes=notes
        )

    def _detect_therapeutic_area(self, text: str) -> str:
        """Detect therapeutic area."""
        text_lower = text.lower()

        if any(w in text_lower for w in ["colorectal", "colon", "rectal", "crc"]):
            return "colorectal_cancer"
        elif any(w in text_lower for w in ["breast cancer", "breast carcinoma"]):
            return "breast_cancer"
        elif any(w in text_lower for w in ["lung cancer", "nsclc", "sclc"]):
            return "lung_cancer"
        elif any(w in text_lower for w in ["melanoma", "skin cancer"]):
            return "melanoma"
        elif any(w in text_lower for w in ["leukemia", "lymphoma", "myeloma"]):
            return "hematologic_malignancy"
        else:
            return "solid_tumor"

    def _build_baseline_variables(
        self,
        study_type: StudyType,
        countries: List[str],
        therapeutic_area: str,
        excluded_vars: List[str],
        protocol_text: str
    ) -> List[ProtocolVariable]:
        """Build list of baseline variables for this specific study."""
        variables = []

        # Standard demographics (filtered)
        standard_demo = [
            ProtocolVariable("AGE", "Age at Randomization", "continuous",
                           unit="years", is_baseline=True,
                           summary_statistic="median (IQR, min-max)"),
            ProtocolVariable("SEX", "Sex", "categorical",
                           ["Female", "Male"], is_baseline=True,
                           summary_statistic="n (%)"),
        ]

        for var in standard_demo:
            if var.name not in excluded_vars:
                variables.append(var)

        # Add Nordic variables if applicable
        nordic_countries = {"Sweden", "Norway", "Denmark", "Finland", "Iceland"}
        if set(countries) & nordic_countries:
            for var in self.NORDIC_BASELINE_VARIABLES:
                if var.name not in excluded_vars:
                    variables.append(var)

        # Add disease-specific variables
        if therapeutic_area == "colorectal_cancer":
            for var in self.CRC_BASELINE_VARIABLES:
                if var.name not in excluded_vars:
                    variables.append(var)

        # Add performance status (correct one)
        perf_status = self.detect_performance_status(protocol_text)
        if perf_status == "ASA" and "ASA_SCORE" not in [v.name for v in variables]:
            variables.append(ProtocolVariable(
                "ASA_SCORE", "ASA Physical Status Score", "categorical",
                ["1", "2", "3", "4", "5"], is_baseline=True,
                summary_statistic="n (%)"
            ))
        elif perf_status == "ECOG" and "ECOG" not in excluded_vars:
            variables.append(ProtocolVariable(
                "ECOG", "ECOG Performance Status", "categorical",
                ["0", "1", "2"], is_baseline=True,
                summary_statistic="n (%)"
            ))

        return variables

    def _extract_populations(self, text: str) -> List[ProtocolPopulation]:
        """Extract analysis population definitions."""
        populations = []

        # Common patterns
        patterns = [
            (r"(?:full\s+analysis|intention[\-\s]to[\-\s]treat|ITT)\s+(?:population|set)[:\s]+([^.]+\.)",
             "Full Analysis Population", "FAP"),
            (r"per[\-\s]?protocol\s+(?:population|set)[:\s]+([^.]+\.)",
             "Per-Protocol Population", "PP"),
            (r"safety\s+(?:population|set|analysis)[:\s]+([^.]+\.)",
             "Safety Population", "SAF"),
        ]

        for pattern, name, abbrev in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                populations.append(ProtocolPopulation(
                    name=name,
                    abbreviation=abbrev,
                    definition=match.group(1).strip()
                ))

        # Default populations if not found
        if not populations:
            populations = [
                ProtocolPopulation(
                    "Full Analysis Population", "FAP",
                    "All randomized subjects"
                ),
                ProtocolPopulation(
                    "Safety Population", "SAF",
                    "All subjects who received at least one dose of study treatment"
                ),
            ]

        return populations

    def _extract_stratification(self, text: str) -> List[str]:
        """Extract stratification factors."""
        factors = []

        # Look for stratification section
        strat_match = re.search(
            r"stratif(?:y|ied|ication)[^:]*:\s*([^.]+(?:\.[^.]+)*)",
            text, re.IGNORECASE
        )

        if strat_match:
            strat_text = strat_match.group(1)
            # Parse factors
            factor_patterns = [
                r"tumor\s+(?:location|site)",
                r"(?:pTNM\s+)?stage",
                r"(?:mutation\s+)?(?:type|status)",
                r"country",
                r"center",
                r"age\s+group",
            ]
            for pattern in factor_patterns:
                if re.search(pattern, strat_text, re.IGNORECASE):
                    factors.append(pattern.replace(r"\s+", " ").replace("(?:", "").replace(")?", ""))

        return factors


def format_protocol_extraction_report(extraction: ProtocolExtraction) -> str:
    """Format extraction as readable report."""
    lines = [
        "=" * 70,
        f"PROTOCOL-SPECIFIC EXTRACTION: {extraction.study_id}",
        "=" * 70,
        "",
        f"Study Type: {extraction.study_type.value.upper()}",
        f"Therapeutic Area: {extraction.therapeutic_area}",
        f"Countries: {', '.join(extraction.countries) or 'Not specified'}",
        "",
    ]

    # Exclusions
    if extraction.excluded_variables or extraction.excluded_tables:
        lines.append("EXCLUSIONS (Do NOT include in SAP):")
        lines.append("-" * 40)
        for var in extraction.excluded_variables:
            lines.append(f"  ❌ Variable: {var}")
        for table in extraction.excluded_tables:
            lines.append(f"  ❌ Table: {table}")
        lines.append("")

    # Notes
    if extraction.notes:
        lines.append("IMPORTANT NOTES:")
        lines.append("-" * 40)
        for note in extraction.notes:
            lines.append(f"  ⚠️ {note}")
        lines.append("")

    # Baseline variables
    lines.append(f"BASELINE VARIABLES ({len(extraction.baseline_variables)}):")
    lines.append("-" * 40)
    for var in extraction.baseline_variables:
        strat = " [STRATIFICATION]" if var.is_stratification else ""
        if var.categories:
            cats = ", ".join(var.categories[:3])
            if len(var.categories) > 3:
                cats += f" (+{len(var.categories)-3} more)"
            lines.append(f"  {var.name}: {var.label}{strat}")
            lines.append(f"      Categories: {cats}")
        else:
            unit = f" ({var.unit})" if var.unit else ""
            lines.append(f"  {var.name}: {var.label}{unit}{strat}")
        lines.append(f"      Summary: {var.summary_statistic}")
    lines.append("")

    # Endpoints
    lines.append(f"ENDPOINTS ({len(extraction.endpoints)}):")
    lines.append("-" * 40)
    for ep in extraction.endpoints:
        primary = " [PRIMARY]" if ep.primary else ""
        lines.append(f"  {ep.name}{primary}")
        lines.append(f"      Type: {ep.type.value}")
        lines.append(f"      Method: {ep.method.value} → {ep.measure}")
    lines.append("")

    # Populations
    lines.append(f"ANALYSIS POPULATIONS ({len(extraction.populations)}):")
    lines.append("-" * 40)
    for pop in extraction.populations:
        lines.append(f"  {pop.abbreviation}: {pop.name}")
        lines.append(f"      {pop.definition}")

    return "\n".join(lines)


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("PROTOCOL-SPECIFIC EXTRACTOR TEST")
    print("=" * 70)

    # Test with ALASCCA-like protocol text
    alascca_text = """
    ALASCCA is a randomized, double-blind, placebo-controlled Phase III trial
    investigating low-dose aspirin (ASA) versus placebo in patients with
    PIK3CA-mutated colorectal cancer who have undergone curative surgical resection.

    The study is conducted in Sweden, Norway, Denmark, and Finland.

    Primary endpoint: Disease-free survival (DFS) at 3 years
    Secondary endpoints: Time to recurrence, Overall survival at 5 years

    Patients will be stratified by tumor location (colon vs rectum) and
    pTNM stage (Stage II vs Stage III).

    ASA Physical Status Score will be recorded at baseline.
    Adverse events will be graded as Mild, Moderate, or Severe.

    Full Analysis Population: All randomized subjects, with the sole exception
    of subjects that were randomized by mistake and never included into the trial.
    """

    extractor = ProtocolSpecificExtractor()
    extraction = extractor.extract(alascca_text, "ALASCCA")

    print(format_protocol_extraction_report(extraction))
