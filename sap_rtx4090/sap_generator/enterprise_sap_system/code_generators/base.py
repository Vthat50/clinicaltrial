#!/usr/bin/env python3
"""
Base Classes for SAS Code Generation
=====================================

Provides foundation for all code generators with common utilities,
formatting standards, and validation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path


@dataclass
class CodeGenerationResult:
    """Result of a single program generation."""
    program_name: str = ""
    code: str = ""
    description: str = ""
    input_datasets: List[str] = field(default_factory=list)
    output_datasets: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    validation_notes: List[str] = field(default_factory=list)


@dataclass
class PackageGenerationResult:
    """Result of code generation containing all generated programs"""
    success: bool = True
    adam_programs: Dict[str, str] = field(default_factory=dict)
    tlf_programs: Dict[str, str] = field(default_factory=dict)
    analysis_programs: Dict[str, str] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def get_all_programs(self) -> Dict[str, str]:
        """Get all generated programs as a flat dictionary"""
        all_programs = {}
        for name, code in self.adam_programs.items():
            all_programs[f"adam/{name}"] = code
        for name, code in self.tlf_programs.items():
            all_programs[f"tlf/{name}"] = code
        for name, code in self.analysis_programs.items():
            all_programs[f"analysis/{name}"] = code
        return all_programs

    def save_all(self, output_dir: str) -> List[str]:
        """Save all programs to directory, return list of saved paths"""
        output_path = Path(output_dir)
        saved_paths = []

        for subdir, programs in [
            ("adam", self.adam_programs),
            ("tlf", self.tlf_programs),
            ("analysis", self.analysis_programs)
        ]:
            if programs:
                (output_path / subdir).mkdir(parents=True, exist_ok=True)
                for name, code in programs.items():
                    file_path = output_path / subdir / name
                    file_path.write_text(code, encoding='utf-8')
                    saved_paths.append(str(file_path))

        return saved_paths


class SASCodeGenerator(ABC):
    """
    Abstract base class for all SAS code generators.

    Provides common utilities for:
    - Header generation
    - Comment formatting
    - Variable name validation
    - Code structure standards
    """

    # SAS naming conventions
    MAX_VAR_LENGTH = 32
    MAX_LABEL_LENGTH = 256
    VALID_VAR_CHARS = set('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_')

    def __init__(self):
        self.generated_code: str = ""
        self.errors: List[str] = []
        self.warnings: List[str] = []

    @abstractmethod
    def generate(self, facts: Any):
        """Generate SAS code from protocol facts. Must be implemented by subclasses.

        Returns either a string (legacy) or CodeGenerationResult (new style).
        """
        pass

    @property
    def program_name(self) -> str:
        """Return the program filename (e.g., 'adsl.sas'). Override in subclass."""
        return "unnamed.sas"

    @property
    def program_purpose(self) -> str:
        """Return brief description of program purpose. Override in subclass."""
        return "SAS program"

    def generate_header(
        self,
        program_name: str = None,
        description: str = None,
        input_datasets: List[str] = None,
        output_datasets: List[str] = None,
        macros_used: List[str] = None,
        study_id: str = None,
        nct_id: str = "",
        additional_info: Dict[str, str] = None,
        **kwargs
    ) -> str:
        """Generate standard SAS program header.

        Supports two calling conventions:
        1. Legacy: generate_header(study_id, nct_id, additional_info)
        2. New: generate_header(program_name, description, input_datasets, ...)
        """
        date_str = datetime.now().strftime("%d%b%Y").upper()

        # Determine which calling convention
        if program_name is not None:
            # New TLF-style calling convention
            prog = program_name
            purpose = description or "SAS program"
            inputs = ", ".join(input_datasets) if input_datasets else "None"
            outputs = ", ".join(output_datasets) if output_datasets else "None"
            macros = ", ".join(macros_used) if macros_used else "None"

            header_lines = [
                "/" + "*" * 77,
                f"* PROGRAM:     {prog}",
                f"* DESCRIPTION: {purpose[:60]}",
                "*" + "-" * 76,
                f"* INPUT:       {inputs}",
                f"* OUTPUT:      {outputs}",
                f"* MACROS:      {macros}",
                "*" + "-" * 76,
                f"* CREATED:     {date_str}",
                "* AUTHOR:      Auto-generated by SAP System",
                "*" + "-" * 76,
                "* MODIFICATION HISTORY:",
                f"* {date_str}  SYSTEM  Initial version",
                "*" * 77 + "/",
                "",
            ]
            return "\n".join(header_lines)
        else:
            # Legacy calling convention - use first positional as study_id
            # This handles the case where generate_header is called with study_id as first arg
            study = study_id if study_id else kwargs.get('study_id', 'UNKNOWN')

            header_lines = [
                "/*" + "=" * 76 + "*/",
                f"/* Program: {self.program_name:<66} */",
                f"/* Study: {study:<68} */",
            ]

            if nct_id:
                header_lines.append(f"/* ClinicalTrials.gov: {nct_id:<54} */")

            header_lines.extend([
                f"/* Purpose: {self.program_purpose:<65} */",
                "/*" + "-" * 76 + "*/",
                f"/* Created: {date_str:<65} */",
                "/* Author: Auto-generated by SAP System                                      */",
                "/*" + "-" * 76 + "*/",
                "/* Modification History:                                                     */",
                "/* Date       Author      Description                                        */",
                f"/* {date_str}  SYSTEM      Initial version                                     */",
                "/*" + "=" * 76 + "*/",
                "",
            ])

            if additional_info:
                header_lines.append("/* Study Parameters:")
                for key, value in additional_info.items():
                    header_lines.append(f"/*   {key}: {value}")
                header_lines.append("*/")
                header_lines.append("")

            return "\n".join(header_lines)

    def generate_section_comment(self, title: str, level: int = 1) -> str:
        """Generate section divider comment"""
        if level == 1:
            return f"\n/*{'=' * 76}*/\n/* {title:<74} */\n/*{'=' * 76}*/\n"
        elif level == 2:
            return f"\n/*{'-' * 76}*/\n/* {title:<74} */\n/*{'-' * 76}*/\n"
        else:
            return f"\n/* --- {title} --- */\n"

    def sanitize_var_name(self, name: str) -> str:
        """Convert string to valid SAS variable name"""
        # Uppercase and replace invalid chars
        clean = name.upper().replace(' ', '_').replace('-', '_')
        # Remove any remaining invalid characters
        clean = ''.join(c for c in clean if c in self.VALID_VAR_CHARS)
        # Ensure starts with letter or underscore
        if clean and clean[0].isdigit():
            clean = '_' + clean
        # Truncate to max length
        return clean[:self.MAX_VAR_LENGTH]

    def format_sas_string(self, value: str, max_length: int = 200) -> str:
        """Format string for SAS, escaping quotes and truncating"""
        if not value:
            return "''"
        # Escape single quotes
        escaped = value.replace("'", "''")
        # Truncate if needed
        if len(escaped) > max_length:
            escaped = escaped[:max_length-3] + "..."
        return f"'{escaped}'"

    def generate_length_statement(self, variables: Dict[str, tuple]) -> str:
        """
        Generate LENGTH statement from variable definitions.

        Args:
            variables: Dict of {var_name: (type, length)}
                       type is 'char' or 'num', length is int
        """
        char_vars = []
        num_vars = []

        for var, (var_type, length) in variables.items():
            if var_type.lower() == 'char':
                char_vars.append(f"{var} ${length}")
            else:
                num_vars.append(f"{var} {length}")

        parts = []
        if char_vars:
            parts.append("    length " + " ".join(char_vars) + ";")
        if num_vars:
            parts.append("    length " + " ".join(num_vars) + ";")

        return "\n".join(parts)

    def generate_format_statement(self, formats: Dict[str, str]) -> str:
        """Generate FORMAT statement"""
        if not formats:
            return ""
        format_pairs = [f"{var} {fmt}" for var, fmt in formats.items()]
        return "    format " + " ".join(format_pairs) + ";"

    def generate_label_statement(self, labels: Dict[str, str]) -> str:
        """Generate LABEL statement"""
        if not labels:
            return ""
        lines = ["    label"]
        for var, label in labels.items():
            # Escape quotes and truncate
            safe_label = label.replace('"', "'")[:self.MAX_LABEL_LENGTH]
            lines.append(f'        {var} = "{safe_label}"')
        lines[-1] += ";"
        return "\n".join(lines)

    def generate_libname_statements(
        self,
        sdtm_path: str = "/data/sdtm",
        adam_path: str = "/data/adam",
        output_path: str = "/output"
    ) -> str:
        """Generate standard libname statements"""
        return f"""
