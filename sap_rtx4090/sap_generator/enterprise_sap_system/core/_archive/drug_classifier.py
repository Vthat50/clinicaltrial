#!/usr/bin/env python3
"""
Drug Classifier with Ontology Integration
==========================================

Tiered approach to drug classification:
1. LOCAL CACHE: 500+ common oncology drugs (instant)
2. NCI THESAURUS API: 15,000+ drugs (200-500ms)
3. LLM FALLBACK: Novel drugs with lower confidence

References:
- NCI Thesaurus: https://ncithesaurus.nci.nih.gov/
- EVS API: https://api-evsrest.nci.nih.gov/
"""

import re
import json
import sqlite3
import requests
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum


# =============================================================================
# DATA CLASSES
# =============================================================================

class DrugClass(Enum):
    """Standard drug classifications for oncology."""
    IMMUNOTHERAPY = "immunotherapy"
    CHEMOTHERAPY = "chemotherapy"
    TARGETED_THERAPY = "targeted_therapy"
    HORMONE_THERAPY = "hormone_therapy"
    ANTIBODY_DRUG_CONJUGATE = "antibody_drug_conjugate"
    CELL_THERAPY = "cell_therapy"
    RADIOTHERAPY = "radiotherapy"
    SUPPORTIVE_CARE = "supportive_care"
    UNKNOWN = "unknown"


class DrugMechanism(Enum):
    """Drug mechanisms relevant to statistical method selection."""
    PD1_INHIBITOR = "PD-1 inhibitor"
    PDL1_INHIBITOR = "PD-L1 inhibitor"
    CTLA4_INHIBITOR = "CTLA-4 inhibitor"
    EGFR_INHIBITOR = "EGFR inhibitor"
    ALK_INHIBITOR = "ALK inhibitor"
    HER2_INHIBITOR = "HER2 inhibitor"
    VEGF_INHIBITOR = "VEGF inhibitor"
    PARP_INHIBITOR = "PARP inhibitor"
    BTK_INHIBITOR = "BTK inhibitor"
    CDK_INHIBITOR = "CDK4/6 inhibitor"
    BRAF_INHIBITOR = "BRAF inhibitor"
    MEK_INHIBITOR = "MEK inhibitor"
    BCL2_INHIBITOR = "BCL-2 inhibitor"
    PI3K_INHIBITOR = "PI3K inhibitor"
    MTOR_INHIBITOR = "mTOR inhibitor"
    JAK_INHIBITOR = "JAK inhibitor"
    FLT3_INHIBITOR = "FLT3 inhibitor"
    IDH_INHIBITOR = "IDH inhibitor"
    KRAS_INHIBITOR = "KRAS inhibitor"
    CAR_T = "CAR-T cell therapy"
    BISPECIFIC_ANTIBODY = "bispecific antibody"
    ALKYLATING_AGENT = "alkylating agent"
    ANTIMETABOLITE = "antimetabolite"
    TAXANE = "taxane"
    PLATINUM = "platinum compound"
    TOPOISOMERASE_INHIBITOR = "topoisomerase inhibitor"
    UNKNOWN = "unknown"


@dataclass
class DrugClassification:
    """
    Complete drug classification result.

    This feeds into the Knowledge Graph for method selection:
    - immunotherapy → Fleming-Harrington test (delayed effect)
    - chemotherapy → standard log-rank test
    - targeted_therapy → depends on mechanism
    """
    drug_name: str
    drug_class: str  # From DrugClass enum
    mechanism: str   # From DrugMechanism enum
    targets: List[str] = field(default_factory=list)
    synonyms: List[str] = field(default_factory=list)

    # Statistical implications
    expects_delayed_effect: bool = False  # Key for method selection
    expects_non_proportional_hazards: bool = False

    # Confidence and source tracking
    confidence: float = 1.0  # 0.0 to 1.0
    source: str = "cache"    # "cache", "nci_thesaurus", "llm_inference"
    requires_review: bool = False

    # Metadata
    nci_code: Optional[str] = None  # e.g., "C68814" for nivolumab
    last_updated: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


# =============================================================================
# LOCAL DRUG CACHE
# =============================================================================

# Pre-loaded common oncology drugs with full classification
# This is the "instant" tier - <1ms lookup

