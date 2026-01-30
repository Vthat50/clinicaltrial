#!/usr/bin/env python3
"""
Production-grade SAP Parser
===========================
Parses all 151 reference SAPs into structured JSON format.

Each SAP is parsed into sections based on hierarchical numbering (1., 1.1, 1.1.1, etc.)
This allows querying ANY section from ANY SAP, not just predefined section types.

Output format:
{
    "sap_name": "PACIFIC_SAP",
    "metadata": {
        "sponsor": "AstraZeneca",
        "indication": "NSCLC",
        "phase": "III"
    },
    "sections": [
        {
            "number": "3.1",
            "title": "Derivation of RECIST Visit Responses",
            "level": 2,
            "content": "...",
            "start_line": 450,
            "end_line": 520
        },
        ...
    ],
    "section_index": {
        "3.1": 0,  # index into sections array
        "3.1.1": 1,
        ...
    }
}
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ProcessPoolExecutor
import hashlib


@dataclass
class Section:
    number: str
    title: str
    level: int
    content: str
    start_line: int
    end_line: int


@dataclass
class ParsedSAP:
    sap_name: str
    file_path: str
    total_chars: int
    total_lines: int
    sections: List[Section]
    section_index: Dict[str, int]
    metadata: Dict[str, str]


class SAPParser:
    """
    Parses SAP documents into structured sections.

    Handles multiple section numbering formats:
    - "1." / "1.1" / "1.1.1" (AstraZeneca style)
    - "1.0" / "2.0" / "2.1" (Merck style)
    - "1." / "3.1." / "3.3.1." (trailing dots)
    """

    # Regex patterns for section headers
    SECTION_PATTERNS = [
        # Pattern 1: "1.0 TITLE" or "1.1 TITLE" on same line
        r'^(\d+(?:\.\d+)*\.?\d*)\s+([A-Z][A-Z\s&\(\)\-\'\/,]+)$',

        # Pattern 2: "1." or "1.1" alone on line, title on next line
        r'^(\d+(?:\.\d+)*\.?)$',
    ]

    # Lines to skip (headers, footers, page numbers)
    SKIP_PATTERNS = [
        r'^---\s*Page\s*\d+\s*---',
        r'^Statistical Analysis Plan\s*$',
        r'^Study Code\s+',
        r'^Edition Number\s+',
        r'^Date\s+\d',
        r'^\d+$',  # Standalone page numbers
        r'^PPD$',  # Redacted content
        r'^\.{10,}',  # TOC dots
        r'^\s*$',  # Empty lines
    ]

    def __init__(self):
        self.section_re = [re.compile(p, re.MULTILINE) for p in self.SECTION_PATTERNS]
        self.skip_re = [re.compile(p) for p in self.SKIP_PATTERNS]

    def should_skip_line(self, line: str) -> bool:
        """Check if line is a header/footer/noise to skip."""
        return any(p.match(line.strip()) for p in self.skip_re)

    def extract_section_number(self, line: str) -> Optional[Tuple[str, str, int]]:
        """
        Extract section number and title from a line.
        Returns: (number, title, level) or None
        """
        line = line.strip()

        # Skip noise lines
        if self.should_skip_line(line):
            return None

        # Try pattern 1: "1.0 TITLE" on same line
        match = re.match(r'^(\d+(?:\.\d+)*\.?\d*)\s+([A-Z][A-Za-z\s&\(\)\-\'\/,\.]+)', line)
        if match:
            number = match.group(1).rstrip('.')
            title = match.group(2).strip()
            # Must have at least 3 uppercase chars to be a real title
            if sum(1 for c in title if c.isupper()) >= 3:
                level = number.count('.') + 1
                return (number, title, level)

        # Try pattern 2: Just a section number
        match = re.match(r'^(\d+(?:\.\d+)*\.?)$', line)
        if match:
            number = match.group(1).rstrip('.')
            level = number.count('.') + 1
            return (number, "", level)  # Title will be on next line

        return None

    def parse_file(self, file_path: Path) -> ParsedSAP:
        """Parse a single SAP file into structured sections."""
        content = file_path.read_text(encoding='utf-8', errors='ignore')
        lines = content.split('\n')

        sections: List[Section] = []
        current_section: Optional[Dict] = None
        content_lines: List[str] = []

        i = 0
        while i < len(lines):
            line = lines[i]

            # Try to extract section header
            section_info = self.extract_section_number(line)

            if section_info:
                number, title, level = section_info

                # If title is empty, check next line
                if not title and i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    # Next line should be mostly uppercase (title)
                    if next_line and sum(1 for c in next_line if c.isupper()) >= 3:
                        if not self.should_skip_line(next_line):
                            title = next_line
                            i += 1

                # Save previous section
                if current_section:
                    current_section['content'] = '\n'.join(content_lines).strip()
                    current_section['end_line'] = i - 1
                    sections.append(Section(**current_section))

                # Start new section
                current_section = {
                    'number': number,
                    'title': title,
                    'level': level,
                    'content': '',
                    'start_line': i + 1,
                    'end_line': i + 1
                }
                content_lines = []
            else:
                # Add line to current section content
                if current_section and not self.should_skip_line(line):
                    content_lines.append(line)

            i += 1

        # Save last section
        if current_section:
            current_section['content'] = '\n'.join(content_lines).strip()
            current_section['end_line'] = len(lines)
            sections.append(Section(**current_section))

        # Build section index
        section_index = {s.number: idx for idx, s in enumerate(sections)}

        # Extract metadata
        metadata = self._extract_metadata(file_path.stem, content)

        return ParsedSAP(
            sap_name=file_path.stem,
            file_path=str(file_path),
            total_chars=len(content),
            total_lines=len(lines),
            sections=sections,
            section_index=section_index,
            metadata=metadata
        )

    def _extract_metadata(self, filename: str, content: str) -> Dict[str, str]:
        """Extract metadata from filename and content."""
        metadata = {}

        # Indication from filename
        filename_lower = filename.lower()
        if 'nsclc' in filename_lower or 'lung' in filename_lower or 'pacific' in filename_lower:
            metadata['indication'] = 'NSCLC'
        elif 'breast' in filename_lower or 'destiny' in filename_lower:
            metadata['indication'] = 'Breast'
        elif 'lymphoma' in filename_lower or 'zuma' in filename_lower or 'elara' in filename_lower:
            metadata['indication'] = 'Lymphoma'
        elif 'myeloma' in filename_lower or 'cassiopeia' in filename_lower:
            metadata['indication'] = 'Myeloma'
        elif 'colorectal' in filename_lower or 'beacon' in filename_lower:
            metadata['indication'] = 'Colorectal'
        elif 'melanoma' in filename_lower:
            metadata['indication'] = 'Melanoma'
        elif 'renal' in filename_lower or 'kidney' in filename_lower:
            metadata['indication'] = 'Renal'
        elif 'ovarian' in filename_lower:
            metadata['indication'] = 'Ovarian'
        elif 'gastric' in filename_lower:
            metadata['indication'] = 'Gastric'
        elif 'cervical' in filename_lower:
            metadata['indication'] = 'Cervical'
        elif 'endometrial' in filename_lower:
            metadata['indication'] = 'Endometrial'
        elif 'leukemia' in filename_lower or 'aml' in filename_lower:
            metadata['indication'] = 'Leukemia'

        # Phase from content
        if 'Phase III' in content or 'Phase 3' in content or 'phase III' in content:
            metadata['phase'] = 'III'
        elif 'Phase II' in content or 'Phase 2' in content:
            metadata['phase'] = 'II'
        elif 'Phase I' in content or 'Phase 1' in content:
            metadata['phase'] = 'I'

        # Sponsor from content patterns
        if 'AstraZeneca' in content or 'MEDI' in content:
            metadata['sponsor'] = 'AstraZeneca'
        elif 'Merck' in content or 'MK-' in content or 'KEYNOTE' in content.upper():
            metadata['sponsor'] = 'Merck'
        elif 'Bristol-Myers' in content or 'BMS' in content or 'CheckMate' in content:
            metadata['sponsor'] = 'BMS'
        elif 'Roche' in content or 'Genentech' in content:
            metadata['sponsor'] = 'Roche'
        elif 'Kite' in content or 'Gilead' in content:
            metadata['sponsor'] = 'Kite/Gilead'
        elif 'Novartis' in content:
            metadata['sponsor'] = 'Novartis'
        elif 'Pfizer' in content:
            metadata['sponsor'] = 'Pfizer'

        return metadata


def parse_all_saps(input_dir: Path, output_dir: Path, force: bool = False) -> Dict[str, str]:
    """
    Parse all SAP files and save as structured JSON.

    Args:
        input_dir: Directory containing .txt SAP files
        output_dir: Directory to save .json parsed files
        force: If True, reparse even if JSON exists

    Returns:
        Dict mapping SAP name to JSON file path
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    parser = SAPParser()
    sap_files = list(input_dir.glob('*.txt'))

    results = {}
    parsed_count = 0
    skipped_count = 0

    print(f"Parsing {len(sap_files)} SAP files...")

    for sap_file in sap_files:
        output_file = output_dir / f"{sap_file.stem}.json"

        # Skip if already parsed (unless force)
        if output_file.exists() and not force:
            results[sap_file.stem] = str(output_file)
            skipped_count += 1
            continue

        try:
            parsed = parser.parse_file(sap_file)

            # Convert to JSON-serializable format
            output_data = {
                'sap_name': parsed.sap_name,
                'file_path': parsed.file_path,
                'total_chars': parsed.total_chars,
                'total_lines': parsed.total_lines,
                'metadata': parsed.metadata,
                'section_count': len(parsed.sections),
                'sections': [asdict(s) for s in parsed.sections],
                'section_index': parsed.section_index
            }

            # Save JSON
            output_file.write_text(json.dumps(output_data, indent=2))
            results[parsed.sap_name] = str(output_file)
            parsed_count += 1

            print(f"  Parsed: {sap_file.stem} -> {len(parsed.sections)} sections")

        except Exception as e:
            print(f"  ERROR parsing {sap_file.stem}: {e}")

    print(f"\nComplete: {parsed_count} parsed, {skipped_count} skipped (already exist)")
    return results


