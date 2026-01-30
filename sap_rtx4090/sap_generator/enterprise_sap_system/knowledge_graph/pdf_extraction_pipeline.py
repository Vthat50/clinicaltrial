"""
PDF Extraction Pipeline for SAP Knowledge Graph
================================================

Extracts text from all PDFs in full_saps/ directory and runs
Claude-based KG extraction to build comprehensive knowledge graph.

Usage:
    python pdf_extraction_pipeline.py [--extract-only] [--kg-only] [--limit N]

    --extract-only: Only extract PDFs to text, don't run KG extraction
    --kg-only: Only run KG extraction on existing text files
    --limit N: Process only first N PDFs (for testing)
    --resume: Resume from last processed file
"""

import os
import sys
import json
import argparse
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import hashlib
import re

# PDF extraction
try:
    import fitz  # PyMuPDF - best quality
    PDF_LIBRARY = "pymupdf"
except ImportError:
    try:
        import pdfplumber
        PDF_LIBRARY = "pdfplumber"
    except ImportError:
        import PyPDF2
        PDF_LIBRARY = "pypdf2"

print(f"Using PDF library: {PDF_LIBRARY}")

# Anthropic for KG extraction
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("Warning: anthropic not installed. KG extraction will fail.")


# =============================================================================
# PATHS
# =============================================================================

BASE_DIR = Path(__file__).parent
FULL_SAPS_DIR = BASE_DIR / "reference_saps" / "full_saps"
EXTRACTED_TEXT_DIR = BASE_DIR / "reference_saps" / "extracted_text"
OUTPUT_DIR = BASE_DIR / "output"
PROGRESS_FILE = BASE_DIR / "output" / "extraction_progress.json"


# =============================================================================
# PDF TEXT EXTRACTION
# =============================================================================

def extract_pdf_pymupdf(pdf_path: Path) -> str:
    """Extract text using PyMuPDF (best quality)."""
    doc = fitz.open(pdf_path)
    text_parts = []

    for page_num, page in enumerate(doc, 1):
        text = page.get_text("text")
        if text.strip():
            text_parts.append(f"\n--- Page {page_num} ---\n{text}")

    doc.close()
    return "\n".join(text_parts)


def extract_pdf_pdfplumber(pdf_path: Path) -> str:
    """Extract text using pdfplumber."""
    import pdfplumber
    text_parts = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            if text.strip():
                text_parts.append(f"\n--- Page {page_num} ---\n{text}")

    return "\n".join(text_parts)


