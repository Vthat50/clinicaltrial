#!/usr/bin/env python3
"""
Code Generation Orchestrator
=============================

Coordinates generation of all SAS programs from protocol facts.
Produces a complete, executable analysis package.

Usage:
    orchestrator = CodeGenerationOrchestrator()
    result = orchestrator.generate_all(protocol_facts)
    orchestrator.save_to_directory(result, output_path)
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

# ADaM generators
from .adam.adsl_generator import ADSLGenerator
from .adam.adae_generator import ADAEGenerator
from .adam.adtte_generator import ADTTEGenerator
from .adam.adeff_generator import ADEFFGenerator

# TLF generators - Tables
from .tlf.t_demog import DemographicsTableGenerator
from .tlf.t_ae_summary import AESummaryTableGenerator
from .tlf.t_primary import PrimaryEfficacyTableGenerator
from .tlf.t_secondary import SecondaryEfficacyTableGenerator

# TLF generators - Listings
from .tlf.l_demog import DemographicsListingGenerator
from .tlf.l_ae import AdverseEventsListingGenerator

# TLF generators - Figures
from .tlf.f_forest import ForestPlotGenerator

from .base import CodeGenerationResult


@dataclass
class GenerationPackage:
    """Complete package of generated SAS programs."""
    protocol_id: str
    generated_at: str
    therapeutic_area: str
    adam_programs: List[CodeGenerationResult] = field(default_factory=list)
    tlf_programs: List[CodeGenerationResult] = field(default_factory=list)
    driver_program: str = ""
    validation_checklist: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_all_programs(self) -> List[CodeGenerationResult]:
        """Return all generated programs."""
        return self.adam_programs + self.tlf_programs

    def get_program_names(self) -> List[str]:
        """Return list of all program names."""
        return [p.program_name for p in self.get_all_programs()]


class CodeGenerationOrchestrator:
    """
    Orchestrates generation of complete SAS program packages.

    Takes protocol facts (extracted from SAP) and generates:
    - ADaM dataset creation programs (ADSL, ADAE, ADTTE, ADEFF)
    - TLF output programs (demographics, AE summary, primary efficacy)
    - Driver program to execute all in correct order
    - Validation checklist
    """

    def __init__(self):
        # Initialize all generators
        self.adam_generators = {
            'adsl': ADSLGenerator(),
            'adae': ADAEGenerator(),
            'adtte': ADTTEGenerator(),
            'adeff': ADEFFGenerator(),
        }

        self.tlf_generators = {
            # Tables
            't_demog': DemographicsTableGenerator(),
            't_ae_summary': AESummaryTableGenerator(),
            't_primary': PrimaryEfficacyTableGenerator(),
            't_secondary': SecondaryEfficacyTableGenerator(),
            # Listings
            'l_demog': DemographicsListingGenerator(),
            'l_ae': AdverseEventsListingGenerator(),
            # Figures
            'f_forest': ForestPlotGenerator(),
        }

    def generate_all(self, protocol_facts: Dict[str, Any]) -> GenerationPackage:
        """
        Generate complete SAS program package from protocol facts.

        Args:
            protocol_facts: Dictionary containing extracted protocol information

        Returns:
            GenerationPackage with all generated programs
        """
        # Extract key metadata
        protocol_id = protocol_facts.get('protocol_id', 'UNKNOWN')
        therapeutic_area = protocol_facts.get('therapeutic_area', 'general')

        package = GenerationPackage(
            protocol_id=protocol_id,
            generated_at=datetime.now().isoformat(),
            therapeutic_area=therapeutic_area,
            metadata={
                'generator_version': '1.0.0',
                'sas_version': '9.4',
                'cdisc_adam_version': '1.1',
            }
        )

        # Generate ADaM programs
        package.adam_programs = self._generate_adam_programs(protocol_facts)

        # Generate TLF programs
        package.tlf_programs = self._generate_tlf_programs(protocol_facts)

        # Generate driver program
        package.driver_program = self._generate_driver_program(package)

        # Generate validation checklist
        package.validation_checklist = self._generate_validation_checklist(package)

        return package

    def _generate_adam_programs(self, protocol_facts: Dict[str, Any]) -> List[CodeGenerationResult]:
        """Generate all ADaM dataset programs."""
        programs = []

        # Helper to convert string results to CodeGenerationResult
        def wrap_result(generator, code_or_result):
            if isinstance(code_or_result, CodeGenerationResult):
                return code_or_result
            # Legacy generators return strings
            return CodeGenerationResult(
                program_name=generator.program_name,
                code=code_or_result,
                description=generator.program_purpose,
                input_datasets=['SDTM'],
                output_datasets=[generator.program_name.replace('.sas', '').upper()],
                validation_notes=["Review generated code", "Verify variable derivations"]
            )

        # Always generate ADSL first (other datasets depend on it)
        gen = self.adam_generators['adsl']
        programs.append(wrap_result(gen, gen.generate(protocol_facts)))

        # Generate ADAE for safety analysis
        gen = self.adam_generators['adae']
        programs.append(wrap_result(gen, gen.generate(protocol_facts)))

        # Generate ADTTE if time-to-event endpoints exist
        if self._has_tte_endpoints(protocol_facts):
            gen = self.adam_generators['adtte']
            programs.append(wrap_result(gen, gen.generate(protocol_facts)))

        # Generate ADEFF for efficacy analysis
        gen = self.adam_generators['adeff']
        programs.append(wrap_result(gen, gen.generate(protocol_facts)))

        return programs

    def _generate_tlf_programs(self, protocol_facts: Dict[str, Any]) -> List[CodeGenerationResult]:
        """Generate all TLF output programs."""
        programs = []

        # === TABLES ===

        # Demographics table (always required)
        programs.append(self.tlf_generators['t_demog'].generate(protocol_facts))

        # AE summary table (always required for safety)
        programs.append(self.tlf_generators['t_ae_summary'].generate(protocol_facts))

        # Primary efficacy table
        programs.append(self.tlf_generators['t_primary'].generate(protocol_facts))

        # Secondary efficacy table (if secondary endpoints exist)
        secondary_endpoints = protocol_facts.get('secondary_endpoints', [])
        if secondary_endpoints:
            programs.append(self.tlf_generators['t_secondary'].generate(protocol_facts))

        # === LISTINGS ===

        # Demographics listing (always required)
        programs.append(self.tlf_generators['l_demog'].generate(protocol_facts))

        # AE listing (always required for safety)
        programs.append(self.tlf_generators['l_ae'].generate(protocol_facts))

        # === FIGURES ===

        # Forest plot for subgroup analysis
        programs.append(self.tlf_generators['f_forest'].generate(protocol_facts))

        return programs

    def _has_tte_endpoints(self, protocol_facts: Dict[str, Any]) -> bool:
        """Check if protocol has time-to-event endpoints."""
        endpoints = protocol_facts.get('endpoints', [])
        tte_keywords = ['survival', 'time to', 'tte', 'os', 'pfs', 'dfs', 'efs']

        for endpoint in endpoints:
            name = endpoint.get('name', '').lower()
            if any(kw in name for kw in tte_keywords):
                return True

        # Also check therapeutic area defaults
        ta = protocol_facts.get('therapeutic_area', '').lower()
        if ta == 'oncology':
            return True

        return False

    def _generate_driver_program(self, package: GenerationPackage) -> str:
        """Generate master driver program that executes all programs in order."""

        header = f"""/*******************************************************************************
* PROGRAM:      driver.sas
* DESCRIPTION:  Master driver program - executes all analysis programs
* PROTOCOL:     {package.protocol_id}
* GENERATED:    {package.generated_at}
*
* EXECUTION ORDER:
*   1. ADaM dataset creation (ADSL -> ADAE -> ADTTE -> ADEFF)
*   2. TLF outputs (demographics -> AE summary -> primary efficacy)
*
* NOTES:
*   - Review all libname assignments before execution
*   - Ensure SDTM datasets are available
*   - Modify paths as needed for your environment
*******************************************************************************/

