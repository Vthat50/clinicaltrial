#!/usr/bin/env python3
"""
Oncology Decision Engine - Intelligent routing to correct criteria and methods
Uses the production knowledge graph (ChromaDB) to make evidence-based recommendations

Location: enterprise_sap_system/core/decision_engine.py
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Lazy import to avoid circular imports
_vector_store = None

def _get_vector_store():
    """Get the shared vector store singleton (ensures auto-indexing completes first)"""
    global _vector_store
    if _vector_store is None:
        from enterprise_sap_system.rag.vector_store import create_vector_store
        _vector_store = create_vector_store()
    return _vector_store


@dataclass
class Recommendation:
    """Structured recommendation with evidence"""
    primary: str
    confidence: float
    reasoning: List[str]
    implementation: Dict[str, Any]
    sources: List[Dict[str, str]]
    alternatives: List[Dict[str, Any]] = field(default_factory=list)


class OncologyDecisionEngine:
    """
    Intelligent decision engine for oncology SAP generation

    Queries the knowledge graph to recommend:
    - Response criteria (RECIST, iRECIST, Choi, mRECIST, etc.)
    - Statistical methods
    - Analysis populations
    - Endpoint definitions

    Uses evidence from:
    - Tier 1: Official criteria documents (sap_methods collection)
    - Tier 2: Real SAP examples (specialized_sap_examples collection)
    - Tier 3: Historical patterns (sap_statistical_methods collection)
    """

    def __init__(self, chromadb_path: str = None):
        """
        Initialize decision engine using shared vector store

        Uses the singleton vector_store which ensures auto-indexing completes
        before collections are accessed.
        """
        try:
            # Use shared vector store (ensures auto-indexing is complete)
            vector_store = _get_vector_store()
            self.client = vector_store.client

            # Map to vector_store collections (they use sap_ prefix)
            # methods -> sap_methods, statistical_methods -> sap_statistical_methods
            self.sap_methods = self._get_collection("sap_methods")
            self.specialized_saps = self._get_collection("sap_endpoints")  # Use endpoints as SAP examples
            self.historical_saps = self._get_collection("sap_statistical_methods")

            methods_count = self.sap_methods.count() if self.sap_methods else 0
            saps_count = self.specialized_saps.count() if self.specialized_saps else 0
            historical_count = self.historical_saps.count() if self.historical_saps else 0

            logger.info(f"[DecisionEngine] Initialized: {methods_count} methods, "
                       f"{saps_count} endpoints, {historical_count} statistical_methods")
            print(f"[DecisionEngine] ✓ Initialized with {methods_count} methods, {saps_count} endpoints, {historical_count} statistical_methods")

        except Exception as e:
            logger.error(f"[DecisionEngine] Failed to initialize: {e}")
            print(f"[DecisionEngine] ✗ Failed to initialize: {e}")
            self.client = None
            self.sap_methods = None
            self.specialized_saps = None
            self.historical_saps = None

    def _get_collection(self, name: str):
        """Safely get a collection from the shared ChromaDB client"""
        if self.client is None:
            return None
        try:
            return self.client.get_collection(name)
        except Exception as e:
            logger.warning(f"[DecisionEngine] Collection '{name}' not found: {e}")
            return None

    def recommend_response_criteria(self, protocol_facts) -> Recommendation:
        """
        Recommend appropriate response criteria based on protocol

        Args:
            protocol_facts: ExtractedProtocolFacts from sectioned_extractor

        Returns:
            Recommendation with criteria, confidence, reasoning, implementation
        """

        # Extract key protocol characteristics
        indication = self._extract_indication(protocol_facts)
        treatment_type = self._classify_treatment(protocol_facts)

        logger.info(f"[DecisionEngine] Recommending response criteria: indication={indication}, treatment={treatment_type}")

        # Route to appropriate criteria
        if "gist" in indication:
            return self._recommend_choi_criteria(protocol_facts)

        elif "hcc" in indication or "hepatocellular" in indication:
            return self._recommend_mrecist(protocol_facts)

        elif "lymphoma" in indication:
            return self._recommend_lugano(protocol_facts)

        elif "myeloma" in indication:
            return self._recommend_imwg(protocol_facts)

        elif any(term in indication for term in ["aml", "leukemia", "cll", "all"]):
            return self._recommend_iwg_eln(protocol_facts)

        elif any(term in indication for term in ["brain", "glioblastoma", "glioma"]):
            return self._recommend_rano(protocol_facts)

        elif "prostate" in indication:
            return self._recommend_pcwg3(protocol_facts)

        elif treatment_type == "immunotherapy":
            return self._recommend_irecist(protocol_facts)

        else:
            return self._recommend_recist11(protocol_facts)

    def recommend_statistical_methods(self, protocol_facts) -> Recommendation:
        """
        Recommend statistical methods based on protocol design

        Args:
            protocol_facts: ExtractedProtocolFacts

        Returns:
            Recommendation with methods, confidence, reasoning
        """

        sample_size = self._get_sample_size(protocol_facts)
        num_arms = self._get_num_arms(protocol_facts)
        primary_endpoint_type = self._classify_endpoint_type(protocol_facts)

        logger.info(f"[DecisionEngine] Recommending statistical methods: N={sample_size}, "
                   f"arms={num_arms}, endpoint={primary_endpoint_type}")

        # Small sample size (< 50)
        if sample_size and sample_size < 50:
            return self._recommend_small_sample_methods(protocol_facts)

        # Time-to-event endpoints
        if primary_endpoint_type in ["TTE", "OS", "PFS", "DFS"]:
            return self._recommend_tte_methods(protocol_facts, num_arms)

        # Binary endpoints (ORR, DCR)
        if primary_endpoint_type in ["binary", "ORR", "DCR"]:
            return self._recommend_binary_methods(protocol_facts, num_arms)

        # Continuous endpoints
        if primary_endpoint_type == "continuous":
            return self._recommend_continuous_methods(protocol_facts, num_arms)

        # Default: descriptive
        return self._recommend_descriptive_methods(protocol_facts)

    def recommend_population_definitions(self, protocol_facts) -> Dict[str, str]:
        """
        Recommend ITT, FAS, PP, Safety population definitions

        Args:
            protocol_facts: ExtractedProtocolFacts OR flat dict from production_pipeline

        Returns:
            Dict with population definitions (keys match production_pipeline expectations)
        """

        num_arms = self._get_num_arms(protocol_facts)
        randomized = self._is_randomized(protocol_facts)

        if num_arms == 1 or not randomized:
            # Single-arm or non-randomized
            itt_def = "all enrolled subjects who meet eligibility criteria"
            fas_def = "all subjects who received at least one dose of study treatment"
        else:
            # Randomized
            itt_def = "all randomized subjects"
            fas_def = "all randomized subjects who received at least one dose of study treatment"

        # Keys match what production_pipeline.py expects
        return {
            "itt_definition": itt_def,
            "fas_definition": fas_def,
            "per_protocol_definition": "all subjects in the FAS who completed the study per protocol without major protocol deviations",
            "safety_population_definition": "all subjects who received at least one dose of study treatment"
        }

    # ========================================================================
    # PRIVATE METHODS: Criteria-specific recommendations
    # ========================================================================

    def _recommend_choi_criteria(self, protocol_facts) -> Recommendation:
        """Choi Criteria for GIST on TKI therapy"""

        choi_docs = self._query_collection(
            self.sap_methods,
            "Choi Criteria GIST imatinib size density",
            where={"criteria": "Choi Criteria"},
            n_results=3
        )

        gist_saps = self._query_collection(
            self.specialized_saps,
            "GIST imatinib response assessment Choi",
            where={"category": "GIST"},
            n_results=5
        )

        return Recommendation(
            primary="Choi Criteria",
            confidence=0.97,
            reasoning=[
                "GIST on TKI therapy detected",
                "Choi Criteria required per Choi et al., JCO 2007",
                "Measures tumor size AND density (Hounsfield units)",
                "97% sensitive vs RECIST 52% for GIST on imatinib",
                "FDA-accepted for GIST since 2006"
            ],
            implementation={
                "criteria": "Choi Criteria",
                "imaging": "Contrast-enhanced CT with arterial and portal venous phases",
                "measurements": "Longest diameter (mm) AND tumor density (Hounsfield units)",
                "pr_threshold": "≥10% decrease in size OR ≥15% decrease in density",
                "cr_threshold": "Disappearance of all lesions OR density <20 HU",
                "pd_threshold": "≥10% increase in size AND no ≥15% decrease in density",
                "timing": "Every 8 weeks (standard) or per protocol",
                "citation": "Choi H, et al. J Clin Oncol. 2007;25(13):1753-1759"
            },
            sources=self._format_sources(choi_docs, gist_saps),
            alternatives=[{
                "criteria": "RECIST 1.1",
                "when_appropriate": "If sponsor explicitly specifies RECIST 1.1",
                "trade_offs": "Less sensitive to density changes in GIST on TKI"
            }]
        )

    def _recommend_mrecist(self, protocol_facts) -> Recommendation:
        """mRECIST for HCC"""

        mrecist_docs = self._query_collection(
            self.sap_methods,
            "mRECIST HCC viable tumor arterial enhancement",
            where={"criteria": "mRECIST"},
            n_results=3
        )

        hcc_saps = self._query_collection(
            self.specialized_saps,
            "HCC sorafenib lenvatinib mRECIST viable",
            where={"category": "HCC_mRECIST"},
            n_results=5
        )

        return Recommendation(
            primary="mRECIST",
            confidence=0.95,
            reasoning=[
                "HCC on systemic therapy detected",
                "mRECIST required per Lencioni & Llovet, SLD 2010",
                "Measures only VIABLE (enhancing) tumor",
                "Standard for HCC trials with sorafenib, lenvatinib",
                "FDA/EMA accepted"
            ],
            implementation={
                "criteria": "mRECIST",
                "imaging": "Multiphase CT or MRI with late arterial phase (25-35 sec post-contrast)",
                "measurement": "Sum of diameters of VIABLE (arterially enhancing) tumor only",
                "pr_threshold": "≥30% decrease in sum of viable tumor diameters",
                "cr_threshold": "Disappearance of any arterial enhancement in all target lesions",
                "pd_threshold": "≥20% increase in sum of viable tumor diameters",
                "special": "Portal vein tumor thrombus (PVTT) assessed for enhancement",
                "citation": "Lencioni R, Llovet JM. Semin Liver Dis. 2010;30(1):52-60"
            },
            sources=self._format_sources(mrecist_docs, hcc_saps),
            alternatives=[{
                "criteria": "RECIST 1.1",
                "when_appropriate": "Ablation/TACE studies may use RECIST",
                "trade_offs": "Measures total lesion size, not viable tumor"
            }]
        )

    def _recommend_irecist(self, protocol_facts) -> Recommendation:
        """iRECIST for immunotherapy"""

        irecist_docs = self._query_collection(
            self.sap_methods,
            "iRECIST immunotherapy pseudoprogression iUPD iCPD",
            where={"binding": "required_for_immunotherapy"},
            n_results=3
        )

        immuno_saps = self._query_collection(
            self.specialized_saps,
            "immunotherapy checkpoint inhibitor iRECIST",
            where={"category": "iRECIST"},
            n_results=5
        )

        return Recommendation(
            primary="iRECIST",
            confidence=0.95,
            reasoning=[
                "Immunotherapy (checkpoint inhibitor) detected",
                "iRECIST required per Seymour et al., Lancet Oncol 2017",
                "Accounts for pseudoprogression (~10% of patients)",
                "Requires 4-8 week confirmation of progression",
                "Use RECIST 1.1 for primary analysis per FDA guidance"
            ],
            implementation={
                "criteria": "iRECIST",
                "primary_endpoint": "Use RECIST 1.1 per FDA guidance",
                "exploratory": "iRECIST for exploratory analysis",
                "new_categories": "iUPD (unconfirmed PD), iCPD (confirmed PD)",
                "confirmation": "Repeat imaging 4-8 weeks after iUPD to confirm progression",
                "treatment": "Continue treatment through iUPD if clinically stable",
                "citation": "Seymour L, et al. Lancet Oncol. 2017;18(3):e143-e152"
            },
            sources=self._format_sources(irecist_docs, immuno_saps),
            alternatives=[{
                "criteria": "RECIST 1.1 only",
                "when_appropriate": "If no pseudoprogression expected (e.g., biomarker-selected)",
                "trade_offs": "May miss delayed responses"
            }]
        )

    def _recommend_recist11(self, protocol_facts) -> Recommendation:
        """RECIST 1.1 for standard solid tumors"""

        recist_docs = self._query_collection(
            self.sap_methods,
            "RECIST 1.1 solid tumors target lesions CR PR SD PD",
            n_results=3
        )

        return Recommendation(
            primary="RECIST 1.1",
            confidence=0.90,
            reasoning=[
                "Standard solid tumor trial",
                "RECIST 1.1 per Eisenhauer et al., Eur J Cancer 2009",
                "FDA/EMA standard for most solid tumors",
                "Validated and widely accepted"
            ],
            implementation={
                "criteria": "RECIST 1.1",
                "target_lesions": "Maximum 5 total (2 per organ)",
                "measurement": "Longest diameter in axial plane",
                "pr_threshold": "≥30% decrease in sum of diameters",
                "cr_threshold": "Disappearance of all target lesions",
                "pd_threshold": "≥20% increase in sum of diameters (minimum 5mm absolute increase)",
                "new_lesions": "Appearance of new lesions = PD",
                "confirmation": "PR/CR confirmed ≥4 weeks later",
                "citation": "Eisenhauer EA, et al. Eur J Cancer. 2009;45(2):228-247"
            },
            sources=self._format_sources(recist_docs),
            alternatives=[]
        )

    def _recommend_lugano(self, protocol_facts) -> Recommendation:
        """Lugano Classification for lymphoma"""

        lugano_docs = self._query_collection(
            self.sap_methods,
            "Lugano Classification lymphoma PET Deauville",
            where={"criteria": "Lugano Classification"},
            n_results=3
        )

        lymphoma_saps = self._query_collection(
            self.specialized_saps,
            "lymphoma Lugano PET response Deauville",
            where={"category": "lymphoma_Lugano"},
            n_results=5
        )

        return Recommendation(
            primary="Lugano Classification",
            confidence=0.93,
            reasoning=[
                "Lymphoma indication detected",
                "Lugano Classification per Cheson et al., JCO 2014",
                "Incorporates PET-CT and Deauville scoring",
                "Standard for Hodgkin and non-Hodgkin lymphoma"
            ],
            implementation={
                "criteria": "Lugano Classification 2014",
                "imaging": "PET-CT with Deauville 5-point scale",
                "response_categories": "CR, PR, SD, PD based on metabolic and anatomic response",
                "citation": "Cheson BD, et al. J Clin Oncol. 2014;32(27):3059-3068"
            },
            sources=self._format_sources(lugano_docs, lymphoma_saps),
            alternatives=[]
        )

    def _recommend_imwg(self, protocol_facts) -> Recommendation:
        """IMWG Criteria for myeloma"""

        imwg_docs = self._query_collection(
            self.sap_methods,
            "IMWG myeloma M-protein CR VGPR PR",
            where={"criteria": "IMWG Criteria"},
            n_results=3
        )

        myeloma_saps = self._query_collection(
            self.specialized_saps,
            "myeloma IMWG M-protein response",
            where={"category": "myeloma"},
            n_results=5
        )

        return Recommendation(
            primary="IMWG Criteria",
            confidence=0.94,
            reasoning=[
                "Myeloma indication detected",
                "IMWG Criteria per Kumar et al., Lancet Oncol 2016",
                "Measures M-protein and bone marrow involvement",
                "International standard for multiple myeloma"
            ],
            implementation={
                "criteria": "IMWG Criteria 2016",
                "response_categories": "sCR, CR, VGPR, PR, SD, PD",
                "key_measurements": "M-protein (serum/urine), bone marrow plasma cells",
                "citation": "Kumar S, et al. Lancet Oncol. 2016;17(8):e328-e346"
            },
            sources=self._format_sources(imwg_docs, myeloma_saps),
            alternatives=[]
        )

    def _recommend_iwg_eln(self, protocol_facts) -> Recommendation:
        """IWG/ELN Criteria for leukemia"""

        iwg_docs = self._query_collection(
            self.sap_methods,
            "IWG ELN leukemia AML blast count CR CRi",
            where={"criteria": "IWG/ELN Criteria"},
            n_results=3
        )

        leukemia_saps = self._query_collection(
            self.specialized_saps,
            "leukemia AML IWG ELN blast response",
            where={"category": "leukemia_IWG"},
            n_results=5
        )

        return Recommendation(
            primary="IWG/ELN Criteria",
            confidence=0.93,
            reasoning=[
                "Leukemia/AML indication detected",
                "IWG/ELN Criteria per Döhner et al., Blood 2017",
                "Measures blast counts and cytogenetics",
                "ELN consensus standard"
            ],
            implementation={
                "criteria": "IWG/ELN Criteria 2017",
                "response_categories": "CR, CRi, PR, SD, Progressive Disease",
                "key_measurements": "Bone marrow and peripheral blast counts",
                "citation": "Döhner H, et al. Blood. 2017;129(4):424-447"
            },
            sources=self._format_sources(iwg_docs, leukemia_saps),
            alternatives=[]
        )

    def _recommend_rano(self, protocol_facts) -> Recommendation:
        """RANO Criteria for brain tumors"""

        rano_docs = self._query_collection(
            self.sap_methods,
            "RANO brain tumor glioblastoma pseudoprogression",
            where={"criteria": "RANO Criteria"},
            n_results=3
        )

        brain_saps = self._query_collection(
            self.specialized_saps,
            "brain tumor glioblastoma RANO response",
            where={"category": "brain_RANO"},
            n_results=5
        )

        return Recommendation(
            primary="RANO Criteria",
            confidence=0.92,
            reasoning=[
                "Brain tumor indication detected",
                "RANO Criteria per Wen et al., JCO 2010",
                "Accounts for pseudoprogression and corticosteroid effects",
                "Standard for high-grade gliomas"
            ],
            implementation={
                "criteria": "RANO Criteria 2010",
                "imaging": "MRI with contrast",
                "response_categories": "CR, PR, SD, PD",
                "special_considerations": "Pseudoprogression, corticosteroid use",
                "citation": "Wen PY, et al. J Clin Oncol. 2010;28(11):1963-1972"
            },
            sources=self._format_sources(rano_docs, brain_saps),
            alternatives=[]
        )

    def _recommend_pcwg3(self, protocol_facts) -> Recommendation:
        """PCWG3 Criteria for prostate cancer"""

        pcwg3_docs = self._query_collection(
            self.sap_methods,
            "PCWG3 prostate PSA bone scan response",
            where={"criteria": "PCWG3 Criteria"},
            n_results=3
        )

        prostate_saps = self._query_collection(
            self.specialized_saps,
            "prostate cancer PCWG PSA response",
            where={"category": "prostate_PCWG"},
            n_results=5
        )

        return Recommendation(
            primary="PCWG3 Criteria",
            confidence=0.91,
            reasoning=[
                "Prostate cancer indication detected",
                "PCWG3 Criteria per Scher et al., JCO 2016",
                "Integrates PSA, imaging, and clinical progression",
                "Standard for castration-resistant prostate cancer trials"
            ],
            implementation={
                "criteria": "PCWG3 Criteria 2016",
                "endpoints": "PSA response, radiographic progression-free survival",
                "psa_response": "≥50% decline from baseline confirmed ≥4 weeks later",
                "citation": "Scher HI, et al. J Clin Oncol. 2016;34(12):1402-1418"
            },
            sources=self._format_sources(pcwg3_docs, prostate_saps),
            alternatives=[]
        )

    # ========================================================================
    # PRIVATE METHODS: Statistical methods recommendations
    # ========================================================================

    def _recommend_small_sample_methods(self, protocol_facts) -> Recommendation:
        """Statistical methods for small sample sizes (< 50)"""

        sample_size = self._get_sample_size(protocol_facts)

        return Recommendation(
            primary="Descriptive statistics only, no formal hypothesis testing",
            confidence=0.92,
            reasoning=[
                f"Small sample size (N={sample_size}) insufficient for formal testing",
                "Precedent in similar small studies",
                "Focus on descriptive summaries and confidence intervals",
                "Kaplan-Meier method for time-to-event endpoints"
            ],
            implementation={
                "primary_analysis": "Descriptive statistics (frequencies, percentages, medians, ranges)",
                "time_to_event": "Kaplan-Meier method with 95% confidence intervals",
                "hypothesis_testing": "None performed due to small sample size",
                "sample_citation": "Similar approach used in phase 1/pilot studies"
            },
            sources=[],
            alternatives=[]
        )

    def _recommend_tte_methods(self, protocol_facts, num_arms: int) -> Recommendation:
        """Statistical methods for time-to-event endpoints"""

        if num_arms == 1:
            methods = {
                "primary_analysis": "Kaplan-Meier method",
                "estimates": "Median survival time with 95% CI",
                "survival_rates": "Survival rates at key timepoints (e.g., 6, 12, 24 months)",
                "hypothesis_testing": "Not applicable for single-arm study"
            }
            reasoning = [
                "Time-to-event endpoint (OS, PFS, or DFS)",
                "Single-arm study - descriptive survival analysis",
                "Kaplan-Meier method for survival estimation",
                "No formal comparison testing"
            ]
            primary = "Kaplan-Meier method"
        else:
            methods = {
                "primary_analysis": "Cox proportional hazards model",
                "effect_measure": "Hazard ratio (HR) with 95% CI",
                "hypothesis_test": "Stratified log-rank test",
                "survival_curves": "Kaplan-Meier curves by treatment arm",
                "adjustment": "Stratified by randomization factors"
            }
            reasoning = [
                "Time-to-event endpoint (OS, PFS, or DFS)",
                "Randomized study - comparative survival analysis",
                "Cox model for hazard ratio estimation",
                "Stratified log-rank test for treatment comparison"
            ]
            primary = "Kaplan-Meier and Cox regression"

        return Recommendation(
            primary=primary,
            confidence=0.94,
            reasoning=reasoning,
            implementation=methods,
            sources=[],
            alternatives=[]
        )

    def _recommend_binary_methods(self, protocol_facts, num_arms: int) -> Recommendation:
        """Statistical methods for binary endpoints (ORR, DCR)"""

        sample_size = self._get_sample_size(protocol_facts)

        if num_arms == 1:
            methods = {
                "primary_analysis": "Binomial proportion with exact 95% CI (Clopper-Pearson)",
                "point_estimate": "Overall response rate (ORR) as percentage",
                "confidence_interval": "Exact binomial 95% CI",
                "hypothesis_testing": "One-sample binomial test vs. historical control" if sample_size and sample_size < 100 else "Not applicable"
            }
            reasoning = [
                "Binary endpoint (ORR or DCR)",
                "Single-arm study - proportion estimation",
                "Exact binomial CI recommended for small samples",
                "May compare to historical control rate"
            ]
            primary = "Binomial proportion estimation"
        else:
            methods = {
                "primary_analysis": "Cochran-Mantel-Haenszel test stratified by randomization factors",
                "effect_measure": "Risk difference and risk ratio with 95% CI",
                "hypothesis_test": "Stratified CMH test",
                "logistic_regression": "Used for covariate adjustment if needed"
            }
            reasoning = [
                "Binary endpoint (ORR or DCR)",
                "Randomized study - comparative proportion analysis",
                "CMH test for stratified comparison",
                "Logistic regression for adjusted analysis"
            ]
            primary = "CMH test"

        return Recommendation(
            primary=primary,
            confidence=0.90,
            reasoning=reasoning,
            implementation=methods,
            sources=[],
            alternatives=[]
        )

    def _recommend_continuous_methods(self, protocol_facts, num_arms: int) -> Recommendation:
        """Statistical methods for continuous endpoints"""

        if num_arms == 1:
            methods = {
                "primary_analysis": "Descriptive statistics (mean, median, SD, range)",
                "confidence_interval": "95% CI for mean change from baseline",
                "hypothesis_testing": "One-sample t-test or Wilcoxon signed-rank test"
            }
            primary = "Descriptive statistics"
        else:
            methods = {
                "primary_analysis": "ANCOVA model adjusting for baseline",
                "effect_measure": "Least squares mean difference with 95% CI",
                "hypothesis_test": "F-test from ANCOVA model",
                "alternative": "Wilcoxon rank-sum test if non-normal distribution"
            }
            primary = "ANCOVA"

        return Recommendation(
            primary=primary,
            confidence=0.88,
            reasoning=[
                "Continuous endpoint detected",
                "ANCOVA adjusts for baseline values" if num_arms > 1 else "Descriptive analysis for single-arm",
                "Non-parametric alternative if distribution assumption violated"
            ],
            implementation=methods,
            sources=[],
            alternatives=[]
        )

    def _recommend_descriptive_methods(self, protocol_facts) -> Recommendation:
        """Default: descriptive methods"""

        return Recommendation(
            primary="Descriptive statistics",
            confidence=0.75,
            reasoning=[
                "Endpoint type unclear or multiple endpoints",
                "Descriptive approach recommended as default",
                "Specific methods depend on endpoint distribution"
            ],
            implementation={
                "categorical": "Frequencies and percentages",
                "continuous": "Mean, median, SD, range, 95% CI",
                "time_to_event": "Kaplan-Meier method"
            },
            sources=[],
            alternatives=[]
        )

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _query_collection(self, collection, query_text: str, where: dict = None, n_results: int = 5):
        """Safely query a ChromaDB collection"""
        if collection is None:
            return None

        try:
            kwargs = {
                "query_texts": [query_text],
                "n_results": n_results
            }
            if where:
                kwargs["where"] = where

            return collection.query(**kwargs)
        except Exception as e:
            logger.warning(f"[DecisionEngine] Query failed: {e}")
            # Try without filter
            try:
                return collection.query(
                    query_texts=[query_text],
                    n_results=n_results
                )
            except:
                return None

    def _extract_indication(self, protocol_facts) -> str:
        """Extract primary indication from protocol facts (handles both object and flat dict)"""
        disease_type = ""
        tumor_type = ""

        # Handle flat dict (from production_pipeline.py)
        if isinstance(protocol_facts, dict):
            disease_type = protocol_facts.get('disease_type', '') or ''
            tumor_type = protocol_facts.get('tumor_type', '') or ''
        # Handle ExtractedProtocolFacts object
        elif hasattr(protocol_facts, 'study_design'):
            disease_type = getattr(protocol_facts.study_design, 'disease_type', '') or ''
            tumor_type = getattr(protocol_facts.study_design, 'tumor_type', '') or ''

        indication = disease_type or tumor_type or 'unknown'
        return indication.strip().lower()

    def _classify_treatment(self, protocol_facts) -> str:
        """Classify treatment type (immunotherapy, TKI, chemotherapy, etc.) - handles both object and flat dict"""
        drug_name = ""

        # Handle flat dict (from production_pipeline.py)
        if isinstance(protocol_facts, dict):
            drug_name = (protocol_facts.get('drug_name', '') or '').lower()
        # Handle ExtractedProtocolFacts object
        elif hasattr(protocol_facts, 'study_design'):
            drug_name = (getattr(protocol_facts.study_design, 'drug_name', '') or '').lower()

        # Immunotherapy
        immuno_keywords = ['pembrolizumab', 'nivolumab', 'atezolizumab', 'durvalumab',
                          'ipilimumab', 'anti-pd-1', 'anti-pd-l1', 'anti-ctla-4',
                          'checkpoint inhibitor', 'avelumab', 'cemiplimab']
        if any(kw in drug_name for kw in immuno_keywords):
            return 'immunotherapy'

        # TKI
        tki_keywords = ['imatinib', 'sunitinib', 'sorafenib', 'lenvatinib', 'regorafenib',
                       'pazopanib', 'cabozantinib', 'axitinib', 'gefitinib', 'erlotinib',
                       'osimertinib', 'crizotinib', 'alectinib']
        if any(kw in drug_name for kw in tki_keywords):
            return 'TKI'

        # VEGF inhibitor
        vegf_keywords = ['bevacizumab', 'ramucirumab', 'aflibercept']
        if any(kw in drug_name for kw in vegf_keywords):
            return 'VEGF_inhibitor'

        return 'other'

    def _classify_endpoint_type(self, protocol_facts) -> str:
        """Classify primary endpoint type - handles both object and flat dict"""
        primary_endpoint = ""

        # Handle flat dict (from production_pipeline.py)
        if isinstance(protocol_facts, dict):
            primary_endpoint = (protocol_facts.get('primary_endpoint', '') or '').lower()
        # Handle ExtractedProtocolFacts object
        elif hasattr(protocol_facts, 'endpoints'):
            primary_endpoint = (getattr(protocol_facts.endpoints, 'primary_endpoint', '') or '').lower()

        if not primary_endpoint:
            return 'unknown'

        # Time-to-event
        if any(kw in primary_endpoint for kw in ['survival', 'pfs', 'dfs', 'efs', 'time to']):
            if 'overall survival' in primary_endpoint or ' os' in primary_endpoint:
                return 'OS'
            elif 'progression-free' in primary_endpoint or 'pfs' in primary_endpoint:
                return 'PFS'
            elif 'disease-free' in primary_endpoint or 'dfs' in primary_endpoint:
                return 'DFS'
            else:
                return 'TTE'

        # Binary
        if any(kw in primary_endpoint for kw in ['response rate', 'orr', 'dcr', 'proportion', 'objective response']):
            return 'binary'

        # Continuous
        if any(kw in primary_endpoint for kw in ['change from baseline', 'mean', 'score']):
            return 'continuous'

        return 'unknown'

    def _get_sample_size(self, protocol_facts) -> Optional[int]:
        """Get sample size from protocol facts - handles both object and flat dict"""
        # Handle flat dict (from production_pipeline.py)
        if isinstance(protocol_facts, dict):
            n = protocol_facts.get('sample_size')
            if n is not None:
                try:
                    return int(n)
                except (ValueError, TypeError):
                    return None
            return None
        # Handle ExtractedProtocolFacts object
        if hasattr(protocol_facts, 'sample_size'):
            return getattr(protocol_facts.sample_size, 'sample_size', None)
        return None

    def _get_num_arms(self, protocol_facts) -> int:
        """Get number of arms from protocol facts - handles both object and flat dict"""
        # Handle flat dict (from production_pipeline.py)
        if isinstance(protocol_facts, dict):
            num_arms = protocol_facts.get('num_arms')
            if num_arms is not None:
                try:
                    return int(num_arms)
                except (ValueError, TypeError):
                    return 1
            # Check is_single_arm
            if protocol_facts.get('is_single_arm'):
                return 1
            return 1
        # Handle ExtractedProtocolFacts object
        if hasattr(protocol_facts, 'study_design'):
            return getattr(protocol_facts.study_design, 'num_arms', 1) or 1
        return 1

    def _is_randomized(self, protocol_facts) -> bool:
        """Check if study is randomized - handles both object and flat dict"""
        # Handle flat dict (from production_pipeline.py)
        if isinstance(protocol_facts, dict):
            # Check multiple possible keys
            randomized = protocol_facts.get('is_randomized') or protocol_facts.get('randomized')
            if randomized is not None:
                return bool(randomized)
            # If is_single_arm is True, likely not randomized
            if protocol_facts.get('is_single_arm'):
                return False
            # If num_arms > 1, likely randomized
            num_arms = protocol_facts.get('num_arms', 1)
            if num_arms and int(num_arms) > 1:
                return True
            return False
        # Handle ExtractedProtocolFacts object
        if hasattr(protocol_facts, 'study_design'):
            return getattr(protocol_facts.study_design, 'randomized', False) or False
        return False

    def _format_sources(self, *results_list) -> List[Dict[str, str]]:
        """Format ChromaDB query results into source citations"""
        sources = []

        for results in results_list:
            if not results or 'documents' not in results:
                continue

            docs = results.get('documents', [[]])[0]
            metas = results.get('metadatas', [[]])[0]

            for i, doc in enumerate(docs[:3]):
                metadata = metas[i] if i < len(metas) else {}

                source = {
                    "text": doc[:200] + "..." if len(doc) > 200 else doc,
                    "document": metadata.get('document', 'Unknown'),
                    "citation": metadata.get('citation_format', ''),
                    "relevance": "High"
                }
                sources.append(source)

        return sources[:5]
