#!/usr/bin/env python3
"""
SAP RAG System (3-Collection Architecture)
==========================================

Three specialized collections:
1. sap_structure - SAP outlines/table of contents
2. sap_content - SAP section content chunks
3. sap_tlf - TLF (Table/Listing/Figure) shells

Integrated with:
- LlamaParse for PDF extraction
- FactExtractor for tiered protocol extraction (43 fields)
- KnowledgeRuleEngine for scientific context (99 rules)
- GraphRAG for domain knowledge
"""

import os
import re
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

# Vector DB
import chromadb
from chromadb.utils import embedding_functions

# LLM for generation - use OpenAI if available
if os.environ.get('OPENAI_API_KEY'):
    from openai import OpenAI
    _USE_OPENAI = True
else:
    from anthropic import Anthropic
    _USE_OPENAI = False


# =============================================================================
# CONFIGURATION
# =============================================================================

CHROMA_DB_PATH = "./chroma_db/sap_rag_3col"

COLLECTION_STRUCTURE = "sap_structure"
COLLECTION_CONTENT = "sap_content"
COLLECTION_TLF = "sap_tlf"

# Section patterns for content classification
CONTENT_SECTION_PATTERNS = {
    "introduction": [r"introduction", r"background"],
    "objectives_endpoints": [r"study\s*objectives", r"primary\s*endpoint", r"endpoints"],
    "study_design": [r"study\s*design", r"trial\s*design"],
    "sample_size": [r"sample\s*size", r"power\s*calculation", r"power\s*and\s*sample"],
    "analysis_populations": [r"analysis\s*populations", r"analysis\s*sets", r"intent.to.treat"],
    "statistical_methods": [r"statistical\s*(?:methods|analysis)", r"general\s*statistical"],
    "efficacy_analysis": [r"efficacy\s*analysis", r"primary\s*efficacy"],
    "safety_analysis": [r"safety\s*analysis", r"adverse\s*events"],
    "missing_data": [r"missing\s*data", r"handling\s*of\s*missing"],
    "sensitivity_analysis": [r"sensitivity\s*analysis"],
    "interim_analysis": [r"interim\s*analysis"],
    "multiplicity": [r"multiplicity", r"multiple\s*comparison"],
    "subgroup_analysis": [r"subgroup\s*analysis"],
    "pharmacokinetics": [r"pharmacokinetic", r"pk\s*analysis"],
}