ONCOLOGY_DRUG_CACHE: Dict[str, DrugClassification] = {
    # ==========================================================================
    # PD-1 INHIBITORS (Immunotherapy - expect delayed effect)
    # ==========================================================================
    "nivolumab": DrugClassification(
        drug_name="nivolumab",
        drug_class=DrugClass.IMMUNOTHERAPY.value,
        mechanism=DrugMechanism.PD1_INHIBITOR.value,
        targets=["PD-1"],
        synonyms=["opdivo", "bms-936558", "ono-4538"],
        expects_delayed_effect=True,
        expects_non_proportional_hazards=True,
        confidence=1.0,
        source="cache",
        nci_code="C68814"
    ),
    "pembrolizumab": DrugClassification(
        drug_name="pembrolizumab",
        drug_class=DrugClass.IMMUNOTHERAPY.value,
        mechanism=DrugMechanism.PD1_INHIBITOR.value,
        targets=["PD-1"],
        synonyms=["keytruda", "mk-3475", "lambrolizumab"],
        expects_delayed_effect=True,
        expects_non_proportional_hazards=True,
        confidence=1.0,
        source="cache",
        nci_code="C106432"
    ),
    "cemiplimab": DrugClassification(
        drug_name="cemiplimab",
        drug_class=DrugClass.IMMUNOTHERAPY.value,
        mechanism=DrugMechanism.PD1_INHIBITOR.value,
        targets=["PD-1"],
        synonyms=["libtayo", "regn2810"],
        expects_delayed_effect=True,
        expects_non_proportional_hazards=True,
        confidence=1.0,
        source="cache",
        nci_code="C150378"
    ),
    "dostarlimab": DrugClassification(
        drug_name="dostarlimab",
        drug_class=DrugClass.IMMUNOTHERAPY.value,
        mechanism=DrugMechanism.PD1_INHIBITOR.value,
        targets=["PD-1"],
        synonyms=["jemperli", "gsk4057190", "tsr-042"],
        expects_delayed_effect=True,
        expects_non_proportional_hazards=True,
        confidence=1.0,
        source="cache",
        nci_code="C150376"
    ),
    "retifanlimab": DrugClassification(
        drug_name="retifanlimab",
        drug_class=DrugClass.IMMUNOTHERAPY.value,
        mechanism=DrugMechanism.PD1_INHIBITOR.value,
        targets=["PD-1"],
        synonyms=["zynyz", "incmga00012", "mg00012"],
        expects_delayed_effect=True,
        expects_non_proportional_hazards=True,
        confidence=1.0,
        source="cache",
        nci_code="C173522"
    ),
    "tislelizumab": DrugClassification(
        drug_name="tislelizumab",
        drug_class=DrugClass.IMMUNOTHERAPY.value,
        mechanism=DrugMechanism.PD1_INHIBITOR.value,
        targets=["PD-1"],
        synonyms=["tevimbra", "bgb-a317"],
        expects_delayed_effect=True,
        expects_non_proportional_hazards=True,
        confidence=1.0,
        source="cache",
        nci_code="C132287"
    ),
    "sintilimab": DrugClassification(
        drug_name="sintilimab",
        drug_class=DrugClass.IMMUNOTHERAPY.value,
        mechanism=DrugMechanism.PD1_INHIBITOR.value,
        targets=["PD-1"],
        synonyms=["tyvyt", "ibi308"],
        expects_delayed_effect=True,
        expects_non_proportional_hazards=True,
        confidence=1.0,
        source="cache",
        nci_code="C147089"
    ),
    "camrelizumab": DrugClassification(
        drug_name="camrelizumab",
        drug_class=DrugClass.IMMUNOTHERAPY.value,
        mechanism=DrugMechanism.PD1_INHIBITOR.value,
        targets=["PD-1"],
        synonyms=["shr-1210", "airuika"],
        expects_delayed_effect=True,
        expects_non_proportional_hazards=True,
        confidence=1.0,
        source="cache",
        nci_code="C147055"
    ),
    "toripalimab": DrugClassification(
        drug_name="toripalimab",
        drug_class=DrugClass.IMMUNOTHERAPY.value,
        mechanism=DrugMechanism.PD1_INHIBITOR.value,
        targets=["PD-1"],
        synonyms=["loqtorzi", "js001", "tab001"],
        expects_delayed_effect=True,
        expects_non_proportional_hazards=True,
        confidence=1.0,
        source="cache",
        nci_code="C147091"
    ),
    "zimberelimab": DrugClassification(
        drug_name="zimberelimab",
        drug_class=DrugClass.IMMUNOTHERAPY.value,
        mechanism=DrugMechanism.PD1_INHIBITOR.value,
        targets=["PD-1"],
        synonyms=["ab122", "gls-010"],
        expects_delayed_effect=True,
        expects_non_proportional_hazards=True,
        confidence=1.0,
        source="cache",
        nci_code="C168584"
    ),

    # ==========================================================================
    # PD-L1 INHIBITORS (Immunotherapy - expect delayed effect)
    # ==========================================================================
    "atezolizumab": DrugClassification(
        drug_name="atezolizumab",
        drug_class=DrugClass.IMMUNOTHERAPY.value,
        mechanism=DrugMechanism.PDL1_INHIBITOR.value,
        targets=["PD-L1"],
        synonyms=["tecentriq", "mpdl3280a", "rg7446"],
        expects_delayed_effect=True,
        expects_non_proportional_hazards=True,
        confidence=1.0,
        source="cache",
        nci_code="C106250"
    ),
    "durvalumab": DrugClassification(
        drug_name="durvalumab",
        drug_class=DrugClass.IMMUNOTHERAPY.value,
        mechanism=DrugMechanism.PDL1_INHIBITOR.value,
        targets=["PD-L1"],
        synonyms=["imfinzi", "medi4736"],
        expects_delayed_effect=True,
        expects_non_proportional_hazards=True,
        confidence=1.0,
        source="cache",
        nci_code="C107676"
    ),
    "avelumab": DrugClassification(
        drug_name="avelumab",
        drug_class=DrugClass.IMMUNOTHERAPY.value,
        mechanism=DrugMechanism.PDL1_INHIBITOR.value,
        targets=["PD-L1"],
        synonyms=["bavencio", "msb0010718c"],
        expects_delayed_effect=True,
        expects_non_proportional_hazards=True,
        confidence=1.0,
        source="cache",
        nci_code="C116870"
    ),

    # ==========================================================================
    # CTLA-4 INHIBITORS (Immunotherapy - expect delayed effect)
    # ==========================================================================
    "ipilimumab": DrugClassification(
        drug_name="ipilimumab",
        drug_class=DrugClass.IMMUNOTHERAPY.value,
        mechanism=DrugMechanism.CTLA4_INHIBITOR.value,
        targets=["CTLA-4"],
        synonyms=["yervoy", "mdx-010", "bms-734016"],
        expects_delayed_effect=True,
        expects_non_proportional_hazards=True,
        confidence=1.0,
        source="cache",
        nci_code="C71709"
    ),
    "tremelimumab": DrugClassification(
        drug_name="tremelimumab",
        drug_class=DrugClass.IMMUNOTHERAPY.value,
        mechanism=DrugMechanism.CTLA4_INHIBITOR.value,
        targets=["CTLA-4"],
        synonyms=["imjudo", "cp-675206", "ticilimumab"],
        expects_delayed_effect=True,
        expects_non_proportional_hazards=True,
        confidence=1.0,
        source="cache",
        nci_code="C77894"
    ),

    # ==========================================================================
    # CHEMOTHERAPY - Taxanes (Standard survival curves)
    # ==========================================================================
    "docetaxel": DrugClassification(
        drug_name="docetaxel",
        drug_class=DrugClass.CHEMOTHERAPY.value,
        mechanism=DrugMechanism.TAXANE.value,
        targets=["microtubules"],
        synonyms=["taxotere", "rp56976"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C1526"
    ),
    "paclitaxel": DrugClassification(
        drug_name="paclitaxel",
        drug_class=DrugClass.CHEMOTHERAPY.value,
        mechanism=DrugMechanism.TAXANE.value,
        targets=["microtubules"],
        synonyms=["taxol", "abraxane", "nab-paclitaxel"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C1411"
    ),
    "cabazitaxel": DrugClassification(
        drug_name="cabazitaxel",
        drug_class=DrugClass.CHEMOTHERAPY.value,
        mechanism=DrugMechanism.TAXANE.value,
        targets=["microtubules"],
        synonyms=["jevtana", "xrp6258", "txd258"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C62528"
    ),

    # ==========================================================================
    # CHEMOTHERAPY - Platinum compounds
    # ==========================================================================
    "cisplatin": DrugClassification(
        drug_name="cisplatin",
        drug_class=DrugClass.CHEMOTHERAPY.value,
        mechanism=DrugMechanism.PLATINUM.value,
        targets=["DNA"],
        synonyms=["platinol", "cddp", "cis-diamminedichloroplatinum"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C376"
    ),
    "carboplatin": DrugClassification(
        drug_name="carboplatin",
        drug_class=DrugClass.CHEMOTHERAPY.value,
        mechanism=DrugMechanism.PLATINUM.value,
        targets=["DNA"],
        synonyms=["paraplatin", "cbdca", "jm8"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C1282"
    ),
    "oxaliplatin": DrugClassification(
        drug_name="oxaliplatin",
        drug_class=DrugClass.CHEMOTHERAPY.value,
        mechanism=DrugMechanism.PLATINUM.value,
        targets=["DNA"],
        synonyms=["eloxatin", "l-ohp"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C1181"
    ),

    # ==========================================================================
    # TARGETED THERAPY - EGFR inhibitors
    # ==========================================================================
    "osimertinib": DrugClassification(
        drug_name="osimertinib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.EGFR_INHIBITOR.value,
        targets=["EGFR", "EGFR T790M"],
        synonyms=["tagrisso", "azd9291"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C113755"
    ),
    "erlotinib": DrugClassification(
        drug_name="erlotinib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.EGFR_INHIBITOR.value,
        targets=["EGFR"],
        synonyms=["tarceva", "osi-774", "cp-358774"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C65530"
    ),
    "gefitinib": DrugClassification(
        drug_name="gefitinib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.EGFR_INHIBITOR.value,
        targets=["EGFR"],
        synonyms=["iressa", "zd1839"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C1855"
    ),
    "afatinib": DrugClassification(
        drug_name="afatinib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.EGFR_INHIBITOR.value,
        targets=["EGFR", "HER2", "HER4"],
        synonyms=["gilotrif", "bibw 2992"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C66939"
    ),

    # ==========================================================================
    # TARGETED THERAPY - ALK inhibitors
    # ==========================================================================
    "alectinib": DrugClassification(
        drug_name="alectinib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.ALK_INHIBITOR.value,
        targets=["ALK", "RET"],
        synonyms=["alecensa", "ch5424802", "ro5424802"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C101790"
    ),
    "crizotinib": DrugClassification(
        drug_name="crizotinib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.ALK_INHIBITOR.value,
        targets=["ALK", "ROS1", "MET"],
        synonyms=["xalkori", "pf-02341066"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C74061"
    ),
    "lorlatinib": DrugClassification(
        drug_name="lorlatinib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.ALK_INHIBITOR.value,
        targets=["ALK", "ROS1"],
        synonyms=["lorbrena", "pf-06463922"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C116073"
    ),
    "brigatinib": DrugClassification(
        drug_name="brigatinib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.ALK_INHIBITOR.value,
        targets=["ALK", "EGFR"],
        synonyms=["alunbrig", "ap26113"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C98831"
    ),

    # ==========================================================================
    # TARGETED THERAPY - PARP inhibitors
    # ==========================================================================
    "olaparib": DrugClassification(
        drug_name="olaparib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.PARP_INHIBITOR.value,
        targets=["PARP1", "PARP2"],
        synonyms=["lynparza", "azd2281", "ku-0059436"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C71719"
    ),
    "niraparib": DrugClassification(
        drug_name="niraparib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.PARP_INHIBITOR.value,
        targets=["PARP1", "PARP2"],
        synonyms=["zejula", "mk-4827"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C95773"
    ),
    "rucaparib": DrugClassification(
        drug_name="rucaparib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.PARP_INHIBITOR.value,
        targets=["PARP1", "PARP2", "PARP3"],
        synonyms=["rubraca", "ag-014699", "co-338", "pf-01367338"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C95766"
    ),
    "talazoparib": DrugClassification(
        drug_name="talazoparib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.PARP_INHIBITOR.value,
        targets=["PARP1", "PARP2"],
        synonyms=["talzenna", "bmn 673", "mdv3800"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C95770"
    ),

    # ==========================================================================
    # TARGETED THERAPY - HER2 inhibitors
    # ==========================================================================
    "trastuzumab": DrugClassification(
        drug_name="trastuzumab",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.HER2_INHIBITOR.value,
        targets=["HER2"],
        synonyms=["herceptin", "rhumab her2"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C1647"
    ),
    "pertuzumab": DrugClassification(
        drug_name="pertuzumab",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.HER2_INHIBITOR.value,
        targets=["HER2"],
        synonyms=["perjeta", "omnitarg", "rg1273", "2c4"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C38692"
    ),
    "tucatinib": DrugClassification(
        drug_name="tucatinib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.HER2_INHIBITOR.value,
        targets=["HER2"],
        synonyms=["tukysa", "oni-534", "arry-380", "irbinitinib"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C116722"
    ),

    # ==========================================================================
    # ANTIBODY-DRUG CONJUGATES (ADCs)
    # ==========================================================================
    "trastuzumab deruxtecan": DrugClassification(
        drug_name="trastuzumab deruxtecan",
        drug_class=DrugClass.ANTIBODY_DRUG_CONJUGATE.value,
        mechanism=DrugMechanism.HER2_INHIBITOR.value,
        targets=["HER2"],
        synonyms=["enhertu", "ds-8201a", "t-dxd", "fam-trastuzumab deruxtecan"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C150504"
    ),
    "sacituzumab govitecan": DrugClassification(
        drug_name="sacituzumab govitecan",
        drug_class=DrugClass.ANTIBODY_DRUG_CONJUGATE.value,
        mechanism="TROP-2 ADC",
        targets=["TROP-2"],
        synonyms=["trodelvy", "immu-132"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C124658"
    ),
    "enfortumab vedotin": DrugClassification(
        drug_name="enfortumab vedotin",
        drug_class=DrugClass.ANTIBODY_DRUG_CONJUGATE.value,
        mechanism="Nectin-4 ADC",
        targets=["Nectin-4"],
        synonyms=["padcev", "agc-22m6e", "asv-22m6"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C124650"
    ),

    # ==========================================================================
    # TARGETED THERAPY - VEGF/Angiogenesis inhibitors
    # ==========================================================================
    "bevacizumab": DrugClassification(
        drug_name="bevacizumab",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.VEGF_INHIBITOR.value,
        targets=["VEGF-A"],
        synonyms=["avastin", "rhumab-vegf"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C2039"
    ),
    "ramucirumab": DrugClassification(
        drug_name="ramucirumab",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.VEGF_INHIBITOR.value,
        targets=["VEGFR-2"],
        synonyms=["cyramza", "imc-1121b", "ly3009806"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C68873"
    ),
    "sunitinib": DrugClassification(
        drug_name="sunitinib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.VEGF_INHIBITOR.value,
        targets=["VEGFR", "PDGFR", "KIT", "FLT3"],
        synonyms=["sutent", "su11248"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C61948"
    ),
    "sorafenib": DrugClassification(
        drug_name="sorafenib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.VEGF_INHIBITOR.value,
        targets=["VEGFR", "PDGFR", "RAF"],
        synonyms=["nexavar", "bay 43-9006"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C61924"
    ),
    "lenvatinib": DrugClassification(
        drug_name="lenvatinib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.VEGF_INHIBITOR.value,
        targets=["VEGFR", "FGFR", "RET", "KIT", "PDGFR"],
        synonyms=["lenvima", "e7080"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C77889"
    ),
    "cabozantinib": DrugClassification(
        drug_name="cabozantinib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.VEGF_INHIBITOR.value,
        targets=["VEGFR", "MET", "AXL", "RET"],
        synonyms=["cabometyx", "cometriq", "xl184"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C74053"
    ),
    "axitinib": DrugClassification(
        drug_name="axitinib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.VEGF_INHIBITOR.value,
        targets=["VEGFR-1", "VEGFR-2", "VEGFR-3"],
        synonyms=["inlyta", "ag-013736"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C62590"
    ),

    # ==========================================================================
    # CDK4/6 INHIBITORS
    # ==========================================================================
    "palbociclib": DrugClassification(
        drug_name="palbociclib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.CDK_INHIBITOR.value,
        targets=["CDK4", "CDK6"],
        synonyms=["ibrance", "pd-0332991"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C95715"
    ),
    "ribociclib": DrugClassification(
        drug_name="ribociclib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.CDK_INHIBITOR.value,
        targets=["CDK4", "CDK6"],
        synonyms=["kisqali", "lee011"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C97661"
    ),
    "abemaciclib": DrugClassification(
        drug_name="abemaciclib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.CDK_INHIBITOR.value,
        targets=["CDK4", "CDK6"],
        synonyms=["verzenio", "ly2835219"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C97659"
    ),

    # ==========================================================================
    # BRAF/MEK INHIBITORS
    # ==========================================================================
    "vemurafenib": DrugClassification(
        drug_name="vemurafenib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.BRAF_INHIBITOR.value,
        targets=["BRAF V600E"],
        synonyms=["zelboraf", "plx4032", "rg7204"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C64768"
    ),
    "dabrafenib": DrugClassification(
        drug_name="dabrafenib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.BRAF_INHIBITOR.value,
        targets=["BRAF V600E", "BRAF V600K"],
        synonyms=["tafinlar", "gsk2118436"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C82386"
    ),
    "encorafenib": DrugClassification(
        drug_name="encorafenib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.BRAF_INHIBITOR.value,
        targets=["BRAF"],
        synonyms=["braftovi", "lgx818"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C98283"
    ),
    "trametinib": DrugClassification(
        drug_name="trametinib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.MEK_INHIBITOR.value,
        targets=["MEK1", "MEK2"],
        synonyms=["mekinist", "gsk1120212", "jtp-74057"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C77908"
    ),
    "cobimetinib": DrugClassification(
        drug_name="cobimetinib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.MEK_INHIBITOR.value,
        targets=["MEK1", "MEK2"],
        synonyms=["cotellic", "gdc-0973", "xl518"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C68923"
    ),
    "binimetinib": DrugClassification(
        drug_name="binimetinib",
        drug_class=DrugClass.TARGETED_THERAPY.value,
        mechanism=DrugMechanism.MEK_INHIBITOR.value,
        targets=["MEK1", "MEK2"],
        synonyms=["mektovi", "mek162", "arry-162"],
        expects_delayed_effect=False,
        expects_non_proportional_hazards=False,
        confidence=1.0,
        source="cache",
        nci_code="C84865"
    ),

    # ==========================================================================
    # BISPECIFIC ANTIBODIES (may have unique PK/PD)
    # ==========================================================================
    "blinatumomab": DrugClassification(
        drug_name="blinatumomab",
        drug_class=DrugClass.IMMUNOTHERAPY.value,
        mechanism=DrugMechanism.BISPECIFIC_ANTIBODY.value,
        targets=["CD19", "CD3"],
        synonyms=["blincyto", "mt103", "amg 103"],
        expects_delayed_effect=True,
        expects_non_proportional_hazards=True,
        confidence=1.0,
        source="cache",
        nci_code="C71718"
    ),
    "teclistamab": DrugClassification(
        drug_name="teclistamab",
        drug_class=DrugClass.IMMUNOTHERAPY.value,
        mechanism=DrugMechanism.BISPECIFIC_ANTIBODY.value,
        targets=["BCMA", "CD3"],
        synonyms=["tecvayli", "jnj-64007957"],
        expects_delayed_effect=True,
        expects_non_proportional_hazards=True,
        confidence=1.0,
        source="cache",
        nci_code="C162588"
    ),

    # ==========================================================================
    # CAR-T CELL THERAPIES (Immunotherapy - delayed effect)
    # ==========================================================================
    "axicabtagene ciloleucel": DrugClassification(
        drug_name="axicabtagene ciloleucel",
        drug_class=DrugClass.CELL_THERAPY.value,
        mechanism=DrugMechanism.CAR_T.value,
        targets=["CD19"],
        synonyms=["yescarta", "axi-cel", "kte-c19"],
        expects_delayed_effect=True,
        expects_non_proportional_hazards=True,
        confidence=1.0,
        source="cache",
        nci_code="C131448"
    ),
    "tisagenlecleucel": DrugClassification(
        drug_name="tisagenlecleucel",
        drug_class=DrugClass.CELL_THERAPY.value,
        mechanism=DrugMechanism.CAR_T.value,
        targets=["CD19"],
        synonyms=["kymriah", "ctl019"],
        expects_delayed_effect=True,
        expects_non_proportional_hazards=True,
        confidence=1.0,
        source="cache",
        nci_code="C125193"
    ),
    "brexucabtagene autoleucel": DrugClassification(
        drug_name="brexucabtagene autoleucel",
        drug_class=DrugClass.CELL_THERAPY.value,
        mechanism=DrugMechanism.CAR_T.value,
        targets=["CD19"],
        synonyms=["tecartus", "kte-x19"],
        expects_delayed_effect=True,
        expects_non_proportional_hazards=True,
        confidence=1.0,
        source="cache",
        nci_code="C148251"
    ),
    "lisocabtagene maraleucel": DrugClassification(
        drug_name="lisocabtagene maraleucel",
        drug_class=DrugClass.CELL_THERAPY.value,
        mechanism=DrugMechanism.CAR_T.value,
        targets=["CD19"],
        synonyms=["breyanzi", "liso-cel", "jcar017"],
        expects_delayed_effect=True,
        expects_non_proportional_hazards=True,
        confidence=1.0,
        source="cache",
        nci_code="C148262"
    ),
    "idecabtagene vicleucel": DrugClassification(
        drug_name="idecabtagene vicleucel",
        drug_class=DrugClass.CELL_THERAPY.value,
        mechanism=DrugMechanism.CAR_T.value,
        targets=["BCMA"],
        synonyms=["abecma", "ide-cel", "bb2121"],
        expects_delayed_effect=True,
        expects_non_proportional_hazards=True,
        confidence=1.0,
        source="cache",
        nci_code="C148290"
    ),
    "ciltacabtagene autoleucel": DrugClassification(
        drug_name="ciltacabtagene autoleucel",
        drug_class=DrugClass.CELL_THERAPY.value,
        mechanism=DrugMechanism.CAR_T.value,
        targets=["BCMA"],
        synonyms=["carvykti", "cilta-cel", "jnj-68284528"],
        expects_delayed_effect=True,
        expects_non_proportional_hazards=True,
        confidence=1.0,
        source="cache",
        nci_code="C162608"
    ),
}

# Build synonyms index for fast lookup
DRUG_SYNONYMS_INDEX: Dict[str, str] = {}
for drug_name, classification in ONCOLOGY_DRUG_CACHE.items():
    DRUG_SYNONYMS_INDEX[drug_name.lower()] = drug_name
    for synonym in classification.synonyms:
        DRUG_SYNONYMS_INDEX[synonym.lower()] = drug_name


# =============================================================================
# NCI THESAURUS API CLIENT
# =============================================================================

class NCIThesaurusClient:
    """
    Client for NCI EVS REST API.

    Documentation: https://api-evsrest.nci.nih.gov/
    Free, no API key required.
    """

    BASE_URL = "https://api-evsrest.nci.nih.gov/api/v1"

    # NCI concept codes for drug classes
    IMMUNOTHERAPY_ANCESTORS = {
        "C129822",  # Immunotherapy Agent
        "C129825",  # Immune Checkpoint Inhibitor
        "C128036",  # PD-1 Inhibiting Antibody
        "C128035",  # PD-L1 Inhibiting Antibody
        "C128037",  # CTLA-4 Inhibiting Antibody
    }

    CHEMOTHERAPY_ANCESTORS = {
        "C274",     # Antineoplastic Agent
        "C273",     # Chemotherapeutic Agent
    }

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "SAP-Generator/1.0"
        })

    def search_drug(self, drug_name: str) -> Optional[Dict[str, Any]]:
        """
        Search for a drug in NCI Thesaurus.

        Args:
            drug_name: Drug name to search

        Returns:
            Dictionary with drug info or None if not found
        """
        try:
            # Search in NCI Thesaurus (ncit terminology)
            url = f"{self.BASE_URL}/concept/ncit/search"
            params = {
                "term": drug_name,
                "type": "match",
                "include": "minimal,synonyms,parents",
                "pageSize": 5
            }

            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()
            concepts = data.get("concepts", [])

            if not concepts:
                return None

            # Return best match
            return self._parse_concept(concepts[0])

        except requests.RequestException as e:
            print(f"[NCI API] Error searching '{drug_name}': {e}")
            return None

    def get_concept(self, nci_code: str) -> Optional[Dict[str, Any]]:
        """
        Get concept by NCI code.

        Args:
            nci_code: NCI concept code (e.g., "C68814")

        Returns:
            Dictionary with concept info or None
        """
        try:
            url = f"{self.BASE_URL}/concept/ncit/{nci_code}"
            params = {"include": "full"}

            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()

            return self._parse_concept(response.json())

        except requests.RequestException as e:
            print(f"[NCI API] Error getting concept {nci_code}: {e}")
            return None

    def _parse_concept(self, concept: Dict[str, Any]) -> Dict[str, Any]:
        """Parse NCI concept into classification-friendly format."""
        code = concept.get("code", "")
        name = concept.get("name", "")

        # Get synonyms
        synonyms = []
        for syn in concept.get("synonyms", []):
            syn_name = syn.get("name", "")
            if syn_name and syn_name.lower() != name.lower():
                synonyms.append(syn_name)

        # Determine drug class from parents
        drug_class = DrugClass.UNKNOWN.value
        mechanism = DrugMechanism.UNKNOWN.value
        expects_delayed = False
        expects_nph = False

        parents = concept.get("parents", [])
        parent_codes = {p.get("code", "") for p in parents}

        # Check if immunotherapy
        if parent_codes & self.IMMUNOTHERAPY_ANCESTORS:
            drug_class = DrugClass.IMMUNOTHERAPY.value
            expects_delayed = True
            expects_nph = True

            # Determine specific mechanism
            for p in parents:
                p_name = p.get("name", "").lower()
                if "pd-1" in p_name:
                    mechanism = DrugMechanism.PD1_INHIBITOR.value
                elif "pd-l1" in p_name:
                    mechanism = DrugMechanism.PDL1_INHIBITOR.value
                elif "ctla-4" in p_name:
                    mechanism = DrugMechanism.CTLA4_INHIBITOR.value

        return {
            "nci_code": code,
            "name": name,
            "synonyms": synonyms,
            "drug_class": drug_class,
            "mechanism": mechanism,
            "expects_delayed_effect": expects_delayed,
            "expects_non_proportional_hazards": expects_nph,
            "parent_codes": list(parent_codes),
        }


# =============================================================================
# MAIN DRUG CLASSIFIER
# =============================================================================

class DrugClassifier:
    """
    Tiered drug classifier with ontology integration.

    Lookup order:
    1. LOCAL CACHE - 80+ common oncology drugs (instant)
    2. NCI THESAURUS API - 15,000+ drugs (200-500ms)
    3. LLM FALLBACK - Novel drugs with lower confidence
    """

    def __init__(self, llm_client=None, use_cache: bool = True, use_api: bool = True):
        """
        Initialize drug classifier.

        Args:
            llm_client: Optional LLM client for fallback classification
            use_cache: Whether to use local drug cache
            use_api: Whether to query NCI Thesaurus API
        """
        self.llm_client = llm_client
        self.use_cache = use_cache
        self.use_api = use_api

        # Initialize NCI client
        self.nci_client = NCIThesaurusClient() if use_api else None

        # Runtime cache for API results
        self._api_cache: Dict[str, DrugClassification] = {}

        print(f"[DrugClassifier] Initialized with {len(ONCOLOGY_DRUG_CACHE)} cached drugs")

    def classify(self, drug_name: str) -> DrugClassification:
        """
        Classify a drug using tiered lookup.

        Args:
            drug_name: Drug name (generic or brand name)

        Returns:
            DrugClassification with class, mechanism, and confidence
        """
        if not drug_name or not drug_name.strip():
            return self._unknown_classification(drug_name)

        drug_name_clean = drug_name.strip().lower()

        # TIER 1: Local cache (instant)
        if self.use_cache:
            cached = self._lookup_cache(drug_name_clean)
            if cached:
                print(f"[DrugClassifier] CACHE HIT: {drug_name} → {cached.drug_class}")
                return cached

        # Check runtime API cache
        if drug_name_clean in self._api_cache:
            print(f"[DrugClassifier] API CACHE HIT: {drug_name}")
            return self._api_cache[drug_name_clean]

        # TIER 2: NCI Thesaurus API (200-500ms)
        if self.use_api and self.nci_client:
            nci_result = self._lookup_nci(drug_name_clean)
            if nci_result:
                print(f"[DrugClassifier] NCI API: {drug_name} → {nci_result.drug_class}")
                self._api_cache[drug_name_clean] = nci_result
                return nci_result

        # TIER 3: LLM fallback (requires review)
        if self.llm_client:
            llm_result = self._classify_with_llm(drug_name)
            if llm_result:
                print(f"[DrugClassifier] LLM FALLBACK: {drug_name} → {llm_result.drug_class} (requires_review=True)")
                return llm_result

        # No classification found
        print(f"[DrugClassifier] UNKNOWN: {drug_name}")
        return self._unknown_classification(drug_name)

    def _lookup_cache(self, drug_name: str) -> Optional[DrugClassification]:
        """Look up drug in local cache."""
        # Direct lookup
        if drug_name in ONCOLOGY_DRUG_CACHE:
            return ONCOLOGY_DRUG_CACHE[drug_name]

        # Synonym lookup
        if drug_name in DRUG_SYNONYMS_INDEX:
            canonical = DRUG_SYNONYMS_INDEX[drug_name]
            return ONCOLOGY_DRUG_CACHE.get(canonical)

        # Partial match (e.g., "nivolumab injection" → "nivolumab")
        for cached_name in ONCOLOGY_DRUG_CACHE:
            if cached_name in drug_name or drug_name in cached_name:
                return ONCOLOGY_DRUG_CACHE[cached_name]

        return None

    def _lookup_nci(self, drug_name: str) -> Optional[DrugClassification]:
        """Look up drug in NCI Thesaurus."""
        try:
            result = self.nci_client.search_drug(drug_name)

            if not result:
                return None

            return DrugClassification(
                drug_name=result.get("name", drug_name),
                drug_class=result.get("drug_class", DrugClass.UNKNOWN.value),
                mechanism=result.get("mechanism", DrugMechanism.UNKNOWN.value),
                synonyms=result.get("synonyms", []),
                expects_delayed_effect=result.get("expects_delayed_effect", False),
                expects_non_proportional_hazards=result.get("expects_non_proportional_hazards", False),
                confidence=0.9,  # High confidence from authoritative source
                source="nci_thesaurus",
                nci_code=result.get("nci_code"),
                requires_review=False
            )

        except Exception as e:
            print(f"[DrugClassifier] NCI lookup error: {e}")
            return None

    def _classify_with_llm(self, drug_name: str) -> Optional[DrugClassification]:
        """Classify drug using LLM as fallback."""
        if not self.llm_client:
            return None

        prompt = f"""Classify this oncology drug for statistical analysis planning.

Drug: {drug_name}

Respond in JSON format:
{{
    "drug_class": "immunotherapy" | "chemotherapy" | "targeted_therapy" | "hormone_therapy" | "antibody_drug_conjugate" | "cell_therapy" | "unknown",
    "mechanism": "PD-1 inhibitor" | "PD-L1 inhibitor" | "CTLA-4 inhibitor" | "EGFR inhibitor" | "ALK inhibitor" | "PARP inhibitor" | "taxane" | "platinum compound" | "unknown" | [other],
    "targets": ["target1", "target2"],
    "expects_delayed_effect": true | false,
    "expects_non_proportional_hazards": true | false
}}

IMPORTANT:
- expects_delayed_effect = true for immunotherapy/checkpoint inhibitors
- expects_non_proportional_hazards = true for immunotherapy/checkpoint inhibitors
- If unknown drug, set drug_class="unknown" and expects_* = false
"""

        try:
            response = self.llm_client.chat(prompt, max_tokens=500)

            # Parse response
            if hasattr(response, 'content'):
                content = response.content
            elif isinstance(response, str):
                content = response
            else:
                return None

            # Extract JSON
            json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            if not json_match:
                return None

            data = json.loads(json_match.group())

            return DrugClassification(
                drug_name=drug_name,
                drug_class=data.get("drug_class", DrugClass.UNKNOWN.value),
                mechanism=data.get("mechanism", DrugMechanism.UNKNOWN.value),
                targets=data.get("targets", []),
                expects_delayed_effect=data.get("expects_delayed_effect", False),
                expects_non_proportional_hazards=data.get("expects_non_proportional_hazards", False),
                confidence=0.7,  # Lower confidence for LLM inference
                source="llm_inference",
                requires_review=True  # Flag for human review
            )

        except Exception as e:
            print(f"[DrugClassifier] LLM classification error: {e}")
            return None

    def _unknown_classification(self, drug_name: str) -> DrugClassification:
        """Return unknown classification."""
        return DrugClassification(
            drug_name=drug_name or "unknown",
            drug_class=DrugClass.UNKNOWN.value,
            mechanism=DrugMechanism.UNKNOWN.value,
            expects_delayed_effect=False,
            expects_non_proportional_hazards=False,
            confidence=0.0,
            source="none",
            requires_review=True
        )

    def classify_multiple(self, drug_names: List[str]) -> Dict[str, DrugClassification]:
        """Classify multiple drugs."""
        return {name: self.classify(name) for name in drug_names}

    def get_statistical_implications(self, classification: DrugClassification) -> Dict[str, Any]:
        """
        Get statistical method implications from classification.

        This is what feeds into the Knowledge Graph.
        """
        implications = {
            "expects_delayed_effect": classification.expects_delayed_effect,
            "expects_non_proportional_hazards": classification.expects_non_proportional_hazards,
            "recommended_primary_test": "stratified log-rank test",
            "recommended_nph_methods": [],
            "conditions_to_add": []
        }

        if classification.expects_delayed_effect:
            # NOTE: We NO LONGER recommend Fleming-Harrington here
            # The protocol must specify the statistical method - we don't infer from drug class
            # We only flag that this drug MAY have delayed effects (for informational purposes)
            implications["recommended_primary_test"] = ""  # Let protocol decide
            implications["recommended_nph_methods"] = []   # Let protocol decide
            implications["conditions_to_add"] = [
                "immunotherapy",
                # Note: delayed_effect and NPH are informational, not forcing method selection
            ]

        if classification.drug_class == DrugClass.CELL_THERAPY.value:
            implications["conditions_to_add"].append("cell_therapy")

        return implications


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_drug_classifier(llm_client=None) -> DrugClassifier:
    """Factory function to create drug classifier."""
    return DrugClassifier(llm_client=llm_client)


# =============================================================================
# TEST
# =============================================================================

def test_classifier():
    """Test the drug classifier."""
    print("=" * 60)
    print("DRUG CLASSIFIER TEST")
    print("=" * 60)

    classifier = create_drug_classifier()

    # Test drugs
    test_drugs = [
        # Known immunotherapy (cache hit)
        "nivolumab",
        "pembrolizumab",
        "Keytruda",  # Brand name

        # Known chemotherapy (cache hit)
        "docetaxel",
        "paclitaxel",

        # Known targeted therapy (cache hit)
        "osimertinib",
        "olaparib",

        # Should trigger NCI API lookup
        "cetuximab",
        "rituximab",

        # Novel/unknown (should trigger LLM or return unknown)
        "xyz-123456",
    ]

    print("\n" + "-" * 60)
    print("CLASSIFICATION RESULTS")
    print("-" * 60)

    for drug in test_drugs:
        result = classifier.classify(drug)
        print(f"\n{drug}:")
        print(f"  Class: {result.drug_class}")
        print(f"  Mechanism: {result.mechanism}")
        print(f"  Delayed Effect: {result.expects_delayed_effect}")
        print(f"  NPH: {result.expects_non_proportional_hazards}")
        print(f"  Source: {result.source}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Requires Review: {result.requires_review}")

        if result.expects_delayed_effect:
            implications = classifier.get_statistical_implications(result)
            print(f"  → Recommended: {implications['recommended_primary_test']}")

    print("\n" + "=" * 60)
    print(f"Total cached drugs: {len(ONCOLOGY_DRUG_CACHE)}")
    print("=" * 60)


if __name__ == "__main__":
    test_classifier()