def build_section_index(parsed_dir: Path) -> Dict:
    """
    Build a master index of all sections across all SAPs.

    This allows quick lookup by:
    - Section title keywords
    - Section number patterns
    - Indication/trial type
    """
    index = {
        'by_keyword': {},      # keyword -> [(sap_name, section_number), ...]
        'by_indication': {},   # indication -> [sap_name, ...]
        'by_section_num': {},  # section_number -> [(sap_name, title), ...]
        'sap_list': []
    }

    json_files = list(parsed_dir.glob('*.json'))

    for json_file in json_files:
        try:
            data = json.loads(json_file.read_text())
            sap_name = data['sap_name']
            index['sap_list'].append(sap_name)

            # Index by indication
            indication = data.get('metadata', {}).get('indication', 'Unknown')
            if indication not in index['by_indication']:
                index['by_indication'][indication] = []
            index['by_indication'][indication].append(sap_name)

            # Index sections
            for section in data['sections']:
                title = section['title'].lower()
                number = section['number']

                # Index by section number pattern
                if number not in index['by_section_num']:
                    index['by_section_num'][number] = []
                index['by_section_num'][number].append((sap_name, section['title']))

                # Index by keywords in title
                keywords = re.findall(r'\b\w{4,}\b', title)
                for kw in keywords:
                    if kw not in index['by_keyword']:
                        index['by_keyword'][kw] = []
                    index['by_keyword'][kw].append((sap_name, number, section['title']))

        except Exception as e:
            print(f"Error indexing {json_file}: {e}")

    return index


if __name__ == '__main__':
    import sys

    # Paths
    script_dir = Path(__file__).parent
    input_dir = script_dir / 'extracted_text'
    output_dir = script_dir / 'structured'

    # Parse command line args
    force = '--force' in sys.argv

    # Parse all SAPs
    results = parse_all_saps(input_dir, output_dir, force=force)

    # Build master index
    print("\nBuilding section index...")
    index = build_section_index(output_dir)

    # Save index
    index_file = output_dir / '_section_index.json'
    index_file.write_text(json.dumps(index, indent=2))

    print(f"\nIndex saved: {index_file}")
    print(f"  - {len(index['sap_list'])} SAPs indexed")
    print(f"  - {len(index['by_keyword'])} unique keywords")
    print(f"  - {len(index['by_indication'])} indications: {list(index['by_indication'].keys())}")
