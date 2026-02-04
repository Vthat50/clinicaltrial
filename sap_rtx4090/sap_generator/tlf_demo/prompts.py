"""Prompt templates for the demo TLF generator.

Two focused prompts that tell Claude exactly which items to produce,
using the titles/populations parsed from the SAP's TLF index.
Claude receives both the protocol (detailed clinical content) and the
SAP (statistical methodology, analysis populations, TLF structure).
"""

from tlf_llm.prompts import SYSTEM_PROMPT as TLF_SYSTEM_PROMPT

# Re-export the shared system prompt (full shell spec with columns, rows, footnotes)
DEMO_SYSTEM_PROMPT = TLF_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Call 1: First table from index + first listing from index
# ---------------------------------------------------------------------------

FIRST_TLF_PROMPT = """## Task — Generate Exactly 2 Items

You must generate exactly **1 table** and **1 listing** as specified below.
Do NOT generate any other items. Do NOT generate figures.

### Item 1: Table — {first_table_title}

Generate a complete table shell for:
- **Title**: "{first_table_title}"
- **Population**: {first_table_population}
- **Number**: {first_table_number}

**CRITICAL — Use the EXACT number from the SAP index above. Do NOT invent sub-levels or change the numbering scheme.**

**SAP is the source of truth. Read the SAP to determine:**
1. The endpoint definition and type (find in protocol, methodology in SAP)
2. Which statistics to include — include ONLY what the SAP specifies, nothing more
3. Which visits/timepoints to include — use ONLY the timepoints specified in the SAP
4. Censoring rules and categories — use ONLY the categories defined in the SAP's censoring table
5. The study design type (superiority, equivalence, non-inferiority, etc.) — this affects footnote language
6. Exact treatment arm names from the protocol/SAP

**Resolving ambiguous terms:** When the SAP uses general terms (like "descriptive statistics") without defining them in the table-specific section, look for definitions in the SAP's General Methodology section.

**Requirements:**
- Use EXACT numbering from the SAP index — do not add sub-levels
- Include ONLY the statistics specified in the SAP for this endpoint type
- Include ONLY the visits/timepoints specified in the SAP
- Match censoring categories to the SAP's censoring definition table
- Footnotes must reflect the study design type (do not use superiority language for equivalence trials)
- If the SAP states that p-values are descriptive or that no multiplicity adjustment applies, include this in a footnote
- 95% CIs shown inline with the statistic where SAP specifies CIs

### Item 2: Listing — {first_listing_title}

Generate a complete listing shell for:
- **Title**: "{first_listing_title}"
- **Population**: {first_listing_population}
- **Number**: {first_listing_number}

**CRITICAL — Use the EXACT number from the SAP index. Do NOT convert to a different numbering scheme.**

**Read the SAP to determine:**
1. What variables are needed for this listing type
2. The population definition
3. Sort order and page break requirements

**Requirements:**
- Use EXACT numbering from the SAP index
- Include variables appropriate for the listing type based on SAP/protocol
- Clearly label columns to avoid ambiguity (specify review type if multiple exist)

---

## Protocol Content (source of truth for clinical details)

{protocol_text}

## Statistical Analysis Plan (analysis methodology, populations, TLF structure)

{sap_text}

---

## Output Format

Return valid JSON only:
{{
  "tables": [<the table>],
  "listings": [<the listing>]
}}

Each table must include complete columns, rows (with format codes, indentation, type, bold), footnotes, source, orientation, and programming_notes.
Each listing must include variables, source, orientation, sort_order, page_break_by, footnotes, and programming_notes.
"""


# ---------------------------------------------------------------------------
# Call 2: Clinical Chemistry CFB table + Clinical Chemistry listing
# ---------------------------------------------------------------------------

LAB_CHEMISTRY_PROMPT = """## Task — Generate Exactly 2 Items

You must generate exactly **1 table** and **1 listing** as specified below.
Do NOT generate any other items. Do NOT generate figures.

### Item 1: Table — {chem_table_title}

Generate a complete table shell for:
- **Title**: "{chem_table_title}"
- **Population**: {chem_table_population}
- **Number**: {chem_table_number}
- **Type**: labs_summary
- **Source dataset**: ADLB
- **Orientation**: LANDSCAPE

**CRITICAL — Use the EXACT number from the SAP index. Do NOT invent sub-levels.**

**SAP is the source of truth. Read the SAP to determine:**
1. Which descriptive statistics to include — use ONLY what the SAP specifies (do not add statistics the SAP doesn't list)
2. Which visits to include — use ALL visits specified in the SAP for this table type
3. Whether to include normal ranges — only if the SAP/title specifies it
4. The baseline definition

**Column structure:**
- Read the SAP to determine the column structure for this table type
- Use exact treatment arm names from the protocol/SAP

**Row structure — Hierarchical to avoid repetition:**
- First column header should be "Parameter / Visit / Statistic" to reflect the three-level hierarchy
- Parameter name appears ONCE as a header row (indent=0)
- Visit names appear as sub-headers (indent=1) — include ALL visits from the SAP
- Statistics appear as data rows (indent=2) — include ONLY statistics from the SAP
- Change from Baseline uses the SAME descriptive statistics as actual values (look up the SAP's definition)

**Footnotes:** Include only footnotes specified or implied by the SAP

### Item 2: Listing — {chem_listing_title}

Generate a complete listing shell for:
- **Title**: "{chem_listing_title}"
- **Population**: {chem_listing_population}
- **Number**: {chem_listing_number}
- **Type**: listing
- **Source dataset**: ADLB
- **Orientation**: LANDSCAPE

**CRITICAL — Use the EXACT number from the SAP index.**

**Read the protocol and SAP to determine:**
1. What columns are needed for this listing type
2. Whether toxicity grading applies (only if SAP/protocol specifies grading)
3. Whether baseline and change from baseline columns are needed (if SAP analyzes CFB, include these)
4. Whether clinical significance assessment applies (only if protocol specifies)

**Requirements:**
- Use EXACT numbering from the SAP index
- Include columns that support the analyses described in the SAP (if SAP analyzes CFB, listing should show baseline and CFB)
- Include grading column if SAP references a grading scale for this parameter type

---

## Protocol Content (source of truth for clinical details)

{protocol_text}

## Statistical Analysis Plan (analysis methodology, populations, TLF structure)

{sap_text}

---

## Output Format

Return valid JSON only:
{{
  "tables": [<the clinical chemistry table>],
  "listings": [<the clinical chemistry listing>]
}}

Each table must include complete columns, rows (with format codes, indentation, type, bold), footnotes, source, orientation, and programming_notes.
Each listing must include variables, source, orientation, sort_order, page_break_by, footnotes, and programming_notes.
"""