*-- Global options --;
options mprint mlogic symbolgen;
options sasautos=("&project_path./macros" sasautos);

*-- Path definitions --;
%let project_path = /clinical/project/{package.protocol_id};
%let sdtm_path = &project_path./data/sdtm;
%let adam_path = &project_path./data/adam;
%let output_path = &project_path./output;
%let program_path = &project_path./programs;

*-- Create output directories if needed --;
options dlcreatedir;
libname _temp "&adam_path";
libname _temp "&output_path";
libname _temp clear;

*-- Libname assignments --;
libname sdtm "&sdtm_path" access=readonly;
libname adam "&adam_path";
libname output "&output_path";

"""

        # ADaM programs section
        adam_section = """
/*******************************************************************************
* SECTION 1: ADaM DATASET CREATION
*******************************************************************************/

"""
        for prog in package.adam_programs:
            adam_section += f"""
*-- {prog.description} --;
%include "&program_path./adam/{prog.program_name}";
"""

        # TLF programs section
        tlf_section = """

/*******************************************************************************
* SECTION 2: TLF OUTPUT GENERATION
*******************************************************************************/

"""
        for prog in package.tlf_programs:
            tlf_section += f"""
*-- {prog.description} --;
%include "&program_path./tlf/{prog.program_name}";
"""

        # Footer
        footer = """