def extract_pdf_pypdf2(pdf_path: Path) -> str:
    """Extract text using PyPDF2 (fallback)."""
    import PyPDF2
    text_parts = []

    with open(pdf_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        for page_num, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            if text.strip():
                text_parts.append(f"\n--- Page {page_num} ---\n{text}")

    return "\n".join(text_parts)


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from PDF using best available library."""
    if PDF_LIBRARY == "pymupdf":
        return extract_pdf_pymupdf(pdf_path)
    elif PDF_LIBRARY == "pdfplumber":
        return extract_pdf_pdfplumber(pdf_path)
    else:
        return extract_pdf_pypdf2(pdf_path)


def extract_all_pdfs(limit: Optional[int] = None, resume: bool = False) -> Dict[str, str]:
    """Extract text from all PDFs in full_saps directory."""

    # Create output directory
    EXTRACTED_TEXT_DIR.mkdir(parents=True, exist_ok=True)

    # Get all PDFs
    pdf_files = sorted(FULL_SAPS_DIR.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDFs in {FULL_SAPS_DIR}")

    if limit:
        pdf_files = pdf_files[:limit]
        print(f"Processing first {limit} PDFs")

    # Load progress if resuming
    processed = set()
    if resume and PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            progress = json.load(f)
            processed = set(progress.get("extracted_pdfs", []))
        print(f"Resuming from {len(processed)} already extracted PDFs")

    results = {}
    errors = []

    for i, pdf_path in enumerate(pdf_files, 1):
        pdf_name = pdf_path.stem
        txt_path = EXTRACTED_TEXT_DIR / f"{pdf_name}.txt"

        # Skip if already processed (resume mode)
        if resume and pdf_name in processed:
            print(f"  [{i}/{len(pdf_files)}] Skipping {pdf_name} (already extracted)")
            if txt_path.exists():
                results[pdf_name] = txt_path.read_text(encoding='utf-8', errors='ignore')
            continue

        # Skip if text file already exists
        if txt_path.exists() and not resume:
            print(f"  [{i}/{len(pdf_files)}] Loading cached {pdf_name}")
            results[pdf_name] = txt_path.read_text(encoding='utf-8', errors='ignore')
            continue

        try:
            print(f"  [{i}/{len(pdf_files)}] Extracting {pdf_name}...", end=" ", flush=True)

            text = extract_pdf_text(pdf_path)

            # Basic quality check
            if len(text) < 500:
                print(f"⚠️ Short ({len(text)} chars)")
                errors.append((pdf_name, "Short extraction"))
            else:
                print(f"✓ ({len(text):,} chars)")

            # Save to text file
            txt_path.write_text(text, encoding='utf-8')
            results[pdf_name] = text
            processed.add(pdf_name)

            # Update progress
            if PROGRESS_FILE.parent.exists():
                with open(PROGRESS_FILE, 'w') as f:
                    json.dump({
                        "extracted_pdfs": list(processed),
                        "last_updated": datetime.now().isoformat()
                    }, f, indent=2)

        except Exception as e:
            print(f"✗ Error: {e}")
            errors.append((pdf_name, str(e)))

    print(f"\nExtraction complete: {len(results)} successful, {len(errors)} errors")
    if errors:
        print("Errors:")
        for name, err in errors[:10]:
            print(f"  - {name}: {err}")

    return results


# =============================================================================
# KNOWLEDGE GRAPH EXTRACTION (Claude-based)
# =============================================================================

EXTRACTION_PROMPT = """You are extracting structured facts from a Statistical Analysis Plan (SAP) document.

Extract ALL relevant information you can find. Be thorough but only extract what's actually in the document.

Categories to extract (include any you find, skip those not present):

1. **ENDPOINTS**: primary, secondary, exploratory endpoints
   - Extract: name, type, definition

2. **STATISTICAL METHODS**: Any analysis methods mentioned
   - Extract: method name, what it's used for, any parameters/details

3. **CENSORING RULES**: For time-to-event endpoints (PFS, OS, DFS, TTP, etc.)
   - Extract: endpoint, what counts as event, when to censor

4. **MULTIPLICITY / TYPE I ERROR CONTROL**: Alpha spending, testing hierarchies, adjustment methods
   - Look for: Hochberg, Holm, Bonferroni, graphical approaches, gatekeeping, hierarchical testing, alpha allocation
   - Extract any details about controlling family-wise error rate

5. **INTERIM ANALYSIS**: Any planned interim looks
   - Extract: number of analyses, alpha spending function, stopping boundaries

6. **SAMPLE SIZE / POWER**: Sample size calculations
   - Extract: total N, power, assumptions (HR, event rates, dropout)

7. **ANALYSIS POPULATIONS**: ITT, mITT, PP, Safety, etc.
   - Extract: population name, definition

8. **ESTIMANDS** (ICH E9 R1 framework if mentioned)
   - Extract: endpoint, population, intercurrent events, strategy

9. **SUBGROUPS**: Any pre-specified subgroup analyses

10. **SENSITIVITY ANALYSES**: Alternative analysis approaches

Return as JSON with structure like:
- trial_id, phase, indication, design
- endpoints: array of name/type/definition objects
- methods: array of name/applied_to/details objects
- censoring_rules: array of endpoint/event/censoring objects
- multiplicity: method/details/alpha_allocation object
- interim_analysis: n_analyses/spending_function/details object
- sample_size: n/power/assumptions object
- populations: array of name/definition objects
- estimands, subgroups, sensitivity_analyses: arrays

SAP Document:
{content}

Return ONLY valid JSON, no explanatory text."""


def extract_kg_from_text(text: str, filename: str, client: anthropic.Anthropic) -> Dict[str, Any]:
    """Extract knowledge graph elements from SAP text using Claude."""

    # Truncate if too long (Claude context limit)
    max_chars = 180000  # ~45k tokens
    if len(text) > max_chars:
        # Keep first and last portions
        text = text[:max_chars//2] + "\n\n[... CONTENT TRUNCATED ...]\n\n" + text[-max_chars//2:]

    prompt = EXTRACTION_PROMPT.format(content=text)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text

        # Extract JSON from response - try multiple methods
        result = None
        parse_errors = []

        # Method 1: Look for ```json code blocks first
        json_block_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
        if json_block_match:
            try:
                result = json.loads(json_block_match.group(1))
            except json.JSONDecodeError as e:
                parse_errors.append(f"Method1: {e}")

        # Method 2: Look for ``` code blocks
        if result is None:
            code_block_match = re.search(r'```\s*([\s\S]*?)\s*```', response_text)
            if code_block_match:
                try:
                    result = json.loads(code_block_match.group(1))
                except json.JSONDecodeError as e:
                    parse_errors.append(f"Method2: {e}")

        # Method 3: Find outermost braces
        if result is None:
            first_brace = response_text.find('{')
            last_brace = response_text.rfind('}')
            if first_brace != -1 and last_brace > first_brace:
                try:
                    result = json.loads(response_text[first_brace:last_brace + 1])
                except json.JSONDecodeError as e:
                    parse_errors.append(f"Method3: {e}")

        if result:
            result["source_file"] = filename
            return result
        else:
            return {
                "error": f"No valid JSON. Parse errors: {parse_errors}",
                "source_file": filename,
                "raw_preview": response_text[:300]
            }

    except Exception as e:
        import traceback
        return {"error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()[:500], "source_file": filename}


def run_kg_extraction(
    texts: Dict[str, str],
    limit: Optional[int] = None,
    resume: bool = False
) -> List[Dict[str, Any]]:
    """Run Claude KG extraction on all text files."""

    if not ANTHROPIC_AVAILABLE:
        print("ERROR: anthropic package not installed")
        return []

    client = anthropic.Anthropic()

    # Load existing results if resuming
    results_file = OUTPUT_DIR / "kg_extraction_results.json"
    existing_results = []
    processed_files = set()

    if resume and results_file.exists():
        with open(results_file) as f:
            existing_results = json.load(f)
            processed_files = {r.get("source_file") for r in existing_results if "source_file" in r}
        print(f"Resuming from {len(processed_files)} already processed files")

    items = list(texts.items())
    if limit:
        items = items[:limit]

    results = existing_results.copy()

    print(f"\nRunning KG extraction on {len(items)} SAPs...")
    print("=" * 60)

    for i, (filename, text) in enumerate(items, 1):
        if resume and filename in processed_files:
            print(f"  [{i}/{len(items)}] Skipping {filename} (already processed)")
            continue

        print(f"  [{i}/{len(items)}] Extracting from {filename}...", end=" ", flush=True)

        try:
            result = extract_kg_from_text(text, filename, client)

            if "error" in result:
                print(f"⚠️ {result['error'][:50]}")
            else:
                ep_count = len(result.get("endpoints", []))
                meth_count = len(result.get("methods", []))
                print(f"✓ (endpoints:{ep_count}, methods:{meth_count})")

            results.append(result)

            # Save progress periodically
            if i % 5 == 0:
                with open(results_file, 'w') as f:
                    json.dump(results, f, indent=2)

            # Rate limiting
            time.sleep(0.5)

        except Exception as e:
            print(f"✗ Error: {e}")
            results.append({"error": str(e), "source_file": filename})

    # Final save
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nKG extraction complete: {len(results)} files processed")
    return results


# =============================================================================
# KNOWLEDGE GRAPH BUILDING
# =============================================================================

def build_knowledge_graph(extractions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build unified knowledge graph from extractions."""

    nodes = []
    edges = []
    node_id_counter = 0

    def make_id(prefix: str, content: str) -> str:
        """Create deterministic ID from content."""
        hash_val = hashlib.md5(content.encode()).hexdigest()[:8]
        return f"{prefix}:{hash_val}"

    for extraction in extractions:
        if "error" in extraction:
            continue

        source_file = extraction.get("source_file", "unknown")
        trial_id = extraction.get("trial_id", source_file)

        # Trial node
        trial_node_id = make_id("trial", trial_id)
        nodes.append({
            "id": trial_node_id,
            "type": "trial",
            "attributes": {
                "trial_id": trial_id,
                "phase": extraction.get("phase", ""),
                "indication": extraction.get("indication", ""),
                "source_file": source_file
            }
        })

        # Document node
        doc_node_id = make_id("doc", source_file)
        nodes.append({
            "id": doc_node_id,
            "type": "document",
            "attributes": {
                "filename": source_file,
                "doc_type": "SAP"
            }
        })
        edges.append({
            "source": doc_node_id,
            "target": trial_node_id,
            "type": "DESCRIBES"
        })

        # Endpoints
        for ep in (extraction.get("endpoints") or []):
            ep_id = make_id("endpoint", f"{trial_id}:{ep.get('name', '')}")
            nodes.append({
                "id": ep_id,
                "type": "endpoint",
                "attributes": {
                    "name": ep.get("name", ""),
                    "endpoint_type": ep.get("type", ""),
                    "definition": ep.get("definition", ""),
                    "exact_quote": ep.get("exact_quote", "")
                }
            })
            edges.append({
                "source": trial_node_id,
                "target": ep_id,
                "type": "HAS_ENDPOINT"
            })

        # Methods
        for meth in (extraction.get("methods") or []):
            meth_id = make_id("method", f"{trial_id}:{meth.get('name', '')}")
            nodes.append({
                "id": meth_id,
                "type": "method",
                "attributes": {
                    "name": meth.get("name", ""),
                    "endpoint": meth.get("endpoint_applied_to", ""),
                    "parameters": meth.get("parameters", {}),
                    "exact_quote": meth.get("exact_quote", "")
                }
            })
            edges.append({
                "source": trial_node_id,
                "target": meth_id,
                "type": "USES_METHOD"
            })

        # Censoring rules
        for rule in (extraction.get("censoring_rules") or []):
            rule_id = make_id("censoring", f"{trial_id}:{rule.get('endpoint', '')}")
            nodes.append({
                "id": rule_id,
                "type": "censoring_rule",
                "attributes": {
                    "endpoint": rule.get("endpoint", ""),
                    "event_definition": rule.get("event_definition", ""),
                    "censoring_conditions": rule.get("censoring_conditions", []),
                    "exact_quote": rule.get("exact_quote", "")
                }
            })
            edges.append({
                "source": trial_node_id,
                "target": rule_id,
                "type": "HAS_CENSORING_RULE"
            })

        # Sample size
        ss = extraction.get("sample_size", {})
        if ss:
            ss_id = make_id("sample_size", trial_id)
            nodes.append({
                "id": ss_id,
                "type": "sample_size",
                "attributes": {
                    "total_n": ss.get("total_n"),
                    "power": ss.get("power"),
                    "assumptions": ss.get("assumptions", {}),
                    "exact_quote": ss.get("exact_quote", "")
                }
            })
            edges.append({
                "source": trial_node_id,
                "target": ss_id,
                "type": "HAS_SAMPLE_SIZE"
            })

        # Multiplicity
        mult = extraction.get("multiplicity", {})
        if mult and mult.get("method"):
            mult_id = make_id("multiplicity", trial_id)
            nodes.append({
                "id": mult_id,
                "type": "multiplicity",
                "attributes": {
                    "method": mult.get("method", ""),
                    "alpha_allocation": mult.get("alpha_allocation", {}),
                    "exact_quote": mult.get("exact_quote", "")
                }
            })
            edges.append({
                "source": trial_node_id,
                "target": mult_id,
                "type": "HAS_MULTIPLICITY"
            })

        # Interim analysis
        interim = extraction.get("interim_analysis", {})
        if interim and interim.get("number_of_analyses"):
            interim_id = make_id("interim", trial_id)
            nodes.append({
                "id": interim_id,
                "type": "interim_analysis",
                "attributes": {
                    "number_of_analyses": interim.get("number_of_analyses"),
                    "alpha_spending_function": interim.get("alpha_spending_function", ""),
                    "boundaries": interim.get("boundaries", {}),
                    "exact_quote": interim.get("exact_quote", "")
                }
            })
            edges.append({
                "source": trial_node_id,
                "target": interim_id,
                "type": "HAS_INTERIM_ANALYSIS"
            })

        # Populations
        for pop in (extraction.get("populations") or []):
            pop_id = make_id("population", f"{trial_id}:{pop.get('name', '')}")
            nodes.append({
                "id": pop_id,
                "type": "population",
                "attributes": {
                    "name": pop.get("name", ""),
                    "definition": pop.get("definition", ""),
                    "exact_quote": pop.get("exact_quote", "")
                }
            })
            edges.append({
                "source": trial_node_id,
                "target": pop_id,
                "type": "HAS_POPULATION"
            })

        # Estimands
        for est in (extraction.get("estimands") or []):
            est_id = make_id("estimand", f"{trial_id}:{est.get('endpoint', '')}")
            nodes.append({
                "id": est_id,
                "type": "estimand",
                "attributes": {
                    "endpoint": est.get("endpoint", ""),
                    "population": est.get("population", ""),
                    "treatment": est.get("treatment", ""),
                    "intercurrent_events": est.get("intercurrent_events", []),
                    "summary_measure": est.get("summary_measure", "")
                }
            })
            edges.append({
                "source": trial_node_id,
                "target": est_id,
                "type": "HAS_ESTIMAND"
            })

    kg = {
        "metadata": {
            "version": "2.0",
            "created": datetime.now().isoformat(),
            "type": "factual_knowledge_graph",
            "source": "pdf_extraction_pipeline",
            "stats": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "trials": len([n for n in nodes if n["type"] == "trial"]),
                "endpoints": len([n for n in nodes if n["type"] == "endpoint"]),
                "methods": len([n for n in nodes if n["type"] == "method"]),
                "censoring_rules": len([n for n in nodes if n["type"] == "censoring_rule"]),
                "sample_sizes": len([n for n in nodes if n["type"] == "sample_size"]),
                "multiplicity": len([n for n in nodes if n["type"] == "multiplicity"]),
                "interim_analyses": len([n for n in nodes if n["type"] == "interim_analysis"])
            }
        },
        "nodes": nodes,
        "edges": edges
    }

    return kg


