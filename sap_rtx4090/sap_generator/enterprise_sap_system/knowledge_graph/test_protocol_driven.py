"""
Test: Protocol-Driven SAP Generation
=====================================

NO extractors, NO hardcoded rules.
Just tell Claude: "Read the protocol, generate SAP that matches it exactly."

The protocol is the source of truth.
"""

import os
import sys
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("Installing anthropic...")
    os.system("pip install anthropic")
    import anthropic


def generate_protocol_driven_sap(protocol_path: str, api_key: str) -> str:
    """
    Generate SAP by letting Claude read the protocol directly.

    NO templates. NO extractors. NO hardcoded rules.
    The protocol drives everything.
    """

    client = anthropic.Anthropic(api_key=api_key)

    # Read protocol
    protocol_content = Path(protocol_path).read_text(encoding='utf-8', errors='ignore')

    print(f"Protocol: {Path(protocol_path).name}")
    print(f"Length: {len(protocol_content)} chars")

    # Simple, direct prompt
    prompt = f"""You are a biostatistician creating a Statistical Analysis Plan (SAP).

Read this protocol carefully and generate a SAP that EXACTLY matches what's in the protocol.

## CRITICAL INSTRUCTIONS:

1. **THE PROTOCOL IS THE SOURCE OF TRUTH**
   - Only include variables that are mentioned or clearly implied in the protocol
   - Only include endpoints that are defined in the protocol
   - Only include populations that are described in the protocol
   - Use the exact statistical methods specified in the protocol

2. **DO NOT ADD GENERIC CONTENT**
   - If the protocol doesn't mention Race/Ethnicity, don't include them
   - If the protocol doesn't mention ECOG, don't include it
   - If the protocol uses ASA Score instead of ECOG, use ASA Score
   - If this is a post-surgery (adjuvant) study, don't include tumor response tables (CR/PR/SD/PD)

3. **MATCH THE STATISTICAL METHODS TO THE ENDPOINTS**
   - Time-to-event endpoints (DFS, OS, PFS, TTR) → Cox regression, Hazard Ratio, Kaplan-Meier
   - Binary endpoints (response rate) → Logistic regression or Fisher's exact, Odds Ratio or Risk Difference
   - Continuous endpoints → t-test or ANCOVA, Mean difference

4. **EXTRACT AND USE ACTUAL VALUES**
   - Sample size: Use what's in the protocol
   - Treatment arms: Use what's in the protocol
   - Stratification factors: Use what's in the protocol
   - Follow-up duration: Use what's in the protocol

5. **GENERATE TABLE SHELLS THAT MATCH THE PROTOCOL**
   - Baseline tables should have columns matching the actual treatment arms
   - Variables in tables should be the ones actually collected per the protocol
   - Use appropriate summary statistics (n(%) for categorical, median/IQR for continuous)

## PROTOCOL:

{protocol_content[:20000]}

---

Now generate a complete SAP that exactly matches this specific protocol.
Do not use generic templates. Extract everything from the protocol above.

If something is not specified in the protocol, either:
- Mark it as [TO BE CONFIRMED]
- Or omit it entirely

Generate the SAP now:"""

    print("\nGenerating SAP with Claude...")

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not set")
        return

    # Test with different protocols
    test_protocols = [
        # Nordic adjuvant CRC (should NOT have Race/Ethnicity, should NOT have tumor response)
        Path(__file__).parent.parent.parent / "data/all_pairs/NCT03558139_protocol.txt",
        # US metastatic study (should have Race/Ethnicity, should have tumor response)
        Path(__file__).parent.parent.parent / "data/all_pairs/NCT00938041_protocol.txt",
    ]

    for protocol_path in test_protocols:
        if not protocol_path.exists():
            print(f"⚠️ Protocol not found: {protocol_path}")
            continue

        print("\n" + "="*70)
        print(f"TESTING: {protocol_path.name}")
        print("="*70)

        sap = generate_protocol_driven_sap(str(protocol_path), api_key)

        # Save output
        output_dir = Path(__file__).parent / "output"
        output_dir.mkdir(exist_ok=True)

        output_file = output_dir / f"protocol_driven_{protocol_path.stem}_sap.md"
        output_file.write_text(sap)

        print(f"\n✅ SAP saved: {output_file}")

        # Quick validation
        print("\n--- VALIDATION ---")
        sap_lower = sap.lower()

        # Check what's in the SAP
        checks = [
            ("Race/Ethnicity", "race" in sap_lower or "ethnicity" in sap_lower),
            ("ECOG", "ecog" in sap_lower),
            ("ASA Score", "asa score" in sap_lower or "asa physical" in sap_lower),
            ("Tumor Response (CR/PR/SD/PD)", "complete response" in sap_lower or "partial response" in sap_lower or "stable disease" in sap_lower),
            ("Disease-Free Survival", "disease-free" in sap_lower or "disease free" in sap_lower),
            ("Hazard Ratio", "hazard ratio" in sap_lower),
            ("Odds Ratio", "odds ratio" in sap_lower),
            ("Cox Regression", "cox" in sap_lower),
            ("Kaplan-Meier", "kaplan" in sap_lower),
        ]

        for name, found in checks:
            status = "✓ FOUND" if found else "✗ not found"
            print(f"  {name}: {status}")

        # Print first 1500 chars
        print("\n--- SAP PREVIEW ---")
        print(sap[:1500])
        print("\n... (see full file)")


if __name__ == "__main__":
    main()