TLF_PATTERNS = {
    "demographics": [r"demographic", r"baseline\s*character"],
    "disposition": [r"disposition", r"patient\s*flow"],
    "efficacy_tte": [r"kaplan.meier", r"survival", r"time.to.event", r"PFS", r"OS"],
    "efficacy_binary": [r"response\s*rate", r"ORR", r"responder"],
    "safety_ae": [r"adverse\s*event", r"TEAE", r"treatment.emergent"],
    "safety_lab": [r"laboratory", r"hematolog", r"chemistry"],
    "pk": [r"concentration", r"pharmacokinetic", r"AUC", r"Cmax"],
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class SAPStructure:
    """SAP table of contents / outline."""
    structure_id: str
    nct_id: str
    source_file: str
    phase: str
    endpoint_type: str
    design: str
    indication: str
    sections: List[Dict]
    section_count: int
    has_interim: bool
    has_multiplicity: bool
    structure_text: str


@dataclass
class SAPContent:
    """SAP content chunk."""
    chunk_id: str
    nct_id: str
    source_file: str
    section_type: str
    content: str
    phase: str
    endpoint_type: str


@dataclass
class SAPTlf:
    """TLF shell."""
    tlf_id: str
    nct_id: str
    source_file: str
    tlf_type: str  # Table, Figure, Listing
    tlf_number: str
    tlf_title: str
    category: str
    content: str
    phase: str


# =============================================================================
# SAP PARSER (LlamaParse)
# =============================================================================

class SAPParser:
    """Parse SAP PDFs using LlamaParse."""

    def __init__(self):
        from .section_parser import ProtocolSectionParser
        self.parser = ProtocolSectionParser()

    def parse_sap(self, pdf_path: str) -> str:
        """Extract full text from SAP PDF."""
        result = self.parser.parse("", pdf_path=pdf_path)
        return result.raw_text or ""

    def detect_characteristics(self, text: str) -> Dict[str, Any]:
        """Detect trial characteristics from SAP text."""
        text_lower = text.lower()

        # Phase detection
        phase = "Unknown"
        if re.search(r'phase\s*3|phase\s*iii', text_lower):
            phase = "Phase 3"
        elif re.search(r'phase\s*2|phase\s*ii', text_lower):
            phase = "Phase 2"
        elif re.search(r'phase\s*1b|phase\s*ib', text_lower):
            phase = "Phase 1b"
        elif re.search(r'phase\s*1|phase\s*i', text_lower):
            phase = "Phase 1"

        # Endpoint type detection
        endpoint_type = "Unknown"
        if re.search(r'overall\s*survival|progression.free|time.to.event|PFS|OS\b', text_lower):
            endpoint_type = "Time-to-Event"
        elif re.search(r'response\s*rate|ORR|objective\s*response|binary', text_lower):
            endpoint_type = "Binary"
        elif re.search(r'dose.limiting|MTD|DLT', text_lower):
            endpoint_type = "Safety/DLT"

        # Design detection
        design = "Unknown"
        if re.search(r'randomized|randomisation', text_lower):
            design = "Randomized"
        elif re.search(r'single.arm', text_lower):
            design = "Single-Arm"
        elif re.search(r'3\+3|dose.escalation', text_lower):
            design = "Dose-Escalation"

        # Indication detection
        indication = "Oncology"
        indications = {
            "NSCLC": [r'non.small\s*cell\s*lung', r'\bnsclc\b'],
            "Breast Cancer": [r'breast\s*cancer'],
            "Ovarian Cancer": [r'ovarian\s*cancer'],
            "RCC": [r'renal\s*cell', r'\brcc\b'],
            "Gastric Cancer": [r'gastric\s*cancer'],
            "Melanoma": [r'melanoma'],
            "CRC": [r'colorectal', r'\bcrc\b'],
        }
        for ind, patterns in indications.items():
            if any(re.search(p, text_lower) for p in patterns):
                indication = ind
                break

        return {
            "phase": phase,
            "endpoint_type": endpoint_type,
            "design": design,
            "indication": indication,
            "has_interim": bool(re.search(r'interim\s*analysis', text_lower)),
            "has_multiplicity": bool(re.search(r'multiplicity', text_lower)),
        }


# =============================================================================
# EXTRACTION FUNCTIONS
# =============================================================================

def extract_nct_id(filename: str) -> str:
    """Extract NCT ID from filename."""
    match = re.search(r'(NCT\d+)', filename, re.IGNORECASE)
    return match.group(1).upper() if match else "UNKNOWN"


def identify_section_type(text: str) -> str:
    """Identify section type from text content."""
    text_lower = text.lower()[:500]
    for section_name, patterns in CONTENT_SECTION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return section_name
    return "general"


def detect_tlf_category(text: str) -> str:
    """Detect TLF category from content."""
    text_lower = text.lower()
    for category, patterns in TLF_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return category
    return "general"


def extract_structure(full_text: str, nct_id: str, source_file: str, chars: Dict) -> SAPStructure:
    """Extract SAP structure (table of contents)."""
    sections = []
    section_pattern = re.compile(r'^(\d+\.?\d*\.?\d*)\s+([A-Z][A-Za-z\s\-/&]+)', re.MULTILINE)

    for match in section_pattern.finditer(full_text):
        num = match.group(1).strip('.')
        title = match.group(2).strip()
        level = num.count('.') + 1 if '.' in num else 1
        sections.append({"number": num, "title": title, "level": level})

    # Build structure text
    structure_text = f"SAP Structure for {nct_id}\n"
    structure_text += f"Phase: {chars['phase']} | Endpoint: {chars['endpoint_type']} | Design: {chars['design']}\n\n"
    for sec in sections:
        indent = "  " * (sec['level'] - 1)
        structure_text += f"{indent}{sec['number']} {sec['title']}\n"

    return SAPStructure(
        structure_id=f"{nct_id}_structure",
        nct_id=nct_id,
        source_file=source_file,
        phase=chars["phase"],
        endpoint_type=chars["endpoint_type"],
        design=chars["design"],
        indication=chars["indication"],
        sections=sections,
        section_count=len(sections),
        has_interim=chars["has_interim"],
        has_multiplicity=chars["has_multiplicity"],
        structure_text=structure_text,
    )


def extract_content_chunks(full_text: str, nct_id: str, source_file: str, chars: Dict,
                           chunk_size: int = 1500, overlap: int = 150) -> List[SAPContent]:
    """Extract content chunks from SAP."""
    chunks = []
    text = re.sub(r'\s+', ' ', full_text).strip()
    start = 0
    chunk_num = 0

    while start < len(text):
        end = start + chunk_size
        chunk_text = text[start:end]

        # Try to break at sentence boundary
        if end < len(text):
            last_period = chunk_text.rfind('. ')
            if last_period > chunk_size * 0.7:
                chunk_text = chunk_text[:last_period + 1]
                end = start + last_period + 1

        section_type = identify_section_type(chunk_text)

        chunk = SAPContent(
            chunk_id=f"{nct_id}_content_{chunk_num}",
            nct_id=nct_id,
            source_file=source_file,
            section_type=section_type,
            content=chunk_text.strip(),
            phase=chars["phase"],
            endpoint_type=chars["endpoint_type"],
        )
        chunks.append(chunk)
        start = end - overlap
        chunk_num += 1

    return chunks


def extract_tlf_shells(full_text: str, nct_id: str, source_file: str, chars: Dict) -> List[SAPTlf]:
    """Extract TLF shells from SAP."""
    shells = []
    # Match Table/Figure/Listing with number and capture the title on same line
    tlf_markers = list(re.finditer(
        r'(Table|Figure|Listing)[-_\s]*(\d+\.?\d*\.?\d*)[\s:\-]*([^\n\r|]{0,150})',
        full_text, re.IGNORECASE
    ))

    for i, marker in enumerate(tlf_markers):
        start = marker.start()
        end = min(start + 2000, tlf_markers[i+1].start() if i+1 < len(tlf_markers) else len(full_text))

        tlf_text = full_text[start:end].strip()
        if len(tlf_text) < 50:
            continue

        # Determine TLF type
        marker_text = marker.group(1).lower()
        if 'figure' in marker_text:
            tlf_type = "Figure"
        elif 'listing' in marker_text:
            tlf_type = "Listing"
        else:
            tlf_type = "Table"

        # Extract title from the captured group or first line
        raw_title = marker.group(3).strip() if marker.group(3) else ""
        if not raw_title or len(raw_title) < 5:
            # Fallback: get first line after the marker
            first_line = tlf_text.split('\n')[0]
            # Remove the marker part to get just the title
            title_match = re.search(r'(?:Table|Figure|Listing)[-_\s]*\d+\.?\d*\.?\d*[\s:\-]*(.*)', first_line, re.IGNORECASE)
            raw_title = title_match.group(1).strip() if title_match else first_line[:100]

        # Clean up title
        tlf_title = re.sub(r'\s+', ' ', raw_title).strip()
        if not tlf_title:
            tlf_title = f"{tlf_type} {marker.group(2)}"

        shell = SAPTlf(
            tlf_id=f"{nct_id}_tlf_{i}",
            nct_id=nct_id,
            source_file=source_file,
            tlf_type=tlf_type,
            tlf_number=marker.group(2) or "unknown",
            tlf_title=tlf_title[:200],
            category=detect_tlf_category(tlf_text),
            content=tlf_text,
            phase=chars["phase"],
        )
        shells.append(shell)

    return shells


# =============================================================================
# 3-COLLECTION RAG INDEX
# =============================================================================

class SAPRAGIndex:
    """3-collection RAG index for SAPs."""

    def __init__(self, db_path: str = CHROMA_DB_PATH):
        """Initialize the 3-collection RAG index."""
        self.db_path = db_path
        os.makedirs(db_path, exist_ok=True)

        # Use sentence-transformers (free, local)
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(path=db_path)

        # 3 collections
        self.structure_collection = self.client.get_or_create_collection(
            name=COLLECTION_STRUCTURE,
            embedding_function=self.embedding_fn,
            metadata={"description": "SAP structure/outlines"}
        )
        self.content_collection = self.client.get_or_create_collection(
            name=COLLECTION_CONTENT,
            embedding_function=self.embedding_fn,
            metadata={"description": "SAP content chunks"}
        )
        self.tlf_collection = self.client.get_or_create_collection(
            name=COLLECTION_TLF,
            embedding_function=self.embedding_fn,
            metadata={"description": "TLF shells"}
        )

        self.parser = SAPParser()

    def index_sap_folder(self, folder_path: str) -> Dict[str, int]:
        """Index all SAP PDFs in a folder into 3 collections."""
        folder = Path(folder_path)
        sap_files = list(folder.glob("*SAP*.pdf")) + list(folder.glob("*sap*.pdf"))

        print(f"[RAG] Found {len(sap_files)} SAP files to index")

        stats = {"structure": 0, "content": 0, "tlf": 0}

        for sap_path in sap_files:
            nct_id = extract_nct_id(sap_path.name)
            print(f"\n[RAG] Processing: {sap_path.name} ({nct_id})")

            try:
                # Parse SAP
                full_text = self.parser.parse_sap(str(sap_path))
                if not full_text:
                    print(f"  [!] No text extracted")
                    continue

                # Detect characteristics
                chars = self.parser.detect_characteristics(full_text)
                print(f"  Phase: {chars['phase']} | Endpoint: {chars['endpoint_type']} | Design: {chars['design']}")

                # Extract and index structure
                structure = extract_structure(full_text, nct_id, sap_path.name, chars)
                self._add_structure(structure)
                stats["structure"] += 1
                print(f"  [+] Structure: {structure.section_count} sections")

                # Extract and index content chunks
                chunks = extract_content_chunks(full_text, nct_id, sap_path.name, chars)
                self._add_content(chunks)
                stats["content"] += len(chunks)
                print(f"  [+] Content: {len(chunks)} chunks")

                # Extract and index TLF shells
                tlfs = extract_tlf_shells(full_text, nct_id, sap_path.name, chars)
                self._add_tlfs(tlfs)
                stats["tlf"] += len(tlfs)
                print(f"  [+] TLF: {len(tlfs)} shells")

            except Exception as e:
                import traceback
                print(f"  [!] Error: {e}")
                traceback.print_exc()
                continue

        print(f"\n[RAG] COMPLETE:")
        print(f"  Structures: {stats['structure']}")
        print(f"  Content chunks: {stats['content']}")
        print(f"  TLF shells: {stats['tlf']}")

        return stats

    def _add_structure(self, structure: SAPStructure):
        """Add structure to collection."""
        existing = self.structure_collection.get(ids=[structure.structure_id])
        if existing["ids"]:
            return

        self.structure_collection.add(
            ids=[structure.structure_id],
            documents=[structure.structure_text],
            metadatas=[{
                "nct_id": structure.nct_id,
                "source_file": structure.source_file,
                "phase": structure.phase,
                "endpoint_type": structure.endpoint_type,
                "design": structure.design,
                "indication": structure.indication,
                "section_count": structure.section_count,
                "has_interim": structure.has_interim,
                "has_multiplicity": structure.has_multiplicity,
                "sections_json": json.dumps(structure.sections),
            }]
        )

    def _add_content(self, chunks: List[SAPContent]):
        """Add content chunks to collection."""
        for chunk in chunks:
            existing = self.content_collection.get(ids=[chunk.chunk_id])
            if existing["ids"]:
                continue

            self.content_collection.add(
                ids=[chunk.chunk_id],
                documents=[chunk.content],
                metadatas=[{
                    "nct_id": chunk.nct_id,
                    "source_file": chunk.source_file,
                    "section_type": chunk.section_type,
                    "phase": chunk.phase,
                    "endpoint_type": chunk.endpoint_type,
                }]
            )

    def _add_tlfs(self, tlfs: List[SAPTlf]):
        """Add TLF shells to collection."""
        for tlf in tlfs:
            existing = self.tlf_collection.get(ids=[tlf.tlf_id])
            if existing["ids"]:
                continue

            self.tlf_collection.add(
                ids=[tlf.tlf_id],
                documents=[tlf.content],
                metadatas=[{
                    "nct_id": tlf.nct_id,
                    "source_file": tlf.source_file,
                    "tlf_type": tlf.tlf_type,
                    "tlf_number": tlf.tlf_number,
                    "tlf_title": tlf.tlf_title,
                    "category": tlf.category,
                    "phase": tlf.phase,
                }]
            )

    # =========================================================================
    # QUERY METHODS
    # =========================================================================

    def query_structure(self, query: str, n_results: int = 3,
                        phase: str = None, design: str = None) -> List[Dict]:
        """Query structure collection."""
        where = {}
        if phase:
            where["phase"] = phase
        if design:
            where["design"] = design

        results = self.structure_collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where if where else None,
            include=["documents", "metadatas", "distances"]
        )

        formatted = []
        if results and results['ids'] and results['ids'][0]:
            for i, sid in enumerate(results['ids'][0]):
                meta = results['metadatas'][0][i]
                meta['sections'] = json.loads(meta.get('sections_json', '[]'))
                formatted.append({
                    "id": sid,
                    "content": results['documents'][0][i],
                    "metadata": meta,
                    "distance": results['distances'][0][i],
                })
        return formatted

    def query_content(self, query: str, n_results: int = 5,
                      section_type: str = None, phase: str = None) -> List[Dict]:
        """Query content collection."""
        where = {}
        if section_type:
            where["section_type"] = section_type
        if phase:
            where["phase"] = phase

        results = self.content_collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where if where else None,
            include=["documents", "metadatas", "distances"]
        )

        formatted = []
        if results and results['ids'] and results['ids'][0]:
            for i, cid in enumerate(results['ids'][0]):
                formatted.append({
                    "id": cid,
                    "content": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i],
                })
        return formatted

    def query_tlf(self, query: str, n_results: int = 5,
                  tlf_type: str = None, category: str = None) -> List[Dict]:
        """Query TLF collection."""
        conditions = []
        if tlf_type:
            conditions.append({"tlf_type": tlf_type})
        if category:
            conditions.append({"category": category})

        where = None
        if len(conditions) == 1:
            where = conditions[0]
        elif len(conditions) > 1:
            where = {"$and": conditions}

        results = self.tlf_collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"]
        )

        formatted = []
        if results and results['ids'] and results['ids'][0]:
            for i, tid in enumerate(results['ids'][0]):
                formatted.append({
                    "id": tid,
                    "content": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i],
                })
        return formatted

    def get_stats(self) -> Dict:
        """Get index statistics."""
        return {
            "structure_count": self.structure_collection.count(),
            "content_count": self.content_collection.count(),
            "tlf_count": self.tlf_collection.count(),
        }

    def clear_all(self):
        """Clear all collections."""
        for name in [COLLECTION_STRUCTURE, COLLECTION_CONTENT, COLLECTION_TLF]:
            try:
                self.client.delete_collection(name)
            except:
                pass

        # Recreate
        self.structure_collection = self.client.get_or_create_collection(
            name=COLLECTION_STRUCTURE, embedding_function=self.embedding_fn
        )
        self.content_collection = self.client.get_or_create_collection(
            name=COLLECTION_CONTENT, embedding_function=self.embedding_fn
        )
        self.tlf_collection = self.client.get_or_create_collection(
            name=COLLECTION_TLF, embedding_function=self.embedding_fn
        )


