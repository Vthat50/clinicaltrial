#!/usr/bin/env python3
"""
Parse Specialized SAPs into RAG Training Format
================================================

Extracts sections from downloaded SAP PDFs and saves them in the format
expected by the RAG training pipeline.

Sections extracted:
- endpoints (primary, secondary, exploratory)
- methods (statistical methods, analysis approach)
- safety (adverse events, safety populations)
- populations (ITT, PP, Safety, FAS)
- sample_size (power calculations, assumptions)
- missing_data (imputation, sensitivity analyses)
- stratification (randomization, stratification factors)
- study_design (design overview, treatment arms)

Special handling for:
- Immunotherapy trials (Fleming-Harrington, NPH, delayed effect)
- Interim analysis (Lan-DeMets, O'Brien-Fleming, alpha spending)
- PRO endpoints (LCSS, QoL instruments)
- Consistency/bridging studies
"""

import os
import sys
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

# Try to import PDF parsing library
try:
    import fitz  # PyMuPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("Warning: PyMuPDF not installed. Run: pip install PyMuPDF")


@dataclass
class ExtractedSection:
    """Extracted section from SAP."""
    section_type: str
    content: str
    nct_id: str
    therapeutic_area: str = "oncology"
    endpoint_type: str = "efficacy"
    phase: str = "PHASE3"
    features: List[str] = field(default_factory=list)
    quality_tier: int = 1  # 1=high (specialized), 2=medium, 3=low
    confidence: float = 0.9


# Section detection patterns
SECTION_PATTERNS = {
    "endpoints": [
        r"(?i)(primary\s+endpoint|primary\s+objective|primary\s+efficacy)",
        r"(?i)(secondary\s+endpoint|secondary\s+objective)",
        r"(?i)(exploratory\s+endpoint|exploratory\s+objective)",
        r"(?i)(endpoint\s+definition|definition\s+of\s+endpoint)",
        r"(?i)(co-primary\s+endpoint)",
    ],
    "methods": [
        r"(?i)(statistical\s+method|analysis\s+method)",
        r"(?i)(primary\s+analysis|primary\s+statistical)",
        r"(?i)(log-rank|cox\s+regression|kaplan-meier)",
        r"(?i)(fleming.harrington|weighted\s+log.rank)",
        r"(?i)(stratified\s+analysis|stratification)",
        r"(?i)(non-proportional\s+hazard|delayed\s+effect)",
        r"(?i)(interim\s+analysis|alpha\s+spending)",
        r"(?i)(lan.demets|o.brien.fleming|pocock)",
        r"(?i)(hierarchical\s+testing|gatekeeping)",
        r"(?i)(consistency\s+analysis|bridging)",
    ],
    "safety": [
        r"(?i)(safety\s+analysis|safety\s+endpoint)",
        r"(?i)(adverse\s+event|teae|treatment.emergent)",
        r"(?i)(serious\s+adverse|sae)",
        r"(?i)(dose.limiting\s+toxicity|dlt)",
        r"(?i)(ctcae|common\s+terminology)",
    ],
    "populations": [
        r"(?i)(analysis\s+population|study\s+population)",
        r"(?i)(intent.to.treat|itt\s+population)",
        r"(?i)(per.protocol|pp\s+population)",
        r"(?i)(safety\s+population|treated\s+population)",
        r"(?i)(full\s+analysis\s+set|fas)",
        r"(?i)(modified\s+itt|mitt)",
    ],
    "sample_size": [
        r"(?i)(sample\s+size|power\s+calculation)",
        r"(?i)(power\s+analysis|statistical\s+power)",
        r"(?i)(type\s+i\s+error|alpha\s+level)",
        r"(?i)(hazard\s+ratio\s+assumption)",
        r"(?i)(event.driven|number\s+of\s+events)",
    ],
    "missing_data": [
        r"(?i)(missing\s+data|missing\s+value)",
        r"(?i)(imputation|multiple\s+imputation)",
        r"(?i)(sensitivity\s+analysis|tipping\s+point)",
        r"(?i)(last\s+observation|locf|bocf)",
        r"(?i)(pattern\s+mixture|selection\s+model)",
    ],
    "stratification": [
        r"(?i)(stratification\s+factor|randomization\s+factor)",
        r"(?i)(stratified\s+by|stratified\s+according)",
        r"(?i)(randomization\s+scheme|block\s+randomization)",
        r"(?i)(interactive\s+response|ixrs|ivrs)",
    ],
    "study_design": [
        r"(?i)(study\s+design|trial\s+design)",
        r"(?i)(treatment\s+arm|study\s+arm)",
        r"(?i)(randomized|randomization\s+ratio)",
        r"(?i)(open.label|double.blind|single.blind)",
        r"(?i)(phase\s+[123]|pivotal\s+study)",
    ],
    "interim_analysis": [
        r"(?i)(interim\s+analysis|interim\s+look)",
        r"(?i)(data\s+monitoring\s+committee|dmc|dsmb)",
        r"(?i)(alpha\s+spending|error\s+spending)",
        r"(?i)(lan.demets|o.brien.fleming|pocock|haybittle)",
        r"(?i)(stopping\s+boundary|stopping\s+rule)",
        r"(?i)(information\s+fraction|timing\s+of\s+interim)",
        r"(?i)(futility|efficacy\s+boundary)",
    ],
    "pro_endpoints": [
        r"(?i)(patient.reported\s+outcome|pro\s+endpoint)",
        r"(?i)(quality\s+of\s+life|qol|hrqol)",
        r"(?i)(lcss|lung\s+cancer\s+symptom)",
        r"(?i)(eortc|qlq.c30|eq.5d|sf.36)",
        r"(?i)(symptom\s+deterioration|symptom\s+burden)",
        r"(?i)(responder\s+definition|mcid|clinically\s+meaningful)",
    ],
}

