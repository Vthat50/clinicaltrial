"""
Test: Prostate Cancer Study - PSA-based progression (not RECIST)
"""

import os
from pathlib import Path
import anthropic


def test_prostate():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set")
        return

    client = anthropic.Anthropic(api_key=api_key)

    # Prostate cancer study
    protocol_path = Path(__file__).parent.parent.parent / "data/all_pairs/NCT00470834_protocol.txt"
    protocol_content = protocol_path.read_text(encoding='utf-8', errors='ignore')

    print("="*70)
    print("TEST: PROSTATE CANCER STUDY (NCT00470834)")
    print("="*70)
    print("\nProtocol Key Facts:")
    print("  - Phase 4 randomized, double-blind")
    print("  - Prostate cancer (failed first-line androgen deprivation)")
    print("  - Primary: Time to Disease Progression (PSA-based)")
    print("  - ECOG Performance Status mentioned")
    print("\nExpected SAP:")
    print("  Should use Cox/Kaplan-Meier for time-to-event")
    print("  Should include ECOG (in protocol)")
    print("  Should include PSA endpoints")
    print("  Should NOT have standard RECIST tumor response (CR/PR/SD/PD)")
    print()

    prompt = f"""You are a biostatistician creating a Statistical Analysis Plan (SAP).

Read this protocol carefully and generate a SAP that EXACTLY matches what's in the protocol.

## CRITICAL INSTRUCTIONS:

1. **THE PROTOCOL IS THE SOURCE OF TRUTH**
   - Only include variables, endpoints, and analyses that are in the protocol
   - Do not add generic oncology content that isn't relevant

2. **UNDERSTAND THIS STUDY**
   - This is a prostate cancer study
   - Disease progression is assessed by PSA (prostate-specific antigen)
   - This is NOT a standard solid tumor study with RECIST measurements
   - Therefore: use PSA-based endpoints, NOT standard tumor response categories

3. **MATCH STATISTICAL METHODS TO ENDPOINTS**
   - Time-to-event endpoints -> Cox regression, Hazard Ratio, Kaplan-Meier
   - PSA response -> appropriate categorical analysis

## PROTOCOL:

{protocol_content}

---

Generate a SAP for this prostate cancer study.
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
    output_file = output_dir / "prostate_test_sap.md"
    output_file.write_text(sap)
    print(f"\n SAP saved: {output_file}")

    # Validate
    print("\n--- VALIDATION ---")
    sap_lower = sap.lower()

    checks = [
        ("ECOG", "ecog" in sap_lower, True, "In protocol"),
        ("PSA", "psa" in sap_lower, True, "Primary endpoint based on PSA"),
        ("Kaplan-Meier", "kaplan" in sap_lower, True, "Time-to-event endpoint"),
        ("Cox/Hazard Ratio", "cox" in sap_lower or "hazard ratio" in sap_lower, True, "Time-to-event"),
        ("Time to Progression", "progression" in sap_lower, True, "Primary endpoint"),
        ("Dutasteride/Bicalutamide", "dutasteride" in sap_lower or "bicalutamide" in sap_lower, True, "Study drugs"),
        ("RECIST CR/PR/SD/PD",
         any(x in sap_lower for x in ["complete response", "partial response", "stable disease", "progressive disease"])
         and "recist" in sap_lower,
         False, "NOT a RECIST study"),
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
    test_prostate()
