"""
Extract TLF patterns from 60 reference SAPs.

Pipeline:
  1. LlamaParse extracts text from each PDF (high-quality markdown)
  2. Claude Sonnet extracts structured TLF list from each SAP
  3. Aggregation script finds universal patterns across all SAPs

Usage:
  python scripts/extract_sap_patterns.py
"""

import os
import sys
import json
import time
import glob
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
LLAMA_API_KEY = "llx-tdPTYmMBurtmVlNxstQCYoFGtm4T9pyQcK8liOsKeP1lPD2b"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

SAP_DIR = Path(__file__).parent.parent / "reference_saps"
OUTPUT_DIR = Path(__file__).parent.parent / "reference_saps" / "_extracted"
PARSED_DIR = OUTPUT_DIR / "parsed_text"
TLF_DIR = OUTPUT_DIR / "tlf_json"
AGGREGATE_DIR = OUTPUT_DIR / "aggregate"

for d in [PARSED_DIR, TLF_DIR, AGGREGATE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# STEP 1: LlamaParse PDF → Markdown
# ---------------------------------------------------------------------------
def parse_pdf_with_llama(pdf_path: Path) -> str:
    """Parse a single PDF with LlamaParse. Returns markdown text."""
    from llama_parse import LlamaParse

    out_file = PARSED_DIR / f"{pdf_path.stem}.md"
    if out_file.exists() and out_file.stat().st_size > 500:
        print(f"  [CACHED] {pdf_path.name}")
        return out_file.read_text()

    print(f"  [PARSE]  {pdf_path.name} ({pdf_path.stat().st_size // 1024} KB)")

    parser = LlamaParse(
        api_key=LLAMA_API_KEY,
        result_type="markdown",
        verbose=False,
    )

    try:
        documents = parser.load_data(str(pdf_path))
        text = "\n\n".join(doc.text for doc in documents)
        out_file.write_text(text)
        return text
    except Exception as e:
        print(f"  [ERROR]  {pdf_path.name}: {e}")
        return ""


def parse_all_pdfs():
    """Parse all SAP PDFs. Returns dict of {nct_id: markdown_text}."""
    pdfs = sorted(SAP_DIR.rglob("*.pdf"))
    print(f"\n=== STEP 1: Parse {len(pdfs)} PDFs with LlamaParse ===\n")

    results = {}
    for pdf in pdfs:
        nct = pdf.stem.replace("_SAP", "")
        area = pdf.parent.name
        text = parse_pdf_with_llama(pdf)
        if text:
            results[nct] = {"text": text, "area": area, "pdf": str(pdf)}

    print(f"\nParsed: {len(results)} / {len(pdfs)} PDFs\n")
    return results


# ---------------------------------------------------------------------------
# STEP 2: Claude Sonnet extracts TLF list from each SAP
# ---------------------------------------------------------------------------
EXTRACTION_PROMPT = """You are a biostatistician. Read this Statistical Analysis Plan (SAP) and extract EVERY table, figure, and listing that the SAP specifies should be produced.

For each item, extract:
- category: "table", "figure", or "listing"
- title: the exact title as stated
- population: analysis population (ITT, Safety, PP, PK, etc.)
- section: ICH section number if stated (e.g. 14.1, 14.2, 14.3, 14.4, 16.2)
- type: classify as one of: disposition, demographics, medical_history, baseline, disease_characteristics, prior_therapy, concomitant_medications, exposure, ae_overview, ae_by_soc_pt, ae_grade3plus, ae_serious, ae_discontinuation, ae_death, ae_common, aesi, labs_summary, labs_shift, labs_ctcae, vitals, ecg, physical_exam, pregnancy_test, ecog, pk_concentration, pk_parameters, immunogenicity, qol, efficacy_binary, efficacy_tte, efficacy_continuous, subgroup, forest_plot, km_plot, waterfall_plot, swimmer_plot, other
- conditional: true if this table is only generated when a certain condition is met (e.g. "only if labs collected"), false if always generated

Also extract these study-level facts:
- therapeutic_area: oncology, cardiology, dermatology, etc.
- phase: Phase 1, 2, 3, etc.
- design_type: superiority, non_inferiority, equivalence, biosimilar, single_arm, descriptive
- has_central_review: true/false
- has_pk: true/false
- has_immunogenicity: true/false
- has_qol: true/false (and instrument names)
- treatment_periods: list of period names
- num_arms: number of treatment arms

Return ONLY valid JSON with this structure:
{
  "study_facts": { ... },
  "tables": [ { "title": "...", "population": "...", "section": "...", "type": "...", "conditional": false }, ... ],
  "figures": [ { "title": "...", "type": "...", ... }, ... ],
  "listings": [ { "title": "...", "population": "...", "type": "...", ... }, ... ]
}

SAP TEXT:
"""


def extract_tlf_with_claude(nct: str, text: str, area: str) -> dict:
    """Send SAP text to Claude Sonnet, get structured TLF list back."""
    from anthropic import Anthropic

    out_file = TLF_DIR / f"{nct}.json"
    if out_file.exists() and out_file.stat().st_size > 100:
        print(f"  [CACHED] {nct}")
        return json.loads(out_file.read_text())

    # Truncate to fit context (Sonnet handles ~200K but keep it reasonable)
    max_chars = 180000
    truncated = text[:max_chars] if len(text) > max_chars else text

    prompt = EXTRACTION_PROMPT + truncated

    print(f"  [CLAUDE] {nct} ({area}) - {len(truncated)//1000}K chars")

    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text.strip()

        # Strip markdown fences if present
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            response_text = "\n".join(lines)

        result = json.loads(response_text)
        result["_nct"] = nct
        result["_area"] = area

        out_file.write_text(json.dumps(result, indent=2))
        return result

    except json.JSONDecodeError as e:
        print(f"  [JSON ERROR] {nct}: {e}")
        # Save raw response for debugging
        (TLF_DIR / f"{nct}_raw.txt").write_text(response_text)
        return {"_nct": nct, "_area": area, "_error": str(e)}
    except Exception as e:
        print(f"  [ERROR] {nct}: {e}")
        return {"_nct": nct, "_area": area, "_error": str(e)}


def extract_all_tlfs(parsed: dict):
    """Extract TLF lists from all parsed SAPs."""
    print(f"\n=== STEP 2: Extract TLFs with Claude Sonnet ({len(parsed)} SAPs) ===\n")

    results = {}
    for nct, data in parsed.items():
        result = extract_tlf_with_claude(nct, data["text"], data["area"])
        results[nct] = result
        # Small delay to avoid rate limits
        time.sleep(0.5)

    success = sum(1 for r in results.values() if "_error" not in r)
    print(f"\nExtracted: {success} / {len(parsed)} SAPs\n")
    return results


# ---------------------------------------------------------------------------
# STEP 3: Aggregate patterns across all SAPs
# ---------------------------------------------------------------------------
def aggregate_patterns(results: dict):
    """Find universal vs conditional patterns across all SAPs."""
    print(f"\n=== STEP 3: Aggregate patterns across {len(results)} SAPs ===\n")

    total_saps = len([r for r in results.values() if "_error" not in r])
    if total_saps == 0:
        print("No successful extractions to aggregate.")
        return

    # Count how often each table TYPE appears
    type_counts = {}
    type_examples = {}
    all_types_by_area = {}

    for nct, result in results.items():
        if "_error" in result:
            continue

        area = result.get("_area", "unknown")
        if area not in all_types_by_area:
            all_types_by_area[area] = set()

        for table in result.get("tables", []):
            t = table.get("type", "other")
            type_counts[t] = type_counts.get(t, 0) + 1
            all_types_by_area[area].add(t)
            if t not in type_examples:
                type_examples[t] = []
            if len(type_examples[t]) < 3:
                type_examples[t].append({
                    "nct": nct,
                    "title": table.get("title", ""),
                    "population": table.get("population", ""),
                })

    # Count figure and listing types
    figure_type_counts = {}
    listing_type_counts = {}

    for nct, result in results.items():
        if "_error" in result:
            continue
        for fig in result.get("figures", []):
            t = fig.get("type", "other")
            figure_type_counts[t] = figure_type_counts.get(t, 0) + 1
        for lst in result.get("listings", []):
            t = lst.get("type", "other")
            listing_type_counts[t] = listing_type_counts.get(t, 0) + 1

    # Classify: mandatory (>80%), common (>50%), conditional (<50%)
    mandatory = []
    common = []
    conditional = []

    for t, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        pct = count / total_saps * 100
        entry = {"type": t, "count": count, "pct": round(pct, 1), "examples": type_examples.get(t, [])}
        if pct >= 80:
            mandatory.append(entry)
        elif pct >= 40:
            common.append(entry)
        else:
            conditional.append(entry)

    # Study facts summary
    design_types = {}
    phases = {}
    areas = {}
    for nct, result in results.items():
        if "_error" in result:
            continue
        facts = result.get("study_facts", {})
        dt = facts.get("design_type", "unknown")
        design_types[dt] = design_types.get(dt, 0) + 1
        ph = facts.get("phase", "unknown")
        phases[ph] = phases.get(ph, 0) + 1
        ar = facts.get("therapeutic_area", result.get("_area", "unknown"))
        areas[ar] = areas.get(ar, 0) + 1

    # Build aggregate report
    aggregate = {
        "total_saps_analyzed": total_saps,
        "study_facts_summary": {
            "design_types": design_types,
            "phases": phases,
            "therapeutic_areas": areas,
        },
        "table_types": {
            "mandatory_80pct_plus": mandatory,
            "common_40_to_80pct": common,
            "conditional_under_40pct": conditional,
        },
        "figure_types": {
            t: {"count": c, "pct": round(c / total_saps * 100, 1)}
            for t, c in sorted(figure_type_counts.items(), key=lambda x: -x[1])
        },
        "listing_types": {
            t: {"count": c, "pct": round(c / total_saps * 100, 1)}
            for t, c in sorted(listing_type_counts.items(), key=lambda x: -x[1])
        },
        "table_types_by_therapeutic_area": {
            area: sorted(list(types))
            for area, types in sorted(all_types_by_area.items())
        },
    }

    # Save
    out_file = AGGREGATE_DIR / "pattern_summary.json"
    out_file.write_text(json.dumps(aggregate, indent=2))
    print(f"Saved aggregate to {out_file}")

    # Print summary
    print(f"\n{'='*60}")
    print(f"PATTERN SUMMARY ({total_saps} SAPs)")
    print(f"{'='*60}")

    print(f"\nMANDATORY TABLES (appear in >=80% of SAPs):")
    for entry in mandatory:
        print(f"  {entry['pct']:5.1f}%  ({entry['count']:2d}/{total_saps})  {entry['type']}")

    print(f"\nCOMMON TABLES (appear in 40-80% of SAPs):")
    for entry in common:
        print(f"  {entry['pct']:5.1f}%  ({entry['count']:2d}/{total_saps})  {entry['type']}")

    print(f"\nCONDITIONAL TABLES (appear in <40% of SAPs):")
    for entry in conditional:
        print(f"  {entry['pct']:5.1f}%  ({entry['count']:2d}/{total_saps})  {entry['type']}")

    print(f"\nFIGURE TYPES:")
    for t, info in aggregate["figure_types"].items():
        print(f"  {info['pct']:5.1f}%  ({info['count']:2d}/{total_saps})  {t}")

    print(f"\nLISTING TYPES:")
    for t, info in aggregate["listing_types"].items():
        print(f"  {info['pct']:5.1f}%  ({info['count']:2d}/{total_saps})  {t}")

    return aggregate


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    if not ANTHROPIC_API_KEY:
        print("ERROR: Set ANTHROPIC_API_KEY environment variable")
        sys.exit(1)

    # Step 1: Parse PDFs
    parsed = parse_all_pdfs()

    # Step 2: Extract TLFs
    results = extract_all_tlfs(parsed)

    # Step 3: Aggregate
    aggregate = aggregate_patterns(results)

    print(f"\n{'='*60}")
    print("DONE")
    print(f"  Parsed text:  {PARSED_DIR}")
    print(f"  TLF JSONs:    {TLF_DIR}")
    print(f"  Aggregate:    {AGGREGATE_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
