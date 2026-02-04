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
- **Section**: {first_table_number}

**How to read the protocol and SAP:**
1. Find the endpoint definition in the protocol — read the full definition including measurement method and assessment criteria
2. Determine the endpoint type (time-to-event, binary, continuous, etc.) from the definition and SAP methodology section
3. Read the analysis population definition section for the full inclusion criteria
4. Extract exact treatment arm names as written in the protocol
5. Find stratification factors in the randomization and statistical methods sections
6. Read the SAP to determine which statistics, rows, and footnotes to include for this endpoint type

**Requirements:**
- Use the exact treatment arm names from the protocol/SAP in column headers
- Determine the correct type, source dataset, and orientation based on the endpoint type
- Follow ALL domain-specific row requirements and format code definitions from the system prompt for this endpoint type
- Each row must specify the appropriate format code from the system prompt's format code list
- Follow the statistical methodology specified in the SAP
- 95% CIs must be shown INLINE with the statistic (inside the same format code), NOT as separate rows
- Include footnotes as specified in the SAP: population definition, statistical methods with CI method names, and any domain-specific notes

### Item 2: Listing — {first_listing_title}

Generate a complete listing shell for:
- **Title**: "{first_listing_title}"
- **Population**: {first_listing_population}
- **Section**: {first_listing_number}
- **Type**: listing
- **Orientation**: LANDSCAPE

**How to read the protocol and SAP:**
1. Determine the source dataset from the listing content
2. Identify all relevant variables a statistical programmer would need for this listing type
3. Find the population definition in the protocol/SAP

**Requirements:**
- Include all relevant column variables for this listing type
- **Sort order**: Specify using the `sort_order` field based on the listing content
- **Page break**: Specify `page_break_by` based on the primary grouping variable
- **Footnotes**: Include population definition, sort order description, and any relevant methodology from the protocol/SAP
- **Programming notes**: Include key ADaM variable mappings and filtering criteria

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
- **Section**: {chem_table_number}
- **Type**: labs_summary
- **Source dataset**: ADLB
- **Orientation**: LANDSCAPE

**How to read the protocol and SAP:**
1. Find the laboratory assessments section — identify all clinical chemistry parameters collected in this study
2. Find the visit schedule — identify every visit where labs are collected across all treatment periods
3. Determine the unit system (SI or conventional) from the protocol
4. Find the baseline definition and statistical methodology in the SAP
5. Read the SAP title to determine the visit structure (by visit vs. summary)

**Column structure:**
- Column 1: Parameter (unit) / Normal Range
- Column 2: Visit (from the protocol schedule)
- Column 3: Statistic (as specified in SAP)
- Columns 4+: One column per treatment arm using exact names from protocol/SAP with (N=xxx)
- Do NOT include a Total column for lab tables

**Row structure:**
- Read the SAP to determine which statistics to include for each parameter
- Apply the SAME set of statistics consistently to ALL visits — do not show full statistics for baseline and abbreviated statistics for other visits
- Standard descriptive statistics for continuous lab values (unless SAP specifies otherwise): n, Mean, SD, Median, Q1, Q3, Min, Max
- If the SAP title says "by Visit": include rows for ALL scheduled assessment visits from the protocol visit schedule
- If the SAP title says "Actual and Change from Baseline" without "by Visit": show Baseline, End of Treatment, and Change from Baseline
- For post-baseline visits, include both actual values AND change from baseline, each with the full set of statistics
- Generate rows for all clinical chemistry parameters from the protocol
- For each parameter, generate FLAT rows (indent=0) with separate columns for Parameter, Visit, and Statistic
- Every row must include `label`, `visit`, `statistic`, `format`, `type`, `bold`, `indent` fields

**Footnotes:** Include population definition, baseline definition, and other footnotes as specified in the SAP

### Item 2: Listing — {chem_listing_title}

Generate a complete listing shell for:
- **Title**: "{chem_listing_title}"
- **Population**: {chem_listing_population}
- **Section**: {chem_listing_number}
- **Type**: listing
- **Source dataset**: ADLB
- **Orientation**: LANDSCAPE

**How to read the protocol:**
1. Check if CTCAE toxicity grading is applied to laboratory values in this study
2. Check if investigators assess clinical significance of abnormal values
3. Determine central vs local laboratory processing

**Variables:** A complete lab listing includes columns for:
- Subject identification and treatment assignment
- Parameter name and units
- Baseline value (for reference)
- Visit name and visit date
- Result value and change from baseline
- Reference range (low and high)
- Toxicity grading if applicable per protocol
- Clinical significance assessment if applicable per protocol

**Requirements:**
- **Sort order**: Specify using the `sort_order` field
- **Page break**: Specify `page_break_by` based on the primary grouping variable
- **Footnotes**: Include population definition, sort order, baseline definition, and other relevant notes
- **Programming notes**: Include key ADaM variable mappings and filtering criteria

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
