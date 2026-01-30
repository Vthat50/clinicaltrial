"""
Test: Metastatic Renal Cell Carcinoma - RECIST-based response
"""

import os
from pathlib import Path
import anthropic


def test_metastatic():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set")
        return

    client = anthropic.Anthropic(api_key=api_key)

    # Metastatic RCC with RECIST
    protocol_path = Path(__file__).parent.parent.parent / "data/all_pairs/NCT00726323_protocol.txt"
    protocol_content = protocol_path.read_text(encoding='utf-8', errors='ignore')

    print("="*70)
    print("TEST: METASTATIC RCC STUDY (NCT00726323)")
    print("="*70)
    print("\nProtocol Key Facts:")
    print("  - Phase 2 renal cell carcinoma")
    print("  - Metastatic disease (measurable tumors)")
    print("  - Primary: Overall Response Rate (RECIST 1.0)")
    print("  - ECOG Performance Status mentioned")
    print("\nExpected SAP:")
    print("  Should include RECIST tumor response (CR/PR/SD/PD)")
    print("  Should include ORR, DCR, PFS, DOR")
    print("  Should include ECOG (in protocol)")
    print("  Should use Kaplan-Meier for PFS/DOR")
    print()

    prompt = f"""You are a biostatistician creating a Statistical Analysis Plan (SAP).

Read this protocol carefully and generate a SAP that EXACTLY matches what's in the protocol.

## CRITICAL INSTRUCTIONS:

1. **THE PROTOCOL IS THE SOURCE OF TRUTH**
   - Only include endpoints and analyses that are in the protocol
   - Use the exact response criteria specified (RECIST 1.0)

2. **UNDERSTAND THIS STUDY**
   - This is a metastatic solid tumor study
   - Has measurable disease assessed by RECIST
   - Primary is Overall Response Rate
   - Include appropriate tumor response tables

3. **MATCH STATISTICAL METHODS TO ENDPOINTS**
   - ORR -> Exact binomial confidence intervals
   - PFS, DOR -> Kaplan-Meier, median with 95% CI

## PROTOCOL:

{protocol_content}

---

Generate a SAP for this metastatic renal cell carcinoma study.
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
    output_file = output_dir / "metastatic_recist_test_sap.md"
    output_file.write_text(sap)
    print(f"\n SAP saved: {output_file}")

    # Validate
    print("\n--- VALIDATION ---")
    sap_lower = sap.lower()

    checks = [
        ("ECOG", "ecog" in sap_lower, True, "In protocol"),
        ("RECIST", "recist" in sap_lower, True, "Response criteria"),
        ("Overall Response Rate/ORR", "response rate" in sap_lower or "orr" in sap_lower, True, "Primary endpoint"),
        ("Complete Response", "complete response" in sap_lower or " cr " in sap_lower, True, "RECIST category"),
        ("Partial Response", "partial response" in sap_lower or " pr " in sap_lower, True, "RECIST category"),
        ("Stable Disease", "stable disease" in sap_lower or " sd " in sap_lower, True, "RECIST category"),
        ("Progressive Disease", "progressive disease" in sap_lower or " pd " in sap_lower, True, "RECIST category"),
        ("PFS", "progression-free" in sap_lower or "progression free" in sap_lower or "pfs" in sap_lower, True, "Secondary endpoint"),
        ("Kaplan-Meier", "kaplan" in sap_lower, True, "For time-to-event"),
        ("Foretinib", "foretinib" in sap_lower, True, "Study drug"),
    ]

    all_pass = True
    for name, found, should_be_found, reason in checks:
        if found == should_be_found:
            status = "PASS"
        else:
            status = "FAIL"
            all_pass = False

        present = "FOUND" if found else "NOT FOUND"
        expected = "Expected" if should_be_found else "Should NOT appear"
        print(f"  {status}: {name} - {present} ({expected}: {reason})")

    print("\n" + "="*70)
    if all_pass:
        print("ALL CHECKS PASSED!")
    else:
        print("SOME CHECKS FAILED - Review the SAP")
    print("="*70)

    # Print preview
    print("\n--- SAP PREVIEW ---")
    print(sap[:2500])


if __name__ == "__main__":
    test_metastatic()