# Special feature detection patterns
FEATURE_PATTERNS = {
    "fleming_harrington": [
        r"(?i)fleming.harrington",
        r"(?i)weighted\s+log.rank.*g\s*\(\s*\d",
        r"(?i)rho\s*=\s*0.*gamma\s*=\s*1",
        r"(?i)g\s*\(\s*0\s*,\s*1\s*\)",
    ],
    "non_proportional_hazards": [
        r"(?i)non.proportional\s+hazard",
        r"(?i)delayed\s+(treatment\s+)?effect",
        r"(?i)piecewise\s+exponential",
        r"(?i)cure\s+model",
        r"(?i)lag\s+phase",
    ],
    "interim_analysis": [
        r"(?i)interim\s+analysis",
        r"(?i)alpha\s+spending",
        r"(?i)lan.demets",
        r"(?i)o.brien.fleming",
        r"(?i)information\s+fraction",
    ],
    "hierarchical_testing": [
        r"(?i)hierarchical\s+testing",
        r"(?i)gatekeeping",
        r"(?i)fixed.sequence",
        r"(?i)testing\s+hierarchy",
    ],
    "consistency_bridging": [
        r"(?i)consistency\s+(analysis|objective|check)",
        r"(?i)bridging\s+study",
        r"(?i)regional\s+(difference|consistency)",
        r"(?i)china|japan|asia",
    ],
    "pro_qol": [
        r"(?i)patient.reported",
        r"(?i)quality\s+of\s+life",
        r"(?i)hrqol",
        r"(?i)lcss|eortc|eq.5d",
    ],
    "immunotherapy": [
        r"(?i)nivolumab|pembrolizumab|atezolizumab|durvalumab|avelumab|ipilimumab",
        r"(?i)checkpoint\s+inhibitor",
        r"(?i)pd.1|pd.l1|ctla.4",
        r"(?i)immuno.oncology|immunotherapy",
    ],
}


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from PDF using PyMuPDF."""
    if not PDF_AVAILABLE:
        raise ImportError("PyMuPDF not installed")

    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text()
        doc.close()
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {e}")

    return text


def detect_features(text: str) -> List[str]:
    """Detect special features in the SAP text."""
    features = []

    for feature, patterns in FEATURE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text):
                features.append(feature)
                break

    return list(set(features))


def extract_nct_id(text: str, filename: str) -> str:
    """Extract NCT ID from text or filename."""
    # Try filename first
    match = re.search(r"NCT\d{8}", filename)
    if match:
        return match.group(0)

    # Try text
    match = re.search(r"NCT\d{8}", text)
    if match:
        return match.group(0)

    return "UNKNOWN"


def extract_sections(text: str, nct_id: str, features: List[str]) -> List[ExtractedSection]:
    """Extract sections from SAP text."""
    sections = []

    # Split text into paragraphs
    paragraphs = text.split('\n\n')

    # Track current section
    current_section = None
    current_content = []

    for para in paragraphs:
        para = para.strip()
        if not para or len(para) < 20:
            continue

        # Check for section headers
        detected_section = None
        for section_type, patterns in SECTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, para[:500]):  # Check first 500 chars
                    detected_section = section_type
                    break
            if detected_section:
                break

        if detected_section:
            # Save previous section
            if current_section and current_content:
                content = '\n\n'.join(current_content)
                if len(content) > 100:  # Minimum content length
                    sections.append(ExtractedSection(
                        section_type=current_section,
                        content=content[:15000],  # Limit content length
                        nct_id=nct_id,
                        features=features,
                    ))

            current_section = detected_section
            current_content = [para]
        elif current_section:
            current_content.append(para)

    # Save last section
    if current_section and current_content:
        content = '\n\n'.join(current_content)
        if len(content) > 100:
            sections.append(ExtractedSection(
                section_type=current_section,
                content=content[:15000],
                nct_id=nct_id,
                features=features,
            ))

    return sections


def extract_specific_content(text: str, section_type: str) -> Optional[str]:
    """Extract specific section content using regex."""
    patterns = SECTION_PATTERNS.get(section_type, [])

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Get surrounding context (up to 5000 chars after match)
            start = max(0, match.start() - 200)
            end = min(len(text), match.end() + 5000)
            return text[start:end]

    return None


def process_pdf(pdf_path: Path, category: str) -> List[ExtractedSection]:
    """Process a single PDF and extract sections."""
    print(f"  Processing: {pdf_path.name}")

    try:
        text = extract_text_from_pdf(pdf_path)
    except Exception as e:
        print(f"    ✗ Failed to extract text: {e}")
        return []

    if len(text) < 500:
        print(f"    ✗ Insufficient text extracted")
        return []

    # Extract NCT ID
    nct_id = extract_nct_id(text, pdf_path.name)

    # Detect features
    features = detect_features(text)
    features.append(category)  # Add category as feature
    print(f"    Features: {features}")

    # Extract sections
    sections = extract_sections(text, nct_id, features)

    # Also try targeted extraction for key sections
    for section_type in ["methods", "endpoints", "interim_analysis", "pro_endpoints"]:
        content = extract_specific_content(text, section_type)
        if content and len(content) > 200:
            # Check if we already have this section
            existing = [s for s in sections if s.section_type == section_type]
            if not existing:
                sections.append(ExtractedSection(
                    section_type=section_type,
                    content=content[:15000],
                    nct_id=nct_id,
                    features=features,
                ))

    print(f"    Extracted {len(sections)} sections")
    return sections


def save_sections(sections: List[ExtractedSection], output_dir: Path):
    """Save extracted sections to RAG training format."""
    for section in sections:
        # Create section directory
        section_dir = output_dir / section.section_type
        section_dir.mkdir(parents=True, exist_ok=True)

        # Create metadata directory
        metadata_dir = output_dir / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)

        # Filename
        filename = f"{section.nct_id}_{section.section_type}"

        # Add feature suffix for specialized content
        if "fleming_harrington" in section.features:
            filename += "_FH"
        if "interim_analysis" in section.features:
            filename += "_IA"
        if "pro_qol" in section.features:
            filename += "_PRO"

        # Save content
        content_path = section_dir / f"{filename}.txt"

        # Add header with metadata
        header = f"""STATISTICAL ANALYSIS PLAN
