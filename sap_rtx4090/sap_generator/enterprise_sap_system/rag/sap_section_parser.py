#!/usr/bin/env python3
"""
SAP Section Parser for RAG Training Data
=========================================
Extracts and structures SAP sections for vector database indexing.

Parses ~350+ SAPs into structured sections:
- Endpoints (primary, secondary, exploratory)
- Statistical Methods
- Stratification Factors
- Safety Definitions
- Analysis Populations
- Study Design
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum


class SectionType(Enum):
    """SAP Section Types for RAG indexing"""
    ENDPOINTS = "endpoints"
    METHODS = "methods"
    STRATIFICATION = "stratification"
    SAFETY = "safety"
    POPULATIONS = "populations"
    STUDY_DESIGN = "study_design"
    MISSING_DATA = "missing_data"
    SAMPLE_SIZE = "sample_size"


class EndpointType(Enum):
    """Endpoint classification for metadata"""
    BINARY = "binary"
    CONTINUOUS = "continuous"
    TIME_TO_EVENT = "time_to_event"
    COUNT = "count"
    SAFETY = "safety"
    PK = "pk"
    COMPOSITE = "composite"
    OTHER = "other"


class TherapeuticArea(Enum):
    """Therapeutic area classification"""
    ONCOLOGY = "oncology"
    GASTROENTEROLOGY = "gastroenterology"
    RHEUMATOLOGY = "rheumatology"
    CNS_PSYCHIATRY = "cns_psychiatry"
    CARDIOVASCULAR = "cardiovascular"
    DERMATOLOGY = "dermatology"
    RESPIRATORY = "respiratory"
    INFECTIOUS = "infectious"
    METABOLIC = "metabolic"
    RARE_DISEASE = "rare_disease"
    GENERAL = "general"


@dataclass
class SAPMetadata:
    """Metadata for a parsed SAP section"""
    nct_id: str
    section_type: str
    therapeutic_area: str
    indication: str
    endpoint_type: str
    primary_endpoint: str
    response_criteria: str
    phase: str
    enrollment: int
    quality_tier: int  # 1=Full, 2=Reference, 3=Incomplete
    has_full_criteria: bool
    has_sas_code: bool
    source_file: str


@dataclass
class ParsedSection:
    """A parsed section from a SAP"""
    nct_id: str
    section_type: SectionType
    content: str
    metadata: SAPMetadata
    quality_score: float = 0.0


class SAPSectionParser:
    """
    Parses SAP documents into structured sections for RAG.
    """

    # Section detection patterns
    SECTION_PATTERNS = {
        SectionType.ENDPOINTS: [
            r'(?:PRIMARY|SECONDARY|EXPLORATORY)\s+(?:ENDPOINT|OUTCOME|ANALYSIS)',
            r'(?:^|\n)\s*(?:\d+\.?\d*\.?\d*\s+)?(?:PRIMARY|EFFICACY)\s+(?:ENDPOINT|OUTCOME)',
            r'PRIMARY\s+ANALYSIS',
            r'ENDPOINT\s+DEFINITIONS?',
            r'(?:^|\n)\s*(?:\d+\.?\d*\.?\d*\s+)?ENDPOINTS?\s*$',
        ],
        SectionType.METHODS: [
            r'STATISTICAL\s+(?:METHODS?|ANALYSIS)',
            r'ANALYSIS\s+METHODS?',
            r'(?:^|\n)\s*(?:\d+\.?\d*\.?\d*\s+)?(?:STATISTICAL|EFFICACY)\s+ANALYSIS',
            r'PRIMARY\s+EFFICACY\s+ANALYSIS',
            r'ANALYSIS\s+OF\s+(?:PRIMARY|EFFICACY)',
        ],
        SectionType.STRATIFICATION: [
            r'STRATIFICATION',
            r'RANDOMIZATION\s+(?:FACTORS?|SCHEME)',
            r'SUBGROUP\s+ANALYSIS',
            r'COVARIATES?',
        ],
        SectionType.SAFETY: [
            r'SAFETY\s+(?:ANALYSIS|ENDPOINTS?|ASSESSMENT)',
            r'ADVERSE\s+EVENTS?',
            r'TOLERABILITY',
        ],
        SectionType.POPULATIONS: [
            r'ANALYSIS\s+POPULATIONS?',
            r'(?:ITT|FAS|PP|SAFETY)\s+POPULATION',
            r'STUDY\s+POPULATIONS?',
        ],
        SectionType.STUDY_DESIGN: [
            r'STUDY\s+DESIGN',
            r'TRIAL\s+DESIGN',
            r'OVERVIEW',
            r'SYNOPSIS',
        ],
        SectionType.MISSING_DATA: [
            r'MISSING\s+DATA',
            r'IMPUTATION',
            r'SENSITIVITY\s+ANALYSIS',
        ],
        SectionType.SAMPLE_SIZE: [
            r'SAMPLE\s+SIZE',
            r'POWER\s+(?:CALCULATION|ANALYSIS)',
            r'SAMPLE\s+SIZE\s+DETERMINATION',
        ],
    }

    # Therapeutic area detection keywords
    TA_KEYWORDS = {
        TherapeuticArea.ONCOLOGY: [
            'cancer', 'tumor', 'tumour', 'carcinoma', 'sarcoma', 'lymphoma',
            'leukemia', 'melanoma', 'oncology', 'malignant', 'metastatic',
            'recist', 'nsclc', 'breast cancer', 'colorectal', 'chemotherapy',
            'immunotherapy', 'pd-1', 'pd-l1', 'checkpoint'
        ],
        TherapeuticArea.GASTROENTEROLOGY: [
            'ulcerative colitis', 'crohn', 'ibd', 'inflammatory bowel',
            'gerd', 'nash', 'nafld', 'celiac', 'gastrointestinal',
            'mayo score', 'cdai', 'endoscopic'
        ],
        TherapeuticArea.RHEUMATOLOGY: [
            'rheumatoid arthritis', 'psoriatic arthritis', 'ankylosing',
            'lupus', 'sle', 'acr20', 'acr50', 'acr70', 'das28', 'rheumat'
        ],
        TherapeuticArea.CNS_PSYCHIATRY: [
            'depression', 'anxiety', 'schizophrenia', 'bipolar', 'alzheimer',
            'parkinson', 'epilepsy', 'migraine', 'madrs', 'ham-d', 'panss',
            'psychiatr', 'neurolog', 'cns'
        ],
        TherapeuticArea.CARDIOVASCULAR: [
            'cardiovascular', 'heart failure', 'myocardial', 'stroke',
            'atrial fibrillation', 'hypertension', 'mace', 'coronary', 'cardiac'
        ],
        TherapeuticArea.DERMATOLOGY: [
            'psoriasis', 'atopic dermatitis', 'eczema', 'acne',
            'pasi', 'iga', 'easi', 'dermat', 'skin'
        ],
        TherapeuticArea.RESPIRATORY: [
            'asthma', 'copd', 'pulmonary', 'respiratory', 'fev1',
            'exacerbation', 'lung function'
        ],
        TherapeuticArea.INFECTIOUS: [
            'hiv', 'hepatitis', 'hcv', 'hbv', 'vaccine', 'antibiotic',
            'antiviral', 'infection', 'viral load'
        ],
        TherapeuticArea.METABOLIC: [
            'diabetes', 'hba1c', 'obesity', 'weight loss', 'metabolic',
            'dyslipidemia', 'ldl', 'insulin', 'sglt2', 'glp-1'
        ],
        TherapeuticArea.RARE_DISEASE: [
            'orphan', 'rare disease', 'ultra-rare', 'gene therapy',
            'enzyme replacement', 'sma', 'duchenne'
        ],
    }

    # Endpoint type detection keywords
    ENDPOINT_KEYWORDS = {
        EndpointType.BINARY: [
            'response rate', 'remission', 'responder', 'proportion',
            'percentage', 'achieving', 'acr20', 'pasi75', 'orr',
            'clinical response', 'complete response', 'partial response'
        ],
        EndpointType.CONTINUOUS: [
            'change from baseline', 'mean change', 'cfb', 'ls mean',
            'mmrm', 'ancova', 'score change', 'difference in'
        ],
        EndpointType.TIME_TO_EVENT: [
            'time to', 'survival', 'progression-free', 'overall survival',
            'pfs', 'dfs', 'efs', 'kaplan-meier', 'cox', 'hazard ratio'
        ],
        EndpointType.COUNT: [
            'number of', 'count of', 'frequency', 'episodes', 'exacerbations',
            'negative binomial', 'poisson'
        ],
        EndpointType.SAFETY: [
            'adverse events', 'safety', 'tolerability', 'aes', 'teae',
            'serious adverse', 'dose limiting'
        ],
        EndpointType.PK: [
            'pharmacokinetic', 'pk', 'auc', 'cmax', 'tmax', 'half-life',
            'clearance', 'bioavailability'
        ],
        EndpointType.COMPOSITE: [
            'composite', 'mace', 'combined endpoint', 'any of the following'
        ],
    }

    # Response criteria detection
    RESPONSE_CRITERIA = {
        'RECIST': ['recist', 'recist 1.1', 'recist criteria'],
        'irRECIST': ['irrecist', 'immune-related recist'],
        'iRECIST': ['irecist'],
        'mRECIST': ['mrecist', 'modified recist'],
        'Lugano': ['lugano', 'deauville'],
        'IMWG': ['imwg', 'international myeloma'],
        'IWG': ['iwg', 'international working group'],
        'RANO': ['rano', 'response assessment neuro-oncology'],
        'Choi': ['choi criteria'],
        'Mayo Score': ['mayo score', 'mayo clinic score'],
        'CDAI': ['cdai', "crohn's disease activity"],
        'ACR': ['acr20', 'acr50', 'acr70', 'acr response'],
        'PASI': ['pasi', 'psoriasis area'],
        'EASI': ['easi', 'eczema area'],
        'MADRS': ['madrs', 'montgomery-asberg'],
    }

    def __init__(self, data_dir: Path = None):
        """Initialize parser with data directory"""
        self.data_dir = data_dir or Path(__file__).parent.parent.parent / "data"
        self.all_pairs_dir = self.data_dir / "all_pairs"
        self.ground_truth_dir = self.data_dir / "ground_truth"
        self.output_dir = self.data_dir.parent / "rag_training_data"

    def parse_sap(self, sap_text: str, nct_id: str, source_file: str = "") -> List[ParsedSection]:
        """
        Parse a SAP into structured sections.

        Args:
            sap_text: Full SAP text
            nct_id: NCT ID of the study
            source_file: Path to source file

        Returns:
            List of ParsedSection objects
        """
        sections = []

        # Detect therapeutic area and endpoint type for metadata
        ta = self._detect_therapeutic_area(sap_text)
        endpoint_type = self._detect_endpoint_type(sap_text)
        response_criteria = self._detect_response_criteria(sap_text)
        phase = self._extract_phase(sap_text)
        enrollment = self._extract_enrollment(sap_text)
        indication = self._extract_indication(sap_text, ta)
        primary_endpoint = self._extract_primary_endpoint(sap_text)

        # Base metadata
        base_metadata = SAPMetadata(
            nct_id=nct_id,
            section_type="",  # Will be set per section
            therapeutic_area=ta.value,
            indication=indication,
            endpoint_type=endpoint_type.value,
            primary_endpoint=primary_endpoint,
            response_criteria=response_criteria,
            phase=phase,
            enrollment=enrollment,
            quality_tier=1,  # Will be calculated
            has_full_criteria=bool(response_criteria),
            has_sas_code=self._has_sas_code(sap_text),
            source_file=source_file
        )

        # Extract each section type
        for section_type in SectionType:
            content = self._extract_section(sap_text, section_type)
            if content and len(content.strip()) > 50:  # Minimum content threshold
                metadata = SAPMetadata(**asdict(base_metadata))
                metadata.section_type = section_type.value

                # Calculate quality score
                quality_score = self._calculate_quality_score(content, section_type)
                metadata.quality_tier = self._quality_score_to_tier(quality_score)

                section = ParsedSection(
                    nct_id=nct_id,
                    section_type=section_type,
                    content=content,
                    metadata=metadata,
                    quality_score=quality_score
                )
                sections.append(section)

        return sections

    def _extract_section(self, text: str, section_type: SectionType) -> str:
        """Extract a specific section from SAP text"""
        patterns = self.SECTION_PATTERNS.get(section_type, [])
        text_upper = text.upper()

        best_match = None
        best_start = len(text)

        # Find the earliest matching section
        for pattern in patterns:
            match = re.search(pattern, text_upper)
            if match and match.start() < best_start:
                best_start = match.start()
                best_match = match

        if not best_match:
            # Try to extract based on content keywords
            return self._extract_by_keywords(text, section_type)

        # Find section end (next major section or end of document)
        all_section_patterns = []
        for patterns in self.SECTION_PATTERNS.values():
            all_section_patterns.extend(patterns)

        end_pos = len(text)
        for pattern in all_section_patterns:
            match = re.search(pattern, text_upper[best_start + 1:])
            if match:
                potential_end = best_start + 1 + match.start()
                if potential_end < end_pos and potential_end > best_start + 100:
                    end_pos = potential_end

        # Extract section content
        content = text[best_start:end_pos].strip()

        # Limit to reasonable size
        if len(content) > 10000:
            content = content[:10000] + "\n... [truncated]"

        return content

    def _extract_by_keywords(self, text: str, section_type: SectionType) -> str:
        """Extract section based on content keywords when headers aren't found"""
        if section_type == SectionType.ENDPOINTS:
            # Look for outcome/endpoint descriptions
            lines = text.split('\n')
            endpoint_lines = []
            for i, line in enumerate(lines):
                if any(kw in line.lower() for kw in ['outcome:', 'endpoint:', 'primary:', 'secondary:']):
                    # Include context
                    start = max(0, i - 1)
                    end = min(len(lines), i + 5)
                    endpoint_lines.extend(lines[start:end])
            return '\n'.join(endpoint_lines)

        elif section_type == SectionType.METHODS:
            # Look for statistical method descriptions
            text_lower = text.lower()
            method_keywords = ['logistic regression', 'cox regression', 'ancova', 'mmrm',
                             'kaplan-meier', 'chi-square', 'log-rank', 'mixed model']
            for kw in method_keywords:
                if kw in text_lower:
                    idx = text_lower.find(kw)
                    start = max(0, idx - 200)
                    end = min(len(text), idx + 500)
                    return text[start:end]

        return ""

    def _detect_therapeutic_area(self, text: str) -> TherapeuticArea:
        """Detect therapeutic area from text"""
        text_lower = text.lower()
        scores = {ta: 0 for ta in TherapeuticArea}

        for ta, keywords in self.TA_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    scores[ta] += 1

        best_ta = max(scores, key=scores.get)
        return best_ta if scores[best_ta] >= 2 else TherapeuticArea.GENERAL

    def _detect_endpoint_type(self, text: str) -> EndpointType:
        """Detect primary endpoint type"""
        text_lower = text.lower()
        scores = {et: 0 for et in EndpointType}

        for et, keywords in self.ENDPOINT_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    scores[et] += 1

        best_type = max(scores, key=scores.get)
        return best_type if scores[best_type] >= 1 else EndpointType.OTHER

    def _detect_response_criteria(self, text: str) -> str:
        """Detect response criteria used"""
        text_lower = text.lower()
        detected = []

        for criteria, keywords in self.RESPONSE_CRITERIA.items():
            for kw in keywords:
                if kw in text_lower:
                    detected.append(criteria)
                    break

        return ', '.join(detected) if detected else ''

    def _extract_phase(self, text: str) -> str:
        """Extract study phase"""
        patterns = [
            r'Phase:\s*(\w+)',
            r'Phase\s+([1234IViv]+[ab]?)',
            r'PHASE\s*(\d+[AB]?)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        return 'Unknown'

    def _extract_enrollment(self, text: str) -> int:
        """Extract enrollment number"""
        patterns = [
            r'Enrollment:\s*(\d+)',
            r'N\s*=\s*(\d+)',
            r'(\d+)\s+(?:patients?|subjects?|participants?)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return 0

    def _extract_indication(self, text: str, ta: TherapeuticArea) -> str:
        """Extract indication/disease"""
        # First look for explicit indication
        patterns = [
            r'Study:\s*[^,]+,?\s*([^,]+)',
            r'(?:patients?|subjects?)\s+with\s+([^,\.]+)',
            r'(?:treatment\s+of|for)\s+([^,\.]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                indication = match.group(1).strip()
                if len(indication) < 100:
                    return indication

        # Fall back to TA-based indication
        ta_indications = {
            TherapeuticArea.ONCOLOGY: "Cancer",
            TherapeuticArea.GASTROENTEROLOGY: "Gastrointestinal Disease",
            TherapeuticArea.RHEUMATOLOGY: "Rheumatic Disease",
            TherapeuticArea.CNS_PSYCHIATRY: "CNS/Psychiatric Disorder",
            TherapeuticArea.CARDIOVASCULAR: "Cardiovascular Disease",
            TherapeuticArea.DERMATOLOGY: "Dermatological Condition",
            TherapeuticArea.RESPIRATORY: "Respiratory Disease",
            TherapeuticArea.INFECTIOUS: "Infectious Disease",
            TherapeuticArea.METABOLIC: "Metabolic Disorder",
            TherapeuticArea.RARE_DISEASE: "Rare Disease",
        }
        return ta_indications.get(ta, "Not specified")

    def _extract_primary_endpoint(self, text: str) -> str:
        """Extract primary endpoint description"""
        patterns = [
            r'PRIMARY\s+(?:ENDPOINT|OUTCOME).*?:\s*([^\n]+)',
            r'(?:primary|main)\s+(?:efficacy\s+)?(?:endpoint|outcome)\s+(?:is|will be)\s+([^\n\.]+)',
            r'Outcome:\s*([^\n]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                endpoint = match.group(1).strip()
                if len(endpoint) < 200:
                    return endpoint

        return "Not specified"

    def _has_sas_code(self, text: str) -> bool:
        """Check if SAP contains SAS code examples"""
        sas_indicators = ['proc ', 'data ', 'run;', 'quit;', 'proc logistic',
                         'proc phreg', 'proc mixed', 'proc genmod']
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in sas_indicators)

    def _calculate_quality_score(self, content: str, section_type: SectionType) -> float:
        """Calculate quality score for a section (0-100)"""
        score = 0.0
        content_lower = content.lower()

        # Base score for content length
        if len(content) > 500:
            score += 20
        elif len(content) > 200:
            score += 10

        # Section-specific quality indicators
        if section_type == SectionType.ENDPOINTS:
            quality_indicators = [
                ('primary', 10), ('secondary', 5), ('definition', 10),
                ('timepoint', 10), ('week', 5), ('day', 5),
                ('response', 10), ('remission', 10), ('survival', 10),
            ]
        elif section_type == SectionType.METHODS:
            quality_indicators = [
                ('regression', 10), ('ancova', 10), ('mmrm', 10),
                ('cox', 10), ('kaplan-meier', 10), ('log-rank', 10),
                ('confidence interval', 10), ('hypothesis', 5),
                ('proc ', 15), ('model', 10),
            ]
        elif section_type == SectionType.STRATIFICATION:
            quality_indicators = [
                ('stratif', 15), ('randomiz', 10), ('factor', 10),
                ('covariate', 10), ('subgroup', 10), ('region', 5),
                ('baseline', 10), ('prior', 5),
            ]
        elif section_type == SectionType.SAFETY:
            quality_indicators = [
                ('adverse', 15), ('serious', 10), ('teae', 10),
                ('discontinuation', 10), ('severity', 10),
                ('medical dictionary', 5), ('meddra', 10),
            ]
        else:
            quality_indicators = [
                ('population', 10), ('criteria', 10), ('definition', 10),
            ]

        for indicator, points in quality_indicators:
            if indicator in content_lower:
                score += points

        return min(score, 100)

    def _quality_score_to_tier(self, score: float) -> int:
        """Convert quality score to tier (1=Best, 3=Worst)"""
        if score >= 60:
            return 1  # Full quality
        elif score >= 30:
            return 2  # Reference quality
        else:
            return 3  # Incomplete

    def process_all_saps(self, max_saps: int = None) -> Dict[str, List[ParsedSection]]:
        """
        Process all SAPs in the data directories.

        Returns:
            Dictionary mapping section_type to list of ParsedSection
        """
        all_sections = {st.value: [] for st in SectionType}

        # Process all_pairs directory
        sap_files = list(self.all_pairs_dir.glob("*_sap.txt"))

        # Process ground_truth directory
        sap_files.extend(list(self.ground_truth_dir.glob("*_sap.txt")))

        # Deduplicate by NCT ID
        seen_ncts = set()
        unique_files = []
        for f in sap_files:
            nct_id = f.stem.replace("_sap", "")
            if nct_id not in seen_ncts:
                seen_ncts.add(nct_id)
                unique_files.append(f)

        if max_saps:
            unique_files = unique_files[:max_saps]

        print(f"Processing {len(unique_files)} unique SAPs...")

        for i, sap_file in enumerate(unique_files):
            nct_id = sap_file.stem.replace("_sap", "")

            try:
                sap_text = sap_file.read_text(encoding='utf-8', errors='ignore')
                sections = self.parse_sap(sap_text, nct_id, str(sap_file))

                for section in sections:
                    all_sections[section.section_type.value].append(section)

                if (i + 1) % 50 == 0:
                    print(f"  Processed {i + 1}/{len(unique_files)} SAPs...")

            except Exception as e:
                print(f"  Error processing {nct_id}: {e}")

        # Summary
        print("\nSection extraction summary:")
        for section_type, sections in all_sections.items():
            tier_counts = {1: 0, 2: 0, 3: 0}
            for s in sections:
                tier_counts[s.metadata.quality_tier] += 1
            print(f"  {section_type}: {len(sections)} total "
                  f"(T1: {tier_counts[1]}, T2: {tier_counts[2]}, T3: {tier_counts[3]})")

        return all_sections

    def save_sections_for_rag(self, sections_dict: Dict[str, List[ParsedSection]]):
        """
        Save parsed sections to files for RAG indexing.

        Creates:
        - rag_training_data/{section_type}/{nct_id}_{section_type}.txt
        - rag_training_data/metadata/{nct_id}_{section_type}.json
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        metadata_dir = self.output_dir / "metadata"
        metadata_dir.mkdir(exist_ok=True)

        total_saved = 0

        for section_type, sections in sections_dict.items():
            section_dir = self.output_dir / section_type
            section_dir.mkdir(exist_ok=True)

            for section in sections:
                # Only save Tier 1 and Tier 2 sections
                if section.metadata.quality_tier > 2:
                    continue

                # Save content
                content_file = section_dir / f"{section.nct_id}_{section_type}.txt"
                content_file.write_text(section.content, encoding='utf-8')

                # Save metadata
                metadata_file = metadata_dir / f"{section.nct_id}_{section_type}.json"
                metadata_dict = asdict(section.metadata)
                metadata_dict['quality_score'] = section.quality_score
                metadata_file.write_text(
                    json.dumps(metadata_dict, indent=2),
                    encoding='utf-8'
                )

                total_saved += 1

        print(f"\nSaved {total_saved} sections for RAG training")
        return total_saved


def create_sap_parser(data_dir: Path = None) -> SAPSectionParser:
    """Factory function to create SAP parser"""
    return SAPSectionParser(data_dir)


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Parse SAPs for RAG training")
    parser.add_argument("--max-saps", type=int, default=None, help="Maximum SAPs to process")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory")
    args = parser.parse_args()

    sap_parser = create_sap_parser()
    if args.output_dir:
        sap_parser.output_dir = Path(args.output_dir)

    print("="*60)
    print("SAP SECTION PARSER FOR RAG TRAINING")
    print("="*60)

    sections = sap_parser.process_all_saps(max_saps=args.max_saps)
    saved = sap_parser.save_sections_for_rag(sections)

    print(f"\nDone! Saved {saved} sections to {sap_parser.output_dir}")
