"""
Data Models for Regulatory Guidance Documents
==============================================

Structures for managing FDA, ICH, and other regulatory guidance documents
with focus on US FDA requirements for oncology Phase 2/3 trials.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from enum import Enum
from datetime import datetime


class GuidanceAuthority(Enum):
    """Regulatory authorities"""
    FDA = "FDA"                    # US Food and Drug Administration
    ICH = "ICH"                    # International Council for Harmonisation
    EMA = "EMA"                    # European Medicines Agency
    PMDA = "PMDA"                  # Japan Pharmaceuticals and Medical Devices Agency
    NMPA = "NMPA"                  # China National Medical Products Administration
    HC = "HC"                      # Health Canada
    TGA = "TGA"                    # Australia Therapeutic Goods Administration
    MHRA = "MHRA"                  # UK Medicines and Healthcare products Regulatory Agency


class GuidanceType(Enum):
    """Guidance document types"""
    DRAFT = "draft"                # Draft guidance
    FINAL = "final"                # Final guidance
    REVISED = "revised"            # Revised guidance
    WITHDRAWN = "withdrawn"        # Withdrawn guidance


class BindingLevel(Enum):
    """How binding the guidance is"""
    REQUIRED = "required"          # Must follow (regulations)
    RECOMMENDED = "recommended"    # Should follow (guidance)
    INFORMATIONAL = "informational"  # For reference only
    DEPRECATED = "deprecated"      # No longer applicable


@dataclass
class GuidanceSection:
    """Individual section within a guidance document"""
    section_id: str                    # e.g., "3.2", "Appendix A"
    title: str
    content: str                       # Full text content
    summary: str = ""                  # Brief summary

    # Applicability filters
    applies_to_drug_classes: List[str] = field(default_factory=list)
    applies_to_conditions: List[str] = field(default_factory=list)
    applies_to_endpoint_types: List[str] = field(default_factory=list)
    applies_to_phases: List[str] = field(default_factory=list)

    # Recommendations
    recommended_methods: List[str] = field(default_factory=list)
    required_elements: List[str] = field(default_factory=list)

    # Examples from guidance
    examples: List[Dict] = field(default_factory=list)

    # Cross-references
    related_guidances: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)


@dataclass
class RegulatoryChecklist:
    """Compliance checklist derived from guidance"""
    name: str
    category: str = ""  # e.g., "SAP Content", "Endpoint Definition", "Safety Monitoring"
    items: List[str] = field(default_factory=list)
    required_items: Set[str] = field(default_factory=set)
    optional_items: Set[str] = field(default_factory=set)

    def add_required(self, item: str):
        """Add a required checklist item"""
        if item not in self.items:
            self.items.append(item)
        self.required_items.add(item)

    def add_optional(self, item: str):
        """Add an optional checklist item"""
        if item not in self.items:
            self.items.append(item)
        self.optional_items.add(item)

    def is_required(self, item: str) -> bool:
        """Check if item is required"""
        return item in self.required_items


@dataclass
class GuidanceDocument:
    """Complete regulatory guidance document"""
    # Identity
    document_id: str                   # e.g., "FDA-2018-D-3755"
    title: str
    authority: GuidanceAuthority
    guidance_type: GuidanceType
    binding_level: BindingLevel

    # Version info
    version: str = "1.0"
    effective_date: str = ""
    revision_date: Optional[str] = None
    supersedes: Optional[str] = None   # Previous version ID

    # Content
    sections: List[GuidanceSection] = field(default_factory=list)
    checklists: List[RegulatoryChecklist] = field(default_factory=list)

    # Metadata
    topics: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    url: str = ""
    pdf_path: Optional[str] = None

    # Applicability
    applies_to_regions: List[str] = field(default_factory=list)
    applies_to_product_types: List[str] = field(default_factory=list)
    applies_to_therapeutic_areas: List[str] = field(default_factory=list)

    # Classification
    category: str = ""  # e.g., "Clinical Trial Design", "Statistical Analysis", "Safety"
    subcategory: str = ""  # e.g., "Endpoint Selection", "Analysis Populations"

    def get_section(self, section_id: str) -> Optional[GuidanceSection]:
        """Get section by ID"""
        for section in self.sections:
            if section.section_id == section_id:
                return section
        return None

    def get_applicable_sections(
        self,
        drug_class: str = None,
        condition: str = None,
        endpoint_type: str = None,
        phase: str = None
    ) -> List[GuidanceSection]:
        """
        Get sections applicable to specific criteria.

        Args:
            drug_class: Drug class (e.g., "Immune checkpoint inhibitor")
            condition: Disease condition (e.g., "NSCLC")
            endpoint_type: Endpoint type (e.g., "OS", "ORR")
            phase: Trial phase (e.g., "Phase 3")

        Returns:
            List of applicable sections
        """
        applicable = []

        for section in self.sections:
            is_applicable = True

            if drug_class and section.applies_to_drug_classes:
                if drug_class not in section.applies_to_drug_classes:
                    is_applicable = False

            if condition and section.applies_to_conditions:
                if condition not in section.applies_to_conditions:
                    is_applicable = False

            if endpoint_type and section.applies_to_endpoint_types:
                if endpoint_type not in section.applies_to_endpoint_types:
                    is_applicable = False

            if phase and section.applies_to_phases:
                if phase not in section.applies_to_phases:
                    is_applicable = False

            if is_applicable:
                applicable.append(section)

        return applicable

    def search_content(self, query: str) -> List[GuidanceSection]:
        """
        Search guidance content for keyword.

        Args:
            query: Search term

        Returns:
            List of sections containing the query
        """
        query_lower = query.lower()
        matching_sections = []

        for section in self.sections:
            if (query_lower in section.title.lower() or
                query_lower in section.content.lower() or
                query_lower in section.summary.lower()):
                matching_sections.append(section)

        return matching_sections

    def get_checklist(self, name: str) -> Optional[RegulatoryChecklist]:
        """Get checklist by name"""
        for checklist in self.checklists:
            if checklist.name == name:
                return checklist
        return None

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            "document_id": self.document_id,
            "title": self.title,
            "authority": self.authority.value,
            "guidance_type": self.guidance_type.value,
            "binding_level": self.binding_level.value,
            "version": self.version,
            "effective_date": self.effective_date,
            "revision_date": self.revision_date,
            "supersedes": self.supersedes,
            "topics": self.topics,
            "keywords": self.keywords,
            "url": self.url,
            "pdf_path": self.pdf_path,
            "applies_to_regions": self.applies_to_regions,
            "applies_to_product_types": self.applies_to_product_types,
            "applies_to_therapeutic_areas": self.applies_to_therapeutic_areas,
            "category": self.category,
            "subcategory": self.subcategory,
            "num_sections": len(self.sections),
            "num_checklists": len(self.checklists),
        }


# Key FDA Guidance Document IDs (for reference)
FDA_GUIDANCE_IDS = {
    # Clinical Trial Design & Conduct
    "E9": "ICH E9 - Statistical Principles for Clinical Trials",
    "E9_R1": "ICH E9(R1) - Addendum on Estimands and Sensitivity Analysis",
    "E10": "ICH E10 - Choice of Control Group",
    "E6_R2": "ICH E6(R2) - Good Clinical Practice",

    # Oncology-Specific
    "ONCOLOGY_ENDPOINTS": "FDA-2018-D-3119 - Clinical Trial Endpoints for Approval of Cancer Drugs",
    "IMMUNO_ONCOLOGY": "FDA-2021-D-0490 - Immuno-Oncology Cancer Drugs",
    "HEMATOLOGIC": "FDA-2015-D-2441 - Hematologic Malignancies",

    # Adaptive Designs
    "ADAPTIVE_DESIGNS": "FDA-2019-D-4853 - Adaptive Designs for Clinical Trials",
    "MASTER_PROTOCOLS": "FDA-2018-D-3955 - Master Protocols: Efficient Clinical Trial Design",

    # Subgroup Analysis
    "SUBGROUP_ANALYSIS": "FDA-2014-D-1115 - Collection of Race and Ethnicity Data",

    # Missing Data
    "MISSING_DATA": "FDA-2019-N-1185 - Missing Data in Clinical Trials",

    # Statistical Analysis Plans
    "SAP_CONTENT": "FDA-2019-D-3742 - Interacting with FDA on Complex Statistical Issues",

    # Safety
    "SAFETY_ASSESSMENT": "FDA-2017-D-6014 - Safety Assessment for IND Safety Reporting",
    "QT_STUDY": "ICH E14 - Clinical Evaluation of QT/QTc Interval Prolongation",

    # Companion Diagnostics
    "COMPANION_DX": "FDA-2014-D-0870 - In Vitro Companion Diagnostic Devices",

    # Biomarkers
    "BIOMARKER_QUALIFICATION": "FDA-2018-D-0904 - Biomarker Qualification",

    # Real-World Evidence
    "RWE": "FDA-2021-D-0310 - Real-World Data: Assessing Registries",
}
