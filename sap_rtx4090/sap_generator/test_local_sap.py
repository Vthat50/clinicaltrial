#!/usr/bin/env python3
"""Quick local test of SAP generation to check if tables are generated."""

import sys
sys.path.insert(0, '/mnt/c/Users/vijay/OneDrive/Documents/Github/clinicaltrial/sap_rtx4090/sap_generator')

from enterprise_sap_system.core.two_pass_extractor import TwoPassExtractor

# Use the test PDF
pdf_path = '/mnt/c/Users/vijay/Downloads/Testing/test3protocol.pdf'

print(f"Testing with PDF: {pdf_path}")
print("=" * 70)

# Initialize and run
extractor = TwoPassExtractor()
result = extractor.process_pdf(
    pdf_path=pdf_path,
    protocol_id="test3protocol",
    validate=False,  # Skip validation for speed
    verbose=True
)

sap_text = result.get("sap_text", "")

print("\n" + "=" * 70)
print("CHECKING SAP OUTPUT")
print("=" * 70)
print(f"SAP length: {len(sap_text)} chars")

# Check for markdown tables - Claude uses |--------| format, not |---|
has_markdown = '|--' in sap_text and '--|' in sap_text
table_count = sap_text.count('|--')
print(f"Has markdown tables: {has_markdown} (found {table_count} table rows)")

# Check for placeholders
has_placeholder = '[Primary endpoint as specified]' in sap_text
print(f"Has placeholder text: {has_placeholder}")

# Check for Section 12
has_section_12 = '## 12.' in sap_text or '# 12.' in sap_text or '12. APPENDICES' in sap_text
print(f"Has Section 12: {has_section_12}")

# Check for APPENDIX: TLF
has_appendix_tlf = 'APPENDIX: TLF' in sap_text or 'APPENDIX:' in sap_text
print(f"Has 'APPENDIX:' section: {has_appendix_tlf}")

# Save SAP for inspection
output_path = '/mnt/c/Users/vijay/Desktop/sap_data/test_sap_output.md'
with open(output_path, 'w') as f:
    f.write(sap_text)
print(f"\nSAP saved to: {output_path}")

# Show last 2000 chars (Section 12 area)
print("\n" + "=" * 70)
print("LAST 2000 CHARS OF SAP (Section 12 area):")
print("=" * 70)
print(sap_text[-2000:])