/*******************************************************************************
* COMPLETION
*******************************************************************************/

%put NOTE: ========================================;
%put NOTE: All programs executed successfully;
%put NOTE: ========================================;
%put NOTE: ADaM datasets created in: &adam_path;
%put NOTE: TLF outputs created in: &output_path;
%put NOTE: ========================================;
"""

        return header + adam_section + tlf_section + footer

    def _generate_validation_checklist(self, package: GenerationPackage) -> List[str]:
        """Generate validation checklist for QC review."""
        checklist = [
            "=== PRE-EXECUTION CHECKS ===",
            "[ ] SDTM datasets available and validated",
            "[ ] Libname paths updated for environment",
            "[ ] Macro library paths configured",
            "[ ] Output directories exist with write permissions",
            "",
            "=== ADaM DATASET VALIDATION ===",
        ]

        for prog in package.adam_programs:
            checklist.append(f"[ ] {prog.program_name}:")
            for note in prog.validation_notes:
                checklist.append(f"    [ ] {note}")

        checklist.extend([
            "",
            "=== TLF OUTPUT VALIDATION ===",
        ])

        for prog in package.tlf_programs:
            checklist.append(f"[ ] {prog.program_name}:")
            for note in prog.validation_notes:
                checklist.append(f"    [ ] {note}")

        checklist.extend([
            "",
            "=== POST-EXECUTION CHECKS ===",
            "[ ] All log files reviewed for errors/warnings",
            "[ ] Dataset counts match expected populations",
            "[ ] Table outputs match mock shells",
            "[ ] Cross-check key statistics with independent programming",
            "[ ] Documentation updated with any deviations",
        ])

        return checklist

    def save_to_directory(self, package: GenerationPackage, output_dir: str) -> Dict[str, str]:
        """
        Save all generated programs to directory structure.

        Args:
            package: GenerationPackage with all programs
            output_dir: Base output directory

        Returns:
            Dictionary mapping program names to file paths
        """
        saved_files = {}

        # Create directory structure
        adam_dir = os.path.join(output_dir, 'adam')
        tlf_dir = os.path.join(output_dir, 'tlf')
        os.makedirs(adam_dir, exist_ok=True)
        os.makedirs(tlf_dir, exist_ok=True)

        # Save ADaM programs
        for prog in package.adam_programs:
            filepath = os.path.join(adam_dir, prog.program_name)
            with open(filepath, 'w') as f:
                f.write(prog.code)
            saved_files[prog.program_name] = filepath

        # Save TLF programs
        for prog in package.tlf_programs:
            filepath = os.path.join(tlf_dir, prog.program_name)
            with open(filepath, 'w') as f:
                f.write(prog.code)
            saved_files[prog.program_name] = filepath

        # Save driver program
        driver_path = os.path.join(output_dir, 'driver.sas')
        with open(driver_path, 'w') as f:
            f.write(package.driver_program)
        saved_files['driver.sas'] = driver_path

        # Save validation checklist
        checklist_path = os.path.join(output_dir, 'validation_checklist.txt')
        with open(checklist_path, 'w') as f:
            f.write('\n'.join(package.validation_checklist))
        saved_files['validation_checklist.txt'] = checklist_path

        # Save metadata
        metadata_path = os.path.join(output_dir, 'generation_metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump({
                'protocol_id': package.protocol_id,
                'generated_at': package.generated_at,
                'therapeutic_area': package.therapeutic_area,
                'programs': package.get_program_names(),
                'metadata': package.metadata
            }, f, indent=2)
        saved_files['generation_metadata.json'] = metadata_path

        return saved_files

    def generate_from_sap(self, sap_content: str) -> GenerationPackage:
        """
        Generate programs directly from SAP document content.

        This method extracts protocol facts from the SAP and then
        generates all programs.

        Args:
            sap_content: Full SAP document text

        Returns:
            GenerationPackage with all generated programs
        """
        # Extract protocol facts from SAP
        protocol_facts = self._extract_facts_from_sap(sap_content)
        return self.generate_all(protocol_facts)

    def _extract_facts_from_sap(self, sap_content: str) -> Dict[str, Any]:
        """
        Extract structured protocol facts from SAP content.

        This is a simplified extraction - in production, this would
        use more sophisticated NLP/parsing.
        """
        facts = {
            'protocol_id': 'UNKNOWN',
            'therapeutic_area': 'general',
            'treatments': [],
            'endpoints': [],
            'populations': {},
        }

        # Extract protocol ID
        import re
        protocol_match = re.search(r'Protocol[:\s]+([A-Z0-9-]+)', sap_content, re.IGNORECASE)
        if protocol_match:
            facts['protocol_id'] = protocol_match.group(1)

        # Detect therapeutic area
        sap_lower = sap_content.lower()
        if any(term in sap_lower for term in ['crohn', 'colitis', 'ibd', 'mayo score']):
            facts['therapeutic_area'] = 'ibd'
        elif any(term in sap_lower for term in ['tumor', 'recist', 'oncology', 'cancer']):
            facts['therapeutic_area'] = 'oncology'
        elif any(term in sap_lower for term in ['rheumatoid', 'arthritis', 'das28', 'acr20']):
            facts['therapeutic_area'] = 'rheumatology'
        elif any(term in sap_lower for term in ['cardiac', 'heart', 'lvef', 'cardiovascular']):
            facts['therapeutic_area'] = 'cardiovascular'

        # Extract treatment arms
        arm_patterns = [
            r'(?:arm|group)\s*[:\s]*([^,\n]+(?:mg|placebo)[^,\n]*)',
            r'(\d+\s*mg\s+[A-Za-z]+)',
            r'(placebo)',
        ]
        for pattern in arm_patterns:
            matches = re.findall(pattern, sap_content, re.IGNORECASE)
            for match in matches:
                if match.strip() and match.strip() not in [t['name'] for t in facts['treatments']]:
                    facts['treatments'].append({
                        'name': match.strip(),
                        'code': f"TRT{len(facts['treatments']) + 1}"
                    })

        return facts
