"""
Define-XML Generator
====================

Generates CDISC Define-XML v2.1 metadata for SDTM datasets.
This is required for FDA regulatory submissions.

References:
- CDISC Define-XML v2.1
- FDA Study Data Technical Conformance Guide v5.5

Author: SAP Generation System
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

try:
    from .sdtm_domains import SDTMDomain, SDTMVariable, VariableCore, VariableRole
    from .sap_sdtm_mapper import SDTMSpec
except ImportError:
    from sdtm_domains import SDTMDomain, SDTMVariable, VariableCore, VariableRole
    from sap_sdtm_mapper import SDTMSpec


# Define-XML namespaces
NAMESPACES = {
    "odm": "http://www.cdisc.org/ns/odm/v1.3",
    "def": "http://www.cdisc.org/ns/def/v2.1",
    "xlink": "http://www.w3.org/1999/xlink",
    "arm": "http://www.cdisc.org/ns/arm/v1.0",
}


@dataclass
class DefineMetadata:
    """Define-XML document metadata."""
    study_oid: str
    study_name: str
    study_description: str
    protocol_name: str
    metadata_version_oid: str = "MDV.1.0.0"
    define_version: str = "2.1.0"
    creation_datetime: str = field(default_factory=lambda: datetime.now().isoformat())
    originator: str = "SAP Generation System"
    source_system: str = "Clinical Trial SAP System"
    source_system_version: str = "2.0"
    file_oid: str = "DEF.SDTM.001"
    context: str = "Submission"  # Submission or Other


class DefineXMLGenerator:
    """Generates Define-XML v2.1 documents from SDTM specifications."""

    # Standard codelists used in SDTM
    STANDARD_CODELISTS = {
        "NY": {
            "oid": "CL.NY",
            "name": "No Yes Response",
            "datatype": "text",
            "items": [("N", "No"), ("Y", "Yes")]
        },
        "SEX": {
            "oid": "CL.SEX",
            "name": "Sex",
            "datatype": "text",
            "items": [("F", "Female"), ("M", "Male"), ("U", "Unknown")]
        },
        "RACE": {
            "oid": "CL.RACE",
            "name": "Race",
            "datatype": "text",
            "items": [
                ("AMERICAN INDIAN OR ALASKA NATIVE", "American Indian or Alaska Native"),
                ("ASIAN", "Asian"),
                ("BLACK OR AFRICAN AMERICAN", "Black or African American"),
                ("NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER", "Native Hawaiian or Other Pacific Islander"),
                ("WHITE", "White"),
                ("MULTIPLE", "Multiple"),
                ("OTHER", "Other"),
            ]
        },
        "ETHNIC": {
            "oid": "CL.ETHNIC",
            "name": "Ethnicity",
            "datatype": "text",
            "items": [
                ("HISPANIC OR LATINO", "Hispanic or Latino"),
                ("NOT HISPANIC OR LATINO", "Not Hispanic or Latino"),
                ("NOT REPORTED", "Not Reported"),
                ("UNKNOWN", "Unknown"),
            ]
        },
        "ACN": {
            "oid": "CL.ACN",
            "name": "Action Taken with Study Treatment",
            "datatype": "text",
            "items": [
                ("DOSE INCREASED", "Dose Increased"),
                ("DOSE NOT CHANGED", "Dose Not Changed"),
                ("DOSE REDUCED", "Dose Reduced"),
                ("DRUG INTERRUPTED", "Drug Interrupted"),
                ("DRUG WITHDRAWN", "Drug Withdrawn"),
                ("NOT APPLICABLE", "Not Applicable"),
                ("UNKNOWN", "Unknown"),
            ]
        },
        "OUT": {
            "oid": "CL.OUT",
            "name": "Outcome of Event",
            "datatype": "text",
            "items": [
                ("FATAL", "Fatal"),
                ("NOT RECOVERED/NOT RESOLVED", "Not Recovered/Not Resolved"),
                ("RECOVERED/RESOLVED", "Recovered/Resolved"),
                ("RECOVERED/RESOLVED WITH SEQUELAE", "Recovered/Resolved With Sequelae"),
                ("RECOVERING/RESOLVING", "Recovering/Resolving"),
                ("UNKNOWN", "Unknown"),
            ]
        },
        "STAT": {
            "oid": "CL.STAT",
            "name": "Completion Status",
            "datatype": "text",
            "items": [("NOT DONE", "Not Done")]
        },
        "EVAL": {
            "oid": "CL.EVAL",
            "name": "Evaluator",
            "datatype": "text",
            "items": [
                ("ADJUDICATION COMMITTEE", "Adjudication Committee"),
                ("INDEPENDENT ASSESSOR", "Independent Assessor"),
                ("INVESTIGATOR", "Investigator"),
                ("SPONSOR", "Sponsor"),
            ]
        },
        "EPOCH": {
            "oid": "CL.EPOCH",
            "name": "Epoch",
            "datatype": "text",
            "items": [
                ("SCREENING", "Screening"),
                ("RUN-IN", "Run-in"),
                ("TREATMENT", "Treatment"),
                ("FOLLOW-UP", "Follow-up"),
            ]
        }
    }

    def __init__(self, metadata: DefineMetadata):
        """Initialize the generator with study metadata."""
        self.metadata = metadata

    def generate(self, spec: SDTMSpec) -> str:
        """
        Generate Define-XML document from SDTM specification.

        Args:
            spec: SDTMSpec object with domain and variable selections

        Returns:
            Define-XML document as string
        """
        # Create root element
        root = ET.Element("ODM")
        root.set("xmlns", NAMESPACES["odm"])
        root.set("xmlns:def", NAMESPACES["def"])
        root.set("xmlns:xlink", NAMESPACES["xlink"])
        root.set("xmlns:arm", NAMESPACES["arm"])
        root.set("ODMVersion", "1.3.2")
        root.set("FileOID", self.metadata.file_oid)
        root.set("FileType", "Snapshot")
        root.set("CreationDateTime", self.metadata.creation_datetime)
        root.set("Originator", self.metadata.originator)
        root.set("SourceSystem", self.metadata.source_system)
        root.set("SourceSystemVersion", self.metadata.source_system_version)
        root.set("def:Context", self.metadata.context)

        # Add Study element
        study = ET.SubElement(root, "Study")
        study.set("OID", self.metadata.study_oid)

        # Add GlobalVariables
        gv = ET.SubElement(study, "GlobalVariables")
        study_name = ET.SubElement(gv, "StudyName")
        study_name.text = self.metadata.study_name
        study_desc = ET.SubElement(gv, "StudyDescription")
        study_desc.text = self.metadata.study_description
        protocol_name = ET.SubElement(gv, "ProtocolName")
        protocol_name.text = self.metadata.protocol_name

        # Add MetaDataVersion
        mdv = ET.SubElement(study, "MetaDataVersion")
        mdv.set("OID", self.metadata.metadata_version_oid)
        mdv.set("Name", f"Study {self.metadata.study_name}, SDTM Data Definitions")
        mdv.set("Description", "SDTM Domain and Variable Definitions")
        mdv.set("def:DefineVersion", self.metadata.define_version)
        mdv.set("def:StandardName", "SDTMIG")
        mdv.set("def:StandardVersion", "3.4")

        # Add Standards
        self._add_standards(mdv)

        # Add ItemGroupDefs (Domains)
        for domain in spec.domains:
            variables = spec.variable_selections.get(domain.code, domain.variables[:10])
            self._add_item_group_def(mdv, domain, variables)

        # Add ItemDefs (Variables)
        added_items = set()
        for domain in spec.domains:
            variables = spec.variable_selections.get(domain.code, domain.variables[:10])
            for var in variables:
                item_oid = f"IT.{domain.code}.{var.name}"
                if item_oid not in added_items:
                    self._add_item_def(mdv, domain, var)
                    added_items.add(item_oid)

        # Add CodeLists
        self._add_codelists(mdv)

        # Add MethodDefs (computational methods)
        self._add_method_defs(mdv, spec)

        # Convert to string with pretty printing
        xml_string = ET.tostring(root, encoding="unicode")
        return self._prettify(xml_string)

    def _add_standards(self, parent: ET.Element):
        """Add Standard definitions."""
        standards = ET.SubElement(parent, "def:Standards")

        # SDTM Standard
        sdtm_std = ET.SubElement(standards, "def:Standard")
        sdtm_std.set("OID", "STD.1")
        sdtm_std.set("Name", "SDTMIG")
        sdtm_std.set("Type", "IG")
        sdtm_std.set("Version", "3.4")
        sdtm_std.set("Status", "Final")

        # CT Standard
        ct_std = ET.SubElement(standards, "def:Standard")
        ct_std.set("OID", "STD.2")
        ct_std.set("Name", "SDTM Terminology")
        ct_std.set("Type", "CT")
        ct_std.set("Version", "2024-03-29")
        ct_std.set("Status", "Final")

    def _add_item_group_def(
        self,
        parent: ET.Element,
        domain: SDTMDomain,
        variables: List[SDTMVariable]
    ):
        """Add ItemGroupDef for a domain."""
        ig = ET.SubElement(parent, "ItemGroupDef")
        ig.set("OID", f"IG.{domain.code}")
        ig.set("Name", domain.code)
        ig.set("Repeating", "Yes" if "per subject" in domain.structure.lower() else "No")
        ig.set("IsReferenceData", "No")
        ig.set("SASDatasetName", domain.code)
        ig.set("Purpose", "Tabulation")
        ig.set("def:StandardOID", "STD.1")
        ig.set("def:Structure", domain.structure)
        ig.set("def:Class", domain.domain_class.value)

        # Add Description
        desc = ET.SubElement(ig, "Description")
        tt = ET.SubElement(desc, "TranslatedText")
        tt.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
        tt.text = domain.description

        # Add ItemRefs
        for i, var in enumerate(variables, 1):
            item_ref = ET.SubElement(ig, "ItemRef")
            item_ref.set("ItemOID", f"IT.{domain.code}.{var.name}")
            item_ref.set("OrderNumber", str(i))
            item_ref.set("Mandatory", "Yes" if var.core == VariableCore.REQUIRED else "No")

            # Key Sequence for identifier variables
            if var.role == VariableRole.IDENTIFIER:
                item_ref.set("KeySequence", str(i))

    def _add_item_def(
        self,
        parent: ET.Element,
        domain: SDTMDomain,
        var: SDTMVariable
    ):
        """Add ItemDef for a variable."""
        item = ET.SubElement(parent, "ItemDef")
        item.set("OID", f"IT.{domain.code}.{var.name}")
        item.set("Name", var.name)
        item.set("DataType", "integer" if var.type == "Num" else "text")
        item.set("SASFieldName", var.name)

        # Set length for character variables
        if var.type == "Char":
            item.set("Length", str(var.length or 200))

        # Add Description
        desc = ET.SubElement(item, "Description")
        tt = ET.SubElement(desc, "TranslatedText")
        tt.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
        tt.text = var.label

        # Add CodeListRef if applicable
        if var.controlled_terms and var.controlled_terms in self.STANDARD_CODELISTS:
            cl_ref = ET.SubElement(item, "CodeListRef")
            cl_ref.set("CodeListOID", self.STANDARD_CODELISTS[var.controlled_terms]["oid"])

        # Add Origin
        origin = ET.SubElement(item, "def:Origin")
        origin.set("Type", "Collected" if var.role in [VariableRole.TOPIC, VariableRole.RECORD_QUALIFIER] else "Derived")

    def _add_codelists(self, parent: ET.Element):
        """Add CodeList definitions."""
        for cl_key, cl_data in self.STANDARD_CODELISTS.items():
            codelist = ET.SubElement(parent, "CodeList")
            codelist.set("OID", cl_data["oid"])
            codelist.set("Name", cl_data["name"])
            codelist.set("DataType", cl_data["datatype"])

            for code, decode in cl_data["items"]:
                ci = ET.SubElement(codelist, "CodeListItem")
                ci.set("CodedValue", code)

                decode_elem = ET.SubElement(ci, "Decode")
                tt = ET.SubElement(decode_elem, "TranslatedText")
                tt.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
                tt.text = decode

    def _add_method_defs(self, parent: ET.Element, spec: SDTMSpec):
        """Add MethodDef elements for derived variables."""
        methods_added = set()

        for domain in spec.domains:
            # Add standard methods for timing variables
            if domain.code in ["AE", "DS", "EX"]:
                method_oid = f"MT.{domain.code}.DY"
                if method_oid not in methods_added:
                    method = ET.SubElement(parent, "MethodDef")
                    method.set("OID", method_oid)
                    method.set("Name", f"Algorithm for {domain.code}DY")
                    method.set("Type", "Computation")

                    desc = ET.SubElement(method, "Description")
                    tt = ET.SubElement(desc, "TranslatedText")
                    tt.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
                    tt.text = f"{domain.code}DY = {domain.code}STDTC - RFSTDTC + 1 (if {domain.code}STDTC >= RFSTDTC)"

                    methods_added.add(method_oid)

    def _prettify(self, xml_string: str) -> str:
        """Return a pretty-printed XML string."""
        parsed = minidom.parseString(xml_string)
        return parsed.toprettyxml(indent="  ")


def generate_define_xml(
    spec: SDTMSpec,
    study_name: str,
    study_description: str,
    output_path: Optional[str] = None
) -> str:
    """
    Generate Define-XML from SDTM specification.

    Args:
        spec: SDTMSpec from SAP mapper
        study_name: Study name
        study_description: Study description
        output_path: Optional path to save XML file

    Returns:
        Define-XML content as string
    """
    metadata = DefineMetadata(
        study_oid=f"ST.{spec.study_id}",
        study_name=study_name,
        study_description=study_description,
        protocol_name=spec.study_id
    )

    generator = DefineXMLGenerator(metadata)
    xml_content = generator.generate(spec)

    if output_path:
        Path(output_path).write_text(xml_content)

    return xml_content


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    from pathlib import Path

    print("="*70)
    print("DEFINE-XML GENERATION TEST")
    print("="*70)

    # Import mapper
    from sap_sdtm_mapper import generate_sdtm_spec

    # Generate SDTM spec from SAP
    sap_path = Path("../../output/generated_saps/NCT03558139_sap.md")
    if sap_path.exists():
        spec = generate_sdtm_spec(str(sap_path), "NCT03558139", "oncology")

        # Generate Define-XML
        xml_content = generate_define_xml(
            spec,
            study_name="NCT03558139",
            study_description="Phase 1b Trial of Hu5F9-G4 in Combination With Avelumab",
            output_path="../../output/sdtm_specs/NCT03558139_define.xml"
        )

        print(f"\nGenerated Define-XML: {len(xml_content)} characters")
        print("Saved to: output/sdtm_specs/NCT03558139_define.xml")

        # Show first 50 lines
        lines = xml_content.split('\n')[:50]
        print("\nFirst 50 lines:")
        print('\n'.join(lines))
    else:
        print(f"SAP file not found: {sap_path}")
