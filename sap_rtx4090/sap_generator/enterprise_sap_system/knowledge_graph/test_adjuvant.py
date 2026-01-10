"""
Test: Adjuvant Study - Should NOT have tumor response tables
"""

import os
from pathlib import Path
import anthropic


def test_adjuvant():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not set")
        return

    client = anthropic.Anthropic(api_key=api_key)

    # Adjuvant NSCLC study
    protocol_path = Path(__file__).parent.parent.parent / "data/all_pairs/NCT01853878_protocol.txt"
    protocol_content = protocol_path.read_text(encoding='utf-8', errors='ignore')

    print("="*70)
    print("TEST: ADJUVANT NSCLC STUDY (NCT01853878)")
    print("="*70)
    print("\nProtocol Key Facts:")
    print("  • Type: Adjuvant (post-surgical resection)")
    print("  • Primary: Time to Recurrence")
    print("  • No measurable disease at baseline")
    print("\nExpected SAP:")
    print("  ✓ Should use Cox regression / Kaplan-Meier for time-to-event")
    print("  ✗ Should NOT have tumor response tables (CR/PR/SD/PD)")
    print("  ✓ Should have ECOG (mentioned in protocol)")
    print()

    prompt = f"""You are a biostatistician creating a Statistical Analysis Plan (SAP).

Read this protocol carefully and generate a SAP that EXACTLY matches what's in the protocol.

## CRITICAL INSTRUCTIONS:

1. **THE PROTOCOL IS THE SOURCE OF TRUTH**
   - Only include variables, endpoints, and analyses that are in the protocol
   - Do not add generic oncology content that isn't relevant to this specific study

2. **UNDERSTAND THE STUDY TYPE**
   - This is an ADJUVANT study (post-surgical resection)
   - Patients have NO MEASURABLE DISEASE at baseline
   - Primary endpoint is TIME TO RECURRENCE (time-to-event)
   - Therefore: NO tumor response tables (CR/PR/SD/PD) are needed

3. **MATCH STATISTICAL METHODS TO ENDPOINTS**
   - Time-to-event endpoints → Cox regression, Hazard Ratio, Kaplan-Meier
   - Do NOT use tumor response categories for adjuvant studies

## PROTOCOL:

{protocol_content[:15000]}

---

Generate a SAP for this ADJUVANT study. Remember: no tumor response tables.
"""

    print("Generating SAP...")
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=6000,
        messages=[{"role": "user", "content": prompt}]
    )

    sap = response.content[0].text

    # Save
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "adjuvant_test_sap.md"
    output_file.write_text(sap)
    print(f"\n✅ SAP saved: {output_file}")

    # Validate
    print("\n--- VALIDATION ---")
    sap_lower = sap.lower()

    critical_checks = [
        ("ECOG", "ecog" in sap_lower, True, "Expected (in protocol)"),
        ("Kaplan-Meier", "kaplan" in sap_lower, True, "Expected for time-to-event"),
        ("Cox Regression/Hazard Ratio", "cox" in sap_lower or "hazard ratio" in sap_lower, True, "Expected for time-to-event"),
        ("Time to Recurrence", "recurrence" in sap_lower, True, "Primary endpoint"),
        ("Tumor Response CR/PR/SD/PD",
         any(x in sap_lower for x in ["complete response", "partial response", "stable disease", "progressive disease", "best overall response"]),
         False, "Should NOT be included - adjuvant study!"),
        ("RECIST", "recist" in sap_lower, False, "Should NOT be included - no measurable disease"),
    ]

    all_pass = True
    for name, found, should_be_found, reason in critical_checks:
        if found == should_be_found:
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
            all_pass = False

        present = "FOUND" if found else "NOT FOUND"
        expected = "Expected" if should_be_found else "Should NOT appear"
        print(f"  {status}: {name} - {present} ({expected}: {reason})")

    print("\n" + "="*70)
    if all_pass:
        print("✅ ALL CHECKS PASSED - Claude correctly handled adjuvant study!")
    else:
        print("❌ SOME CHECKS FAILED - Review the SAP")
    print("="*70)

    # Print preview
    print("\n--- SAP PREVIEW (first 2000 chars) ---")
    print(sap[:2000])


if __name__ == "__main__":
    test_adjuvant()