# =============================================================================
# RAG SAP GENERATOR
# =============================================================================

class RAGSAPGenerator:
    """Generate SAP using 3-collection RAG + Knowledge Graph."""

    def __init__(self, rag_index: SAPRAGIndex):
        self.rag_index = rag_index
        if _USE_OPENAI:
            self.client = OpenAI()
            self.use_openai = True
        else:
            self.client = Anthropic()
            self.use_openai = False

        # Layer 1: Fact extraction (43 tiered fields)
        from .fact_extractor import FactExtractor
        self.fact_extractor = FactExtractor()

        # Layer 2: Scientific context (99 rules)
        try:
            from .knowledge_rule_engine import KnowledgeRuleEngine
            self.knowledge_engine = KnowledgeRuleEngine()
            print("[RAGSAPGenerator] Loaded KnowledgeRuleEngine (99 rules)")
        except Exception as e:
            print(f"[RAGSAPGenerator] KnowledgeRuleEngine not available: {e}")
            self.knowledge_engine = None

        # Layer 2: Domain knowledge graph
        try:
            from ..knowledge_graph.graph_rag import BiostatisticsGraphRAG
            self.graph_rag = BiostatisticsGraphRAG()
            print("[RAGSAPGenerator] Loaded GraphRAG (domain knowledge)")
        except Exception as e:
            print(f"[RAGSAPGenerator] GraphRAG not available: {e}")
            self.graph_rag = None

    def generate_section(
        self,
        section_type: str,
        protocol_facts: 'ProtocolFacts',
        n_examples: int = 3,
        scientific_context: str = ""
    ) -> str:
        """Generate a SAP section using RAG + Knowledge Graph."""

        # Query content collection for similar sections
        query = f"{section_type} {protocol_facts.phase or ''} {protocol_facts.endpoint_type or ''}"
        examples = self.rag_index.query_content(
            query=query,
            section_type=section_type,
            n_results=n_examples
        )

        # Build examples text
        examples_text = ""
        if examples:
            print(f"    [RAG] Found {len(examples)} examples for {section_type}")
            for i, ex in enumerate(examples, 1):
                source = ex["metadata"].get("nct_id", "unknown")
                print(f"    [RAG]   - Example {i}: {source}")
                examples_text += f"\n--- Example {i} (from {source}) ---\n"
                examples_text += ex["content"][:2500]
                examples_text += "\n"
        else:
            print(f"    [RAG] No examples found for {section_type}")
            examples_text = "[No examples found]"

        # Build facts string
        facts_str = protocol_facts.to_formatted_string()

        # Build scientific context
        sci_context = ""
        if scientific_context:
            sci_context = f"\n## SCIENTIFIC CONTEXT (Informational):\n{scientific_context}\n"

        # Generate section
        prompt = f"""You are writing a Statistical Analysis Plan (SAP) section.

TASK: Write the "{section_type.replace('_', ' ').title()}" section.

## EXTRACTED PROTOCOL FACTS (use these values):
{facts_str}
{sci_context}
## STYLE EXAMPLES FROM REAL SAPs:
{examples_text}

## RULES:
1. Use the extracted facts - do not invent values
2. Follow the style of the example SAP sections
3. If a required value is not in the facts, write [REQUIRES PROTOCOL INPUT]
4. Be concise and professional
5. Output ONLY the section content

Write the {section_type.replace('_', ' ').title()} section:"""

        if self.use_openai:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        else:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text

    def get_sap_structure(self, facts: 'ProtocolFacts') -> List[str]:
        """Query structure collection to get recommended sections for this trial type."""
        query = f"SAP structure {facts.phase or ''} {facts.endpoint_type or ''}"

        structures = self.rag_index.query_structure(
            query=query,
            phase=facts.phase,
            n_results=3
        )

        if structures:
            print(f"    [Structure RAG] Found {len(structures)} similar SAP structures")
            # Get sections from best matching structure
            best = structures[0]
            sections = best["metadata"].get("sections", [])
            if sections:
                print(f"    [Structure RAG] Using structure from {best['metadata'].get('nct_id', 'unknown')}")
                return [s.get("type", s.get("title", "").lower().replace(" ", "_")) for s in sections if isinstance(s, dict)]

        return None  # Use default sections

    def generate_tlf_appendix(self, facts: 'ProtocolFacts', n_per_category: int = 5) -> str:
        """Generate TLF appendix using TLF collection."""
        print("\n[Layer 3] Generating TLF Appendix...")

        tlf_sections = []

        # Define TLF categories to include
        categories = [
            ("demographics", "Demographics and Baseline Characteristics"),
            ("disposition", "Patient Disposition"),
            ("efficacy", "Efficacy Tables and Figures"),
            ("safety", "Safety Tables and Listings"),
        ]

        # Add PK for Phase 1
        if facts.phase and "1" in facts.phase:
            categories.append(("pk", "Pharmacokinetic Tables"))

        for category_key, category_title in categories:
            query = f"{category_key} {facts.phase or ''} {facts.indication or ''}"

            tlfs = self.rag_index.query_tlf(
                query=query,
                category=category_key if category_key != "efficacy" else None,
                n_results=n_per_category
            )

            if tlfs:
                print(f"    [TLF RAG] Found {len(tlfs)} {category_key} TLFs")

                tlf_sections.append(f"### {category_title}\n")
                tlf_sections.append("| Number | Type | Title |")
                tlf_sections.append("|--------|------|-------|")

                for tlf in tlfs:
                    meta = tlf["metadata"]
                    number = meta.get("tlf_number", "TBD")
                    tlf_type = meta.get("tlf_type", "Table")
                    title = meta.get("tlf_title", "TBD")[:60]
                    source = meta.get("nct_id", "")
                    tlf_sections.append(f"| {number} | {tlf_type} | {title} |")

                tlf_sections.append("")

        if not tlf_sections:
            return "\n[No TLF shells found in RAG]\n"

        return "\n".join(tlf_sections)

    def generate_full_sap(
        self,
        protocol_path_or_text: str,
        sections: List[str] = None
    ) -> str:
        """Generate full SAP from protocol file path or text."""

        # If it's a file path, extract text first
        if protocol_path_or_text.endswith('.pdf'):
            print(f"[Layer 0] Extracting text from PDF...")
            parser = SAPParser()
            protocol_text = parser.parse_sap(protocol_path_or_text)
            if not protocol_text:
                raise ValueError(f"Failed to extract text from {protocol_path_or_text}")
            print(f"  Extracted {len(protocol_text)} characters")
        else:
            protocol_text = protocol_path_or_text

        # LAYER 1: Extract facts (43 tiered fields)
        print("[Layer 1] Extracting facts from protocol...")
        facts = self.fact_extractor.extract(protocol_text)

        print(f"  Phase: {facts.phase}")
        print(f"  Primary Endpoint: {facts.primary_endpoint}")
        print(f"  Sample Size: {facts.sample_size}")
        print(f"  Alpha: {facts.alpha}")

        # Get scientific context
        scientific_context = ""
        if self.knowledge_engine:
            print("\n[Knowledge Engine] Getting scientific context...")
            try:
                facts_dict = facts.to_dict()
                scientific_context = self.knowledge_engine.get_context_for_generation(facts_dict)
            except Exception as e:
                print(f"  [!] Error: {e}")

        # LAYER 2: Get SAP structure from RAG
        print("\n[Layer 2] Getting SAP structure from RAG...")

        default_sections = [
            "introduction",
            "objectives_endpoints",
            "study_design",
            "sample_size",
            "analysis_populations",
            "statistical_methods",
            "efficacy_analysis",
            "safety_analysis",
            "missing_data",
            "sensitivity_analysis",
        ]

        if facts.interim_analysis:
            default_sections.append("interim_analysis")
        if facts.multiplicity_adjustment:
            default_sections.append("multiplicity")

        # Try to get structure from RAG
        if sections is None:
            rag_sections = self.get_sap_structure(facts)
            if rag_sections:
                # Map RAG section names to our standard names
                section_mapping = {
                    "introduction": "introduction",
                    "objectives": "objectives_endpoints",
                    "endpoints": "objectives_endpoints",
                    "study_design": "study_design",
                    "design": "study_design",
                    "sample_size": "sample_size",
                    "populations": "analysis_populations",
                    "analysis_populations": "analysis_populations",
                    "statistical_methods": "statistical_methods",
                    "efficacy": "efficacy_analysis",
                    "efficacy_analysis": "efficacy_analysis",
                    "safety": "safety_analysis",
                    "safety_analysis": "safety_analysis",
                    "missing_data": "missing_data",
                    "sensitivity": "sensitivity_analysis",
                    "sensitivity_analysis": "sensitivity_analysis",
                    "interim": "interim_analysis",
                    "interim_analysis": "interim_analysis",
                    "multiplicity": "multiplicity",
                }
                mapped = []
                for s in rag_sections:
                    s_lower = s.lower().replace(" ", "_")
                    if s_lower in section_mapping:
                        mapped.append(section_mapping[s_lower])
                    elif s_lower in default_sections:
                        mapped.append(s_lower)
                if mapped:
                    sections_to_generate = list(dict.fromkeys(mapped))  # Remove duplicates, preserve order
                    print(f"    Using RAG-guided structure: {len(sections_to_generate)} sections")
                else:
                    sections_to_generate = default_sections
            else:
                sections_to_generate = default_sections
        else:
            sections_to_generate = sections

        print(f"\n[Layer 2] Generating SAP sections...")
        generated = {}

        for section_type in sections_to_generate:
            print(f"  [{section_type}] Generating...")
            try:
                content = self.generate_section(
                    section_type=section_type,
                    protocol_facts=facts,
                    scientific_context=scientific_context
                )
                generated[section_type] = content
                print(f"  [{section_type}] Done ({len(content)} chars)")
            except Exception as e:
                print(f"  [{section_type}] Error: {e}")

        # Combine sections into full SAP document
        study_name_line = f"**Study Name:** {facts.study_name}\n" if facts.study_name else ""
        sap_doc = f"""# STATISTICAL ANALYSIS PLAN

**Protocol:** {facts.protocol_number or facts.nct_id or 'TBD'}
{study_name_line}**Phase:** {facts.phase or 'TBD'}
**Indication:** {facts.indication or 'TBD'}
**Primary Endpoint:** {facts.primary_endpoint or 'TBD'}

---

"""
        for section_type in sections_to_generate:
            if section_type in generated:
                title = section_type.replace('_', ' ').title()
                sap_doc += f"## {title}\n\n{generated[section_type]}\n\n---\n\n"

        # LAYER 3: Generate TLF Appendix from TLF collection
        tlf_appendix = self.generate_tlf_appendix(facts)
        if tlf_appendix and "[No TLF" not in tlf_appendix:
            sap_doc += f"## Appendix: Tables, Listings, and Figures (TLF)\n\n{tlf_appendix}\n\n---\n\n"

        return sap_doc


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_rag_index(db_path: str = CHROMA_DB_PATH) -> SAPRAGIndex:
    """Create a new 3-collection RAG index."""
    return SAPRAGIndex(db_path=db_path)


def index_saps(sap_folder: str, db_path: str = CHROMA_DB_PATH) -> SAPRAGIndex:
    """Index SAPs from a folder."""
    index = SAPRAGIndex(db_path=db_path)
    index.index_sap_folder(sap_folder)
    return index


# =============================================================================
# MAIN / TEST
# =============================================================================

if __name__ == "__main__":
    print("SAP RAG System (3-Collection Architecture)")
    print("=" * 60)

    # Default SAP folder
    sap_folder = "/mnt/c/Users/vijay/Desktop/sap_data/oncology_trials/saps"

    print(f"\n[1] Creating 3-collection RAG index...")
    rag = SAPRAGIndex()

    print(f"\n[2] Indexing SAPs from: {sap_folder}")
    stats = rag.index_sap_folder(sap_folder)

    print(f"\n[3] Index stats:")
    print(f"  Structures: {stats['structure']}")
    print(f"  Content chunks: {stats['content']}")
    print(f"  TLF shells: {stats['tlf']}")