NCT ID: {section.nct_id}
Section: {section.section_type.upper()}
Features: {', '.join(section.features)}
Quality Tier: {section.quality_tier} (Specialized)

---

"""
        with open(content_path, 'w', encoding='utf-8') as f:
            f.write(header + section.content)

        # Save metadata
        metadata_path = metadata_dir / f"{filename}.json"
        metadata = {
            "nct_id": section.nct_id,
            "section_type": section.section_type,
            "therapeutic_area": section.therapeutic_area,
            "endpoint_type": section.endpoint_type,
            "phase": section.phase,
            "features": section.features,
            "quality_tier": section.quality_tier,
            "confidence": section.confidence,
            "specialized": True,
        }
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)


def process_all_pdfs(input_dir: Path, output_dir: Path):
    """Process all PDFs in input directory."""
    all_sections = []

    for category in ["immunotherapy", "interim_analysis", "pro_endpoints", "methodology"]:
        category_dir = input_dir / category
        if not category_dir.exists():
            print(f"\n⊘ Skipping {category} (directory not found)")
            continue

        print(f"\n{'='*60}")
        print(f"Processing: {category.upper()}")
        print(f"{'='*60}")

        pdf_files = list(category_dir.glob("*.pdf"))
        print(f"  Found {len(pdf_files)} PDF files")

        for pdf_path in pdf_files:
            sections = process_pdf(pdf_path, category)
            all_sections.extend(sections)

    # Save all sections
    print(f"\n{'='*60}")
    print(f"SAVING SECTIONS")
    print(f"{'='*60}")

    save_sections(all_sections, output_dir)

    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")

    section_counts = {}
    for section in all_sections:
        section_counts[section.section_type] = section_counts.get(section.section_type, 0) + 1

    for section_type, count in sorted(section_counts.items()):
        print(f"  {section_type}: {count} sections")

    print(f"\n  TOTAL: {len(all_sections)} sections extracted")
    print(f"  Output: {output_dir}")


if __name__ == "__main__":
    script_dir = Path(__file__).parent
    default_input = script_dir.parent / "rag_training_data" / "specialized_saps"
    default_output = script_dir.parent / "rag_training_data"

    input_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else default_input
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else default_output

    if not input_dir.exists():
        print(f"Input directory not found: {input_dir}")
        print(f"Run download_specialized_saps.py first")
        sys.exit(1)

    print(f"Input: {input_dir}")
    print(f"Output: {output_dir}")

    process_all_pdfs(input_dir, output_dir)

    print(f"\nNext step: Run index_rag.py to rebuild the vector index")
