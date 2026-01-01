#!/usr/bin/env python3
"""
Pipeline Integration Test
==========================

Run this before committing to catch integration errors.

Usage:
    python test_pipeline.py
    python test_pipeline.py NCT03197467
"""

import sys


def test_api_extractor():
    """Test API extractor works"""
    print("\n[TEST 1] API Extractor...")
    from enterprise_sap_system.core.api_extractor import ClinicalTrialsAPIExtractor

    extractor = ClinicalTrialsAPIExtractor()
    facts = extractor.fetch("NCT03197467")

    assert facts.api_success, f"API failed: {facts.api_error}"
    assert facts.nct_id == "NCT03197467"
    assert facts.sample_size > 0
    assert facts.primary_endpoints, "No primary endpoints"

    print(f"  ✓ API extraction works")
    print(f"    NCT: {facts.nct_id}, Sample: {facts.sample_size}, Drug: {facts.drug_name}")
    return True


def test_section_parser():
    """Test section parser works"""
    print("\n[TEST 2] Section Parser...")
    from enterprise_sap_system.core.section_parser import ProtocolSectionParser

    parser = ProtocolSectionParser()

    # Test with sample protocol text
    sample_text = """
    1. STUDY OBJECTIVES

    The primary objective is to evaluate efficacy.

    2. ENDPOINTS

    Primary Endpoint: Overall Response Rate
    Secondary Endpoints: Duration of Response, PFS

    3. STATISTICAL METHODS

    The primary analysis will use ANCOVA with baseline as covariate.
    Missing data will be handled using MMRM.
    """

    parsed = parser.parse(sample_text)

    assert parsed.parse_success, "Parsing failed"
    assert parsed.section_count > 0, "No sections found"

    print(f"  ✓ Section parsing works")
    print(f"    Found {parsed.section_count} sections: {list(parsed.sections.keys())}")
    return True


def test_unified_extractor():
    """Test unified extractor works"""
    print("\n[TEST 3] Unified Extractor...")
    from enterprise_sap_system.core.unified_extractor import UnifiedExtractor

    extractor = UnifiedExtractor(
        use_api=True,
        use_llm=False,  # Skip LLM for faster testing
        use_regex_fallback=True,
        verbose=False
    )

    # Test with NCT ID
    facts = extractor.extract("NCT03197467", nct_id="NCT03197467")

    assert facts.api_success, f"API extraction failed"
    assert facts.primary_endpoint, "No primary endpoint"
    assert facts.sample_size > 0, "No sample size"

    print(f"  ✓ Unified extraction works")
    print(f"    Sources: {facts.sources_used}")
    print(f"    Primary endpoint: {facts.primary_endpoint[:60]}...")
    return True


def test_full_pipeline(nct_id: str = "NCT03197467"):
    """Test full pipeline with a real NCT ID"""
    print(f"\n[TEST 4] Full Pipeline (NCT: {nct_id})...")
    from enterprise_sap_system.core.hybrid_pipeline import HybridSAPPipeline

    pipeline = HybridSAPPipeline(
        use_rag=False,  # Skip RAG for faster testing
        use_validation=False,
        verbose=False
    )

    # Minimal protocol text with NCT ID
    protocol_text = f"""
    Protocol: {nct_id}

    This is a clinical trial protocol.
    """

    result = pipeline.generate(protocol_text, nct_id=nct_id)

    if not result.success:
        print(f"  ✗ Pipeline failed: {result.errors}")
        return False

    assert result.sap_text, "No SAP text generated"
    assert len(result.sap_text) > 1000, f"SAP too short: {len(result.sap_text)} chars"

    print(f"  ✓ Pipeline works")
    print(f"    Generated {len(result.sap_text)} chars")
    print(f"    Warnings: {len(result.warnings)}")

    if result.warnings:
        for w in result.warnings[:3]:
            print(f"      - {w[:80]}")

    return True


def run_all_tests(nct_id: str = None):
    """Run all tests"""
    print("=" * 60)
    print("SAP Pipeline Integration Tests")
    print("=" * 60)

    tests = [
        test_api_extractor,
        test_section_parser,
        test_unified_extractor,
    ]

    # Add full pipeline test
    if nct_id:
        tests.append(lambda: test_full_pipeline(nct_id))
    else:
        tests.append(test_full_pipeline)

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    nct_id = sys.argv[1] if len(sys.argv) > 1 else None
    success = run_all_tests(nct_id)
    sys.exit(0 if success else 1)
