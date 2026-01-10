"""
SDTM Module
===========

SDTM domain knowledge base and SAP to SDTM mapping functionality.

This module provides:
- Complete SDTM domain specifications (35+ domains per SDTMIG v3.4)
- SAP parsing to extract data requirements
- Automatic mapping of SAP requirements to SDTM domains
- SDTM specification generation

Usage:
    from enterprise_sap_system.sdtm import (
        generate_sdtm_spec,
        SDTMMapper,
        SDTM_DOMAINS,
        get_domain
    )

    # Generate SDTM spec from SAP
    spec = generate_sdtm_spec("path/to/sap.md", "NCT12345678", "oncology")

    # Get specific domain
    ae_domain = get_domain("AE")
"""

from .sdtm_domains import (
    SDTMDomain,
    SDTMVariable,
    DomainClass,
    VariableRole,
    VariableCore,
    SDTM_DOMAINS,
    get_domain,
    get_all_domains,
    get_domains_by_class,
    find_domains_by_trigger,
)

from .sap_sdtm_mapper import (
    SAPParser,
    SDTMMapper,
    SDTMSpec,
    DataRequirement,
    generate_sdtm_spec,
    format_sdtm_spec_as_markdown,
)

from .define_xml import (
    DefineXMLGenerator,
    DefineMetadata,
    generate_define_xml,
)

__all__ = [
    # Domain classes
    "SDTMDomain",
    "SDTMVariable",
    "DomainClass",
    "VariableRole",
    "VariableCore",
    # Domain registry
    "SDTM_DOMAINS",
    "get_domain",
    "get_all_domains",
    "get_domains_by_class",
    "find_domains_by_trigger",
    # SAP Mapper
    "SAPParser",
    "SDTMMapper",
    "SDTMSpec",
    "DataRequirement",
    "generate_sdtm_spec",
    "format_sdtm_spec_as_markdown",
    # Define-XML
    "DefineXMLGenerator",
    "DefineMetadata",
    "generate_define_xml",
]
