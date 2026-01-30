#!/usr/bin/env python3
"""
Test the EXACT production flow - same as worker in main.py
This will show if the issue is in TwoPassExtractor or worker processing.
"""

import sys
sys.path.insert(0, '/mnt/c/Users/vijay/OneDrive/Documents/Github/clinicaltrial/sap_rtx4090/sap_generator')

from enterprise_sap_system.core.two_pass_extractor import TwoPassExtractor

# Use the test PDF
pdf_path = '/mnt/c/Users/vijay/Downloads/Testing/test3protocol.pdf'

print("=" * 70)
print("TESTING EXACT PRODUCTION FLOW")
print("=" * 70)

# Step 1: Initialize and run TwoPassExtractor (same as production)
print("\n[STEP 1] Running TwoPassExtractor.process_pdf()...")
extractor = TwoPassExtractor()
result = extractor.process_pdf(
    pdf_path=pdf_path,
    protocol_id="test3protocol",
    validate=True,
    verbose=True
)

# Step 2: Get sap_text from result (same as worker line 3320)
sap_text = result.get("sap_text", "")
discovered_elements = result.get("discovered_elements", [])

print("\n" + "=" * 70)
print("[STEP 2] SAP FROM TwoPassExtractor:")
print("=" * 70)
print(f"  Length: {len(sap_text)} chars")
print(f"  Contains '|--': {'|--' in sap_text}")
print(f"  Contains '## 12.': {'## 12.' in sap_text}")

if '## 12.' in sap_text:
    sec12_pos = sap_text.find('## 12.')
    print(f"  Section 12 position: {sec12_pos}")
    print(f"  Section 12 preview:\n{sap_text[sec12_pos:sec12_pos+500]}")
else:
    print("  NO SECTION 12 FOUND!")
    print(f"  Last 500 chars:\n{sap_text[-500:]}")

# Step 3: Simulate worker's table check (EXACT code from main.py)
print("\n" + "=" * 70)
print("[STEP 3] WORKER TABLE CHECK (same as main.py):")
print("=" * 70)

# This is the EXACT code from main.py lines 3472-3482
section_12_start = -1
for marker in ['## 12.', '# 12.', '12. APPENDICES', '12. Appendices']:
    if marker in sap_text:
        section_12_start = sap_text.find(marker)
        break

if section_12_start >= 0:
    section_12_text = sap_text[section_12_start:]
    has_markdown_tables = '|--' in section_12_text and '--|' in section_12_text
else:
    has_markdown_tables = False

print(f"  Section 12 start: {section_12_start}")
print(f"  Has markdown tables IN Section 12: {has_markdown_tables}")

if not has_markdown_tables:
    print("\n  >>> WORKER WOULD INJECT TLF TABLES <<<")
else:
    print("\n  >>> WORKER WOULD KEEP EXISTING TABLES <<<")

# Step 4: Save output for inspection
output_path = '/mnt/c/Users/vijay/Desktop/sap_data/test_production_flow.md'
with open(output_path, 'w') as f:
    f.write(sap_text)
print(f"\n[STEP 4] SAP saved to: {output_path}")

# Step 5: Count tables
table_count = sap_text.count('|--')
print(f"\n[STEP 5] Total markdown table rows: {table_count}")

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
