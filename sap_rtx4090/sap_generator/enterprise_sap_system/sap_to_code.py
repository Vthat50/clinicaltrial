#!/usr/bin/env python3
"""
SAP to Code Integration
========================

Bridges SAP generation with SAS code generation.
100% additive - does not modify any existing code.

Usage:
    from sap_to_code import generate_sap_with_code, generate_code_from_facts

    # Option 1: Full pipeline (protocol → SAP → code)
    result = generate_sap_with_code(protocol_text)

    # Option 2: Just code from existing facts
    code_package = generate_code_from_facts(pipeline_result.facts)
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

# Import existing pipeline (unchanged)
from core.constrained_pipeline import ConstrainedSAPPipeline, PipelineResult
from core.full_schema_generator import FullProtocolFacts

# Import new code generators (additive)
from code_generators import CodeGenerationOrchestrator, GenerationPackage

# Import SDTM specification generator
from specs.sdtm_specs import SDTMSpecGenerator, SDTMSpecification


@dataclass
class FullGenerationResult:
    """Combined result: SAP + SDTM Specs + SAS Code"""
    # SAP Generation
    sap_success: bool = False
    sap_text: str = ""
    facts: Optional[FullProtocolFacts] = None
    sap_errors: list = field(default_factory=list)

    # SDTM Specification Generation
    sdtm_success: bool = False
    sdtm_spec: Optional[SDTMSpecification] = None
    sdtm_errors: list = field(default_factory=list)

    # Code Generation
    code_success: bool = False
    code_package: Optional[GenerationPackage] = None
    code_errors: list = field(default_factory=list)

    # Output paths
    sap_path: str = ""
    sdtm_path: str = ""
    code_paths: Dict[str, str] = field(default_factory=dict)


def facts_to_dict(facts: FullProtocolFacts) -> Dict[str, Any]:
    """
    Convert FullProtocolFacts to dictionary for code generators.

    Maps the dataclass fields to the format expected by CodeGenerationOrchestrator.
    """
    # Build treatments list from arm data
    treatments = []
    arm_names = facts.arm_names or []
    arm_doses = facts.arm_doses or []

    for i, name in enumerate(arm_names):
        dose = arm_doses[i] if i < len(arm_doses) else ""
        treatments.append({
            "name": name,
            "dose": dose,
            "code": f"TRT{i+1}",
            "n": str(i + 1)
        })

    # Build primary endpoint dict
    primary_endpoint = {
        "name": facts.primary_endpoint or "Primary Endpoint",
        "definition": facts.primary_endpoint_definition or "",
        "parameter": _derive_paramcd(facts.primary_endpoint, facts.therapeutic_area),
        "type": _derive_endpoint_type(facts.primary_endpoint, facts.therapeutic_area),
    }

    # Build primary timepoint dict
    primary_timepoint = {
        "visit": facts.primary_timepoint or "Week 12",
        "avisit": (facts.primary_timepoint or "Week 12").upper().replace(" ", " "),
        "avisitn": _extract_week_number(facts.primary_timepoint),
    }

    # Build secondary endpoints list
    secondary_endpoints = []
    for ep in (facts.secondary_endpoints or []):
        secondary_endpoints.append({
            "name": ep,
            "parameter": _derive_paramcd(ep, facts.therapeutic_area),
        })

    return {
        # Identifiers
        "protocol_id": facts.nct_id or facts.study_id or "UNKNOWN",
        "study_id": facts.study_id or facts.nct_id or "UNKNOWN",
        "nct_id": facts.nct_id or "",
        "sponsor": facts.sponsor or "",

        # Study info
        "title": facts.title or "",
        "phase": facts.phase or "",
        "therapeutic_area": facts.therapeutic_area or "general",
        "indication": facts.indication or "",
        "design_type": facts.design_type or "",

        # Drug/Treatment
        "drug_name": facts.drug_name or "Study Drug",
        "drug_code": facts.drug_code or "",
        "route": facts.route or "",

        # Arms
        "treatments": treatments,
        "arm_names": arm_names,
        "arm_doses": arm_doses,
        "num_arms": facts.num_arms or len(arm_names),
        "ratio": facts.ratio or "1:1",

        # Sample size
        "total_n": facts.total_n or 100,
        "per_arm_n": facts.per_arm_n or {},
        "power": facts.power or "",
        "alpha": facts.alpha or 0.05,

        # Endpoints
        "primary_endpoint": primary_endpoint,
        "primary_timepoint": primary_timepoint,
        "secondary_endpoints": secondary_endpoints,

        # Populations
        "primary_population": facts.primary_population or "ITT",
        "itt_definition": facts.itt_definition or "All randomized patients",
        "safety_definition": facts.safety_definition or "All patients who received at least one dose",
        "pp_definition": facts.pp_definition or "",
        "efficacy_population": "ITTFL",
        "safety_population": "SAFFL",
        "demographics_population": "SAFFL",

        # Stratification
        "stratification_factors": facts.stratification_factors or [],

        # Analysis
        "primary_analysis_method": facts.primary_analysis_method or "",

        # Study timing
        "study_duration": facts.study_duration or "",
    }


def _derive_paramcd(endpoint_name: str, therapeutic_area: str) -> str:
    """Derive PARAMCD from endpoint name."""
    if not endpoint_name:
        return "PRMEFF"

    ep_lower = endpoint_name.lower()
    ta = (therapeutic_area or "").lower()

    # IBD endpoints
    if "remission" in ep_lower:
        return "CLREMIS"
    if "response" in ep_lower and "clinical" in ep_lower:
        return "CLRESP"
    if "mayo" in ep_lower:
        return "MAYO"
    if "endoscop" in ep_lower:
        return "ENDOIMP"

    # Oncology endpoints
    if "overall survival" in ep_lower or ep_lower == "os":
        return "OS"
    if "progression" in ep_lower or "pfs" in ep_lower:
        return "PFS"
    if "response rate" in ep_lower or "orr" in ep_lower:
        return "ORR"

    # Rheumatology endpoints
    if "acr20" in ep_lower:
        return "ACR20"
    if "acr50" in ep_lower:
        return "ACR50"
    if "das28" in ep_lower:
        return "DAS28"

    return "PRMEFF"


def _derive_endpoint_type(endpoint_name: str, therapeutic_area: str) -> str:
    """Derive endpoint type (continuous, binary, time_to_event)."""
    if not endpoint_name:
        return "continuous"

    ep_lower = endpoint_name.lower()

    # Binary endpoints
    binary_keywords = ["remission", "response", "responder", "acr", "orr", "rate"]
    if any(kw in ep_lower for kw in binary_keywords):
        return "binary"

    # Time-to-event endpoints
    tte_keywords = ["survival", "time to", "pfs", "efs", "dfs", "tte"]
    if any(kw in ep_lower for kw in tte_keywords):
        return "time_to_event"

    return "continuous"


def _extract_week_number(timepoint: str) -> int:
    """Extract week number from timepoint string."""
    if not timepoint:
        return 12

    import re
    match = re.search(r'week\s*(\d+)', timepoint, re.IGNORECASE)
    if match:
        return int(match.group(1))

    match = re.search(r'(\d+)\s*week', timepoint, re.IGNORECASE)
    if match:
        return int(match.group(1))

    return 12  # Default


def generate_sdtm_specs_from_facts(
    facts: FullProtocolFacts,
    output_dir: str = None
) -> SDTMSpecification:
    """
    Generate SDTM domain specifications from FullProtocolFacts.

    This implements Sandy's vision: Protocol/SAP → SDTM Specs

    Args:
        facts: FullProtocolFacts from SAP generation
        output_dir: Optional directory to save specs

    Returns:
        SDTMSpecification with all required domains
    """
    # Convert facts to dict format
    facts_dict = facts_to_dict(facts)

    # Generate SDTM specs
    generator = SDTMSpecGenerator()
    spec = generator.generate(facts_dict)

    # Save if output dir provided
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        generator.save_specification(spec, output_dir)

    return spec


def generate_code_from_facts(
    facts: FullProtocolFacts,
    output_dir: str = None
) -> GenerationPackage:
    """
    Generate SAS code from FullProtocolFacts.

    Args:
        facts: FullProtocolFacts from SAP generation
        output_dir: Optional directory to save generated code

    Returns:
        GenerationPackage with all SAS programs
    """
    # Convert facts to dict format
    facts_dict = facts_to_dict(facts)

    # Generate code
    orchestrator = CodeGenerationOrchestrator()
    package = orchestrator.generate_all(facts_dict)

    # Save if output dir provided
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        orchestrator.save_to_directory(package, output_dir)

    return package


def generate_sap_with_code(
    protocol_text: str,
    nct_id: str = None,
    output_dir: str = None,
    skip_sections: list = None
) -> FullGenerationResult:
    """
    Full pipeline: Protocol → SAP → SDTM Specs → SAS Code

    This is the main integration function implementing Sandy's vision:
    1. Generates SAP using existing pipeline (unchanged)
    2. Extracts protocol facts
    3. Generates SDTM domain specifications from facts
    4. Generates SAS code from facts

    Args:
        protocol_text: Full protocol document text
        nct_id: NCT ID (optional)
        output_dir: Directory to save outputs
        skip_sections: SAP sections to skip

    Returns:
        FullGenerationResult with SAP, SDTM specs, and code
    """
    result = FullGenerationResult()

    # Step 1: Generate SAP using existing pipeline
    print("\n" + "="*60)
    print("INTEGRATED SAP + SDTM + CODE GENERATION")
    print("="*60)
    print("\n[1/3] Generating SAP...")

    pipeline = ConstrainedSAPPipeline()
    sap_result = pipeline.generate(
        protocol_text=protocol_text,
        nct_id=nct_id,
        skip_sections=skip_sections
    )

    result.sap_success = sap_result.success
    result.sap_text = sap_result.sap_text
    result.facts = sap_result.facts
    result.sap_errors = sap_result.errors

    if not sap_result.success:
        print(f"[!] SAP generation failed: {sap_result.errors}")
        return result

    print(f"[✓] SAP generated successfully ({len(sap_result.sap_text):,} characters)")

    # Step 2: Generate SDTM Specifications from facts
    print("\n[2/3] Generating SDTM specifications...")

    if sap_result.facts:
        try:
            sdtm_output_dir = None
            if output_dir:
                sdtm_output_dir = os.path.join(output_dir, "sdtm_specs")

            sdtm_spec = generate_sdtm_specs_from_facts(
                facts=sap_result.facts,
                output_dir=sdtm_output_dir
            )

            result.sdtm_success = True
            result.sdtm_spec = sdtm_spec

            if output_dir:
                result.sdtm_path = os.path.join(sdtm_output_dir, "sdtm_specification.md")

            print(f"[✓] Generated SDTM specs for {len(sdtm_spec.domains)} domains")
            print(f"    Domains: {', '.join(sdtm_spec.get_all_domain_codes())}")

        except Exception as e:
            result.sdtm_success = False
            result.sdtm_errors.append(str(e))
            print(f"[!] SDTM spec generation failed: {e}")
    else:
        result.sdtm_errors.append("No protocol facts available")
        print("[!] No protocol facts extracted - cannot generate SDTM specs")

    # Step 3: Generate SAS code from facts
    print("\n[3/3] Generating SAS code...")

    if sap_result.facts:
        try:
            code_output_dir = None
            if output_dir:
                code_output_dir = os.path.join(output_dir, "sas_programs")

            package = generate_code_from_facts(
                facts=sap_result.facts,
                output_dir=code_output_dir
            )

            result.code_success = True
            result.code_package = package

            # Track output paths
            if output_dir:
                result.sap_path = os.path.join(output_dir, "sap.md")
                result.code_paths = {
                    "adam": os.path.join(code_output_dir, "adam"),
                    "tlf": os.path.join(code_output_dir, "tlf"),
                    "driver": os.path.join(code_output_dir, "driver.sas"),
                }

                # Save SAP
                with open(result.sap_path, 'w') as f:
                    f.write(sap_result.sap_text)

            total_lines = sum(
                len(p.code.split('\n'))
                for p in package.adam_programs + package.tlf_programs
            )
            print(f"[✓] Generated {len(package.adam_programs)} ADaM + {len(package.tlf_programs)} TLF programs")
            print(f"[✓] Total: {total_lines:,} lines of SAS code")

        except Exception as e:
            result.code_success = False
            result.code_errors.append(str(e))
            print(f"[!] Code generation failed: {e}")
    else:
        result.code_errors.append("No protocol facts available")
        print("[!] No protocol facts extracted - cannot generate code")

    # Summary
    print("\n" + "="*60)
    print("GENERATION COMPLETE")
    print("="*60)
    print(f"SAP:       {'✓' if result.sap_success else '✗'}")
    print(f"SDTM Specs: {'✓' if result.sdtm_success else '✗'}")
    print(f"SAS Code:  {'✓' if result.code_success else '✗'}")

    if output_dir:
        print(f"\nOutputs saved to: {output_dir}")

    return result


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate SAP and SAS code from protocol")
    parser.add_argument("protocol_path", help="Path to protocol PDF or text file")
    parser.add_argument("-o", "--output", help="Output directory", default="./output")
    parser.add_argument("--nct-id", help="NCT ID (optional)")
    parser.add_argument("--code-only", action="store_true", help="Generate code only (requires existing facts)")

    args = parser.parse_args()

    # Read protocol
    print(f"Reading protocol from: {args.protocol_path}")

    if args.protocol_path.endswith('.pdf'):
        # Would need PDF extraction - for now just note it
        print("PDF support requires pdfplumber. Please provide text file.")
        exit(1)
    else:
        with open(args.protocol_path, 'r') as f:
            protocol_text = f.read()

    # Generate
    result = generate_sap_with_code(
        protocol_text=protocol_text,
        nct_id=args.nct_id,
        output_dir=args.output
    )

    if result.sap_success and result.code_success:
        print("\n✓ All generation complete!")
        exit(0)
    else:
        print("\n✗ Generation had errors")
        exit(1)
