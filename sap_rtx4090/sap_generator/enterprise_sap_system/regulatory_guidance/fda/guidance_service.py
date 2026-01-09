"""
FDA Guidance Service
====================

Centralized service for accessing FDA regulatory guidance documents
for oncology Phase 2/3 clinical trials.

Provides:
- Guidance document management
- Context-sensitive guidance retrieval
- Compliance checking
- SAP generation support
"""

from typing import List, Dict, Optional, Set
from pathlib import Path
import json
import logging
from dataclasses import asdict

from ..guidance_model import (
    GuidanceDocument,
    GuidanceSection,
    GuidanceAuthority,
    GuidanceType,
    BindingLevel,
    RegulatoryChecklist,
    FDA_GUIDANCE_IDS
)

logger = logging.getLogger(__name__)


class FDAGuidanceService:
    """
    Service for managing FDA regulatory guidance documents.

    Provides context-aware guidance retrieval for SAP generation.
    """

    def __init__(self, guidance_dir: Path = None):
        """
        Initialize FDA guidance service.

        Args:
            guidance_dir: Directory containing guidance documents
        """
        self.guidance_dir = guidance_dir or (Path(__file__).parent / "data")
        self.guidance_dir.mkdir(parents=True, exist_ok=True)

        # In-memory guidance cache
        self._guidance_cache: Dict[str, GuidanceDocument] = {}
        self._loaded = False

        # Index for fast searching
        self._topic_index: Dict[str, List[str]] = {}  # topic -> document_ids
        self._keyword_index: Dict[str, List[str]] = {}  # keyword -> document_ids

    def load_guidance_library(self):
        """Load all FDA guidance documents into memory"""
        if self._loaded:
            return

        logger.info("Loading FDA guidance library...")

        # Load from JSON files if available
        guidance_files = list(self.guidance_dir.glob("*.json"))

        for file_path in guidance_files:
            try:
                doc = self._load_guidance_from_file(file_path)
                self._guidance_cache[doc.document_id] = doc
                self._index_document(doc)
            except Exception as e:
                logger.error(f"Failed to load guidance from {file_path}: {e}")

        # If no files, load embedded core guidance
        if not self._guidance_cache:
            logger.info("No guidance files found, loading embedded core guidance...")
            self._load_embedded_guidance()

        self._loaded = True
        logger.info(f"Loaded {len(self._guidance_cache)} FDA guidance documents")

    def _load_guidance_from_file(self, file_path: Path) -> GuidanceDocument:
        """Load guidance document from JSON file"""
        with open(file_path, 'r') as f:
            data = json.load(f)

        # Convert JSON to GuidanceDocument
        doc = GuidanceDocument(
            document_id=data['document_id'],
            title=data['title'],
            authority=GuidanceAuthority(data['authority']),
            guidance_type=GuidanceType(data['guidance_type']),
            binding_level=BindingLevel(data['binding_level']),
            version=data.get('version', '1.0'),
            effective_date=data.get('effective_date', ''),
            revision_date=data.get('revision_date'),
            supersedes=data.get('supersedes'),
            topics=data.get('topics', []),
            keywords=data.get('keywords', []),
            url=data.get('url', ''),
            pdf_path=data.get('pdf_path'),
            applies_to_regions=data.get('applies_to_regions', []),
            applies_to_product_types=data.get('applies_to_product_types', []),
            applies_to_therapeutic_areas=data.get('applies_to_therapeutic_areas', []),
            category=data.get('category', ''),
            subcategory=data.get('subcategory', ''),
        )

        # Load sections
        for section_data in data.get('sections', []):
            section = GuidanceSection(
                section_id=section_data['section_id'],
                title=section_data['title'],
                content=section_data['content'],
                summary=section_data.get('summary', ''),
                applies_to_drug_classes=section_data.get('applies_to_drug_classes', []),
                applies_to_conditions=section_data.get('applies_to_conditions', []),
                applies_to_endpoint_types=section_data.get('applies_to_endpoint_types', []),
                applies_to_phases=section_data.get('applies_to_phases', []),
                recommended_methods=section_data.get('recommended_methods', []),
                required_elements=section_data.get('required_elements', []),
                examples=section_data.get('examples', []),
                related_guidances=section_data.get('related_guidances', []),
                references=section_data.get('references', []),
            )
            doc.sections.append(section)

        # Load checklists
        for checklist_data in data.get('checklists', []):
            checklist = RegulatoryChecklist(
                name=checklist_data['name'],
                category=checklist_data.get('category', ''),
                items=checklist_data.get('items', []),
                required_items=set(checklist_data.get('required_items', [])),
                optional_items=set(checklist_data.get('optional_items', [])),
            )
            doc.checklists.append(checklist)

        return doc

    def _load_embedded_guidance(self):
        """Load embedded core FDA guidance for oncology trials"""
        # Load key guidance documents with essential content
        # This provides baseline functionality even without external files

        # 1. FDA Oncology Endpoints Guidance
        endpoints_doc = self._create_oncology_endpoints_guidance()
        self._guidance_cache[endpoints_doc.document_id] = endpoints_doc
        self._index_document(endpoints_doc)

        # 2. ICH E9 Statistical Principles
        e9_doc = self._create_ich_e9_guidance()
        self._guidance_cache[e9_doc.document_id] = e9_doc
        self._index_document(e9_doc)

        # 3. ICH E9(R1) Estimands
        e9r1_doc = self._create_ich_e9r1_guidance()
        self._guidance_cache[e9r1_doc.document_id] = e9r1_doc
        self._index_document(e9r1_doc)

        logger.info("Loaded embedded core guidance documents")

    def _create_oncology_endpoints_guidance(self) -> GuidanceDocument:
        """Create FDA oncology endpoints guidance document"""
        doc = GuidanceDocument(
            document_id="FDA-2018-D-3119",
            title="Clinical Trial Endpoints for the Approval of Cancer Drugs and Biologics",
            authority=GuidanceAuthority.FDA,
            guidance_type=GuidanceType.FINAL,
            binding_level=BindingLevel.RECOMMENDED,
            version="Final (December 2018)",
            effective_date="2018-12",
            topics=["oncology", "endpoints", "clinical trial design"],
            keywords=["overall survival", "progression-free survival", "response rate", "duration of response"],
            url="https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-trial-endpoints-approval-cancer-drugs-and-biologics",
            applies_to_regions=["United States"],
            applies_to_product_types=["Cancer drugs", "Biologics"],
            applies_to_therapeutic_areas=["oncology"],
            category="Clinical Trial Design",
            subcategory="Endpoint Selection",
        )

        # Add sections
        doc.sections.append(GuidanceSection(
            section_id="III.A",
            title="Overall Survival (OS)",
            content="""Overall survival is defined as the time from randomization until death from any cause, and is measured in the intent-to-treat population. OS is considered the most reliable cancer endpoint and is rarely subject to assessment bias.""",
            summary="OS is the gold standard endpoint for cancer trials",
            applies_to_endpoint_types=["OS"],
            applies_to_phases=["Phase 3"],
            recommended_methods=["Kaplan-Meier analysis", "Log-rank test", "Cox proportional hazards model"],
            required_elements=["Intent-to-treat population", "All-cause mortality", "Time from randomization"],
        ))

        doc.sections.append(GuidanceSection(
            section_id="III.B",
            title="Progression-Free Survival (PFS)",
            content="""Progression-free survival is defined as the time from randomization until objective tumor progression or death. PFS is based on objective assessment of tumor status and is commonly used as a primary endpoint in Phase 3 cancer trials.""",
            summary="PFS is widely accepted for regulatory approval",
            applies_to_endpoint_types=["PFS"],
            applies_to_phases=["Phase 2", "Phase 3"],
            recommended_methods=["Blinded independent central review", "RECIST 1.1 criteria"],
            required_elements=["Objective tumor assessments", "Scheduled imaging", "Clear progression criteria"],
        ))

        doc.sections.append(GuidanceSection(
            section_id="III.C",
            title="Objective Response Rate (ORR)",
            content="""Objective response rate is the proportion of patients with tumor size reduction of a predefined amount and for a minimum time period. ORR is a direct measure of drug antitumor activity and can be assessed in a single-arm trial.""",
            summary="ORR can support accelerated approval",
            applies_to_endpoint_types=["ORR"],
            applies_to_phases=["Phase 2"],
            recommended_methods=["RECIST 1.1", "Independent review committee"],
            required_elements=["Confirmed response", "Minimum duration requirement"],
        ))

        # Add checklist
        sap_checklist = RegulatoryChecklist(name="SAP Endpoint Requirements", category="Endpoint Definition")
        sap_checklist.add_required("Define endpoint precisely")
        sap_checklist.add_required("Specify measurement schedule")
        sap_checklist.add_required("Define censoring rules")
        sap_checklist.add_required("Specify assessment criteria (e.g., RECIST)")
        sap_checklist.add_optional("Describe sensitivity analyses")
        doc.checklists.append(sap_checklist)

        return doc

    def _create_ich_e9_guidance(self) -> GuidanceDocument:
        """Create ICH E9 statistical principles guidance"""
        doc = GuidanceDocument(
            document_id="ICH-E9",
            title="Statistical Principles for Clinical Trials",
            authority=GuidanceAuthority.ICH,
            guidance_type=GuidanceType.FINAL,
            binding_level=BindingLevel.RECOMMENDED,
            version="E9 (1998)",
            effective_date="1998-02",
            topics=["statistical analysis", "trial design", "analysis populations"],
            keywords=["type I error", "multiplicity", "interim analysis", "missing data"],
            url="https://www.ich.org/page/efficacy-guidelines",
            applies_to_regions=["United States", "Europe", "Japan"],
            applies_to_product_types=["All drug products"],
            category="Statistical Analysis",
            subcategory="General Principles",
        )

        # Add key sections
        doc.sections.append(GuidanceSection(
            section_id="5.1",
            title="Type I Error and Significance Level",
            content="""The significance level (alpha) should be defined in advance. For superiority trials, a two-sided significance level of 0.05 is conventional.""",
            summary="Define alpha and control Type I error",
            recommended_methods=["Two-sided testing at alpha=0.05"],
            required_elements=["Pre-specified alpha level", "Control of Type I error"],
        ))

        doc.sections.append(GuidanceSection(
            section_id="5.5",
            title="Adjustment for Multiplicity",
            content="""When multiple primary endpoints are analyzed, appropriate adjustments should be made to preserve the overall Type I error rate.""",
            summary="Control familywise error rate in multiple testing",
            recommended_methods=["Bonferroni", "Hochberg", "Holm", "Hierarchical testing"],
            required_elements=["Multiplicity adjustment method", "Justification for approach"],
        ))

        return doc

    def _create_ich_e9r1_guidance(self) -> GuidanceDocument:
        """Create ICH E9(R1) estimands guidance"""
        doc = GuidanceDocument(
            document_id="ICH-E9-R1",
            title="Addendum on Estimands and Sensitivity Analysis in Clinical Trials",
            authority=GuidanceAuthority.ICH,
            guidance_type=GuidanceType.FINAL,
            binding_level=BindingLevel.RECOMMENDED,
            version="E9(R1) (2019)",
            effective_date="2019-11",
            topics=["estimands", "intercurrent events", "sensitivity analysis"],
            keywords=["estimand", "intercurrent event", "treatment policy", "composite strategy"],
            url="https://www.ich.org/page/efficacy-guidelines",
            applies_to_regions=["United States", "Europe", "Japan"],
            applies_to_product_types=["All drug products"],
            category="Statistical Analysis",
            subcategory="Estimands",
        )

        # Add estimand section
        doc.sections.append(GuidanceSection(
            section_id="2.1",
            title="Estimand Framework",
            content="""An estimand precisely describes the treatment effect to be estimated. It includes: population, variable, population-level summary, and how intercurrent events are handled.""",
            summary="Define estimands with all five attributes",
            required_elements=["Treatment", "Population", "Variable", "Population-level summary", "Intercurrent events handling"],
        ))

        return doc

    def _index_document(self, doc: GuidanceDocument):
        """Index document for fast searching"""
        # Index by topics
        for topic in doc.topics:
            if topic not in self._topic_index:
                self._topic_index[topic] = []
            self._topic_index[topic].append(doc.document_id)

        # Index by keywords
        for keyword in doc.keywords:
            if keyword not in self._keyword_index:
                self._keyword_index[keyword] = []
            self._keyword_index[keyword].append(doc.document_id)

    def get_guidance(self, document_id: str) -> Optional[GuidanceDocument]:
        """
        Get guidance document by ID.

        Args:
            document_id: Document identifier

        Returns:
            GuidanceDocument or None
        """
        if not self._loaded:
            self.load_guidance_library()

        return self._guidance_cache.get(document_id)

    def search_by_topic(self, topic: str) -> List[GuidanceDocument]:
        """
        Search guidance documents by topic.

        Args:
            topic: Topic name (e.g., "oncology", "endpoints")

        Returns:
            List of matching guidance documents
        """
        if not self._loaded:
            self.load_guidance_library()

        topic_lower = topic.lower()
        matching_docs = []

        for doc_id, doc in self._guidance_cache.items():
            if any(topic_lower in t.lower() for t in doc.topics):
                matching_docs.append(doc)

        return matching_docs

    def search_by_keyword(self, keyword: str) -> List[GuidanceDocument]:
        """
        Search guidance documents by keyword.

        Args:
            keyword: Keyword (e.g., "overall survival", "multiplicity")

        Returns:
            List of matching guidance documents
        """
        if not self._loaded:
            self.load_guidance_library()

        keyword_lower = keyword.lower()
        matching_docs = []

        for doc_id, doc in self._guidance_cache.items():
            if any(keyword_lower in k.lower() for k in doc.keywords):
                matching_docs.append(doc)

        return matching_docs

    def get_relevant_guidance(
        self,
        therapeutic_area: str = None,
        endpoint_type: str = None,
        phase: str = None,
        drug_class: str = None
    ) -> List[GuidanceDocument]:
        """
        Get guidance documents relevant to trial context.

        Args:
            therapeutic_area: Therapeutic area (e.g., "oncology")
            endpoint_type: Endpoint type (e.g., "OS", "PFS")
            phase: Trial phase (e.g., "Phase 3")
            drug_class: Drug class (e.g., "checkpoint inhibitor")

        Returns:
            List of relevant guidance documents
        """
        if not self._loaded:
            self.load_guidance_library()

        relevant_docs = []

        for doc_id, doc in self._guidance_cache.items():
            is_relevant = False

            # Check therapeutic area
            if therapeutic_area:
                if therapeutic_area.lower() in [ta.lower() for ta in doc.applies_to_therapeutic_areas]:
                    is_relevant = True

            # Check if any section applies
            if endpoint_type or phase or drug_class:
                applicable_sections = doc.get_applicable_sections(
                    drug_class=drug_class,
                    endpoint_type=endpoint_type,
                    phase=phase
                )
                if applicable_sections:
                    is_relevant = True

            if is_relevant:
                relevant_docs.append(doc)

        return relevant_docs

    def get_sap_guidance(self) -> List[GuidanceDocument]:
        """
        Get guidance documents specifically relevant to SAP writing.

        Returns:
            List of SAP-relevant guidance documents
        """
        sap_topics = ["statistical analysis", "estimands", "missing data", "multiplicity"]

        sap_docs = []
        for topic in sap_topics:
            sap_docs.extend(self.search_by_topic(topic))

        # Remove duplicates
        unique_docs = {doc.document_id: doc for doc in sap_docs}
        return list(unique_docs.values())

    def export_guidance_summary(self, output_path: Path):
        """
        Export summary of all guidance documents.

        Args:
            output_path: Path for JSON export
        """
        if not self._loaded:
            self.load_guidance_library()

        summary = {
            "total_documents": len(self._guidance_cache),
            "documents": [doc.to_dict() for doc in self._guidance_cache.values()]
        }

        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2)

        logger.info(f"Exported guidance summary to {output_path}")


# Singleton instance
_fda_guidance_service: Optional[FDAGuidanceService] = None


def get_fda_guidance_service(guidance_dir: Path = None) -> FDAGuidanceService:
    """
    Get singleton FDA guidance service instance.

    Args:
        guidance_dir: Optional guidance directory

    Returns:
        FDAGuidanceService instance
    """
    global _fda_guidance_service

    if _fda_guidance_service is None:
        _fda_guidance_service = FDAGuidanceService(guidance_dir=guidance_dir)
        _fda_guidance_service.load_guidance_library()

    return _fda_guidance_service