/*--- Library References ---*/
libname sdtm "{sdtm_path}" access=readonly;
libname adam "{adam_path}";
libname output "{output_path}";

options mprint symbolgen nocenter ls=150 ps=60;
"""

    def generate_proc_contents(self, dataset: str) -> str:
        """Generate PROC CONTENTS for documentation"""
        return f"""
/*--- Dataset Documentation ---*/
proc contents data={dataset} varnum;
run;
"""

    def generate_proc_freq(self, dataset: str, variables: List[str], where: str = "") -> str:
        """Generate PROC FREQ for QC"""
        tables = " ".join(variables)
        where_clause = f"\n    where {where};" if where else ""
        return f"""
proc freq data={dataset};{where_clause}
    tables {tables} / missing;
run;
"""

    def wrap_in_macro(self, code: str, macro_name: str, parameters: List[str] = None) -> str:
        """Wrap code in a macro definition"""
        param_str = ""
        if parameters:
            param_str = "(" + ", ".join(parameters) + ")"

        return f"""
%macro {macro_name}{param_str};

{code}

%mend {macro_name};
"""

    def add_error(self, message: str):
        """Add error to errors list"""
        self.errors.append(message)

    def add_warning(self, message: str):
        """Add warning to warnings list"""
        self.warnings.append(message)

    def validate_required_facts(self, facts: Any, required_fields: List[str]) -> bool:
        """Check that required fields exist in facts"""
        missing = []
        for field_name in required_fields:
            value = getattr(facts, field_name, None)
            if value is None or value == "" or value == []:
                missing.append(field_name)

        if missing:
            self.add_warning(f"Missing recommended fields: {', '.join(missing)}")
            return False
        return True
