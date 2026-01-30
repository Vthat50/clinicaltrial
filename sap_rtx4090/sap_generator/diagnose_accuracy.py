"""
Run this on a specific protocol to see WHERE accuracy is lost.
Usage: python diagnose_accuracy.py /path/to/protocol.pdf
"""
import sys
import json
sys.path.insert(0, '.')

def diagnose(pdf_path: str):
    print("=" * 70)
    print(f"DIAGNOSING: {pdf_path}")
    print("=" * 70)
    
    # Step 1: Parse with LlamaParse
    print("\n[STEP 1] LlamaParse Extraction")
    print("-" * 70)
    from enterprise_sap_system.core.section_parser import ProtocolSectionParser
    parser = ProtocolSectionParser()
    parsed = parser.parse(pdf_path)
    
    print(f"Sections found: {list(parsed.sections.keys())}")
    for name, section in parsed.sections.items():
        print(f"  {name}: {len(section.content)} chars, confidence={section.confidence:.2f}")
    
    # Step 2: Extract facts
    print("\n[STEP 2] Fact Extraction (Claude)")
    print("-" * 70)
    from enterprise_sap_system.core.sectioned_extractor import SectionedProtocolExtractor
    
    # Read the PDF text
    with open(pdf_path, 'rb') as f:
        # For now just use parsed content
        protocol_text = "\n\n".join([s.content for s in parsed.sections.values()])
    
    extractor = SectionedProtocolExtractor()
    facts = extractor.extract_all_sections(protocol_text, pdf_path)
    
    # Show critical extracted values
    print("\n📊 CRITICAL EXTRACTED VALUES (verify these against protocol):")
    critical_fields = [
        'sample_size', 'total_sample_size', 'power', 'alpha', 'alpha_level',
        'primary_endpoint', 'primary_endpoints', 'hazard_ratio', 'target_hr',
        'interim_analyses', 'number_of_interim_analyses',
        'randomization_ratio', 'treatment_arms'
    ]
    
    facts_dict = facts if isinstance(facts, dict) else facts.__dict__
    
    for field in critical_fields:
        value = facts_dict.get(field, 'NOT EXTRACTED')
        if value and value != 'NOT EXTRACTED':
            print(f"  ✓ {field}: {str(value)[:80]}")
        else:
            print(f"  ✗ {field}: NOT FOUND")
    
    # Step 3: Show what goes into generation prompt
    print("\n[STEP 3] What gets sent to generation LLM")
    print("-" * 70)
    print("Facts that will be used for SAP generation:")
    print(json.dumps(facts_dict, indent=2, default=str)[:2000])
    
    print("\n" + "=" * 70)
    print("DIAGNOSIS COMPLETE")
    print("=" * 70)
    print("""
    COMPARE the extracted values above against your protocol PDF.
    
    If values are WRONG here → Problem is in EXTRACTION (Step 1-2)
    If values are RIGHT here → Problem is in GENERATION (LLM ignoring facts)
    """)
    
    return facts_dict

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python diagnose_accuracy.py /path/to/protocol.pdf")
        sys.exit(1)
    diagnose(sys.argv[1])