def merge_knowledge_graphs(new_kg: Dict, existing_kg_path: Path) -> Dict:
    """Merge new KG with existing one."""

    if not existing_kg_path.exists():
        return new_kg

    with open(existing_kg_path) as f:
        existing_kg = json.load(f)

    # Get existing node IDs
    existing_node_ids = {n["id"] for n in existing_kg.get("nodes", [])}
    existing_edge_keys = {
        (e["source"], e["target"], e["type"])
        for e in existing_kg.get("edges", [])
    }

    # Add new nodes that don't exist
    merged_nodes = existing_kg.get("nodes", []).copy()
    for node in new_kg.get("nodes", []):
        if node["id"] not in existing_node_ids:
            merged_nodes.append(node)
            existing_node_ids.add(node["id"])

    # Add new edges that don't exist
    merged_edges = existing_kg.get("edges", []).copy()
    for edge in new_kg.get("edges", []):
        key = (edge["source"], edge["target"], edge["type"])
        if key not in existing_edge_keys:
            merged_edges.append(edge)
            existing_edge_keys.add(key)

    merged_kg = {
        "metadata": {
            "version": "2.0",
            "created": datetime.now().isoformat(),
            "type": "factual_knowledge_graph",
            "source": "merged",
            "stats": {
                "total_nodes": len(merged_nodes),
                "total_edges": len(merged_edges),
                "trials": len([n for n in merged_nodes if n["type"] == "trial"]),
                "endpoints": len([n for n in merged_nodes if n["type"] == "endpoint"]),
                "methods": len([n for n in merged_nodes if n["type"] == "method"])
            }
        },
        "nodes": merged_nodes,
        "edges": merged_edges
    }

    return merged_kg


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="PDF Extraction Pipeline for SAP Knowledge Graph")
    parser.add_argument("--extract-only", action="store_true", help="Only extract PDFs to text")
    parser.add_argument("--kg-only", action="store_true", help="Only run KG extraction")
    parser.add_argument("--limit", type=int, help="Limit number of PDFs to process")
    parser.add_argument("--resume", action="store_true", help="Resume from last progress")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("SAP PDF EXTRACTION PIPELINE")
    print("=" * 70)
    print(f"PDFs directory: {FULL_SAPS_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"PDF library: {PDF_LIBRARY}")
    print()

    # Step 1: Extract PDFs to text
    if not args.kg_only:
        print("STEP 1: Extracting PDFs to text...")
        print("-" * 50)
        texts = extract_all_pdfs(limit=args.limit, resume=args.resume)
    else:
        # Load existing text files
        print("STEP 1: Loading existing text files...")
        texts = {}
        for txt_file in EXTRACTED_TEXT_DIR.glob("*.txt"):
            texts[txt_file.stem] = txt_file.read_text(encoding='utf-8', errors='ignore')
        print(f"Loaded {len(texts)} text files")

    if args.extract_only:
        print("\n--extract-only specified, stopping here.")
        return

    # Step 2: Run KG extraction
    print("\nSTEP 2: Running Claude KG extraction...")
    print("-" * 50)
    extractions = run_kg_extraction(texts, limit=args.limit, resume=args.resume)

    # Step 3: Build knowledge graph
    print("\nSTEP 3: Building knowledge graph...")
    print("-" * 50)
    new_kg = build_knowledge_graph(extractions)

    # Step 4: Merge with existing KG
    print("\nSTEP 4: Merging with existing knowledge graph...")
    existing_kg_path = OUTPUT_DIR / "factual_kg_claude.json"
    merged_kg = merge_knowledge_graphs(new_kg, existing_kg_path)

    # Save merged KG
    output_path = OUTPUT_DIR / "factual_kg_merged.json"
    with open(output_path, 'w') as f:
        json.dump(merged_kg, f, indent=2)

    print(f"\nKnowledge graph saved to: {output_path}")
    print("\nFINAL STATISTICS:")
    print("-" * 50)
    stats = merged_kg["metadata"]["stats"]
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\n" + "=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
