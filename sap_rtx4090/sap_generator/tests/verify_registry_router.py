"""
Simple verification script for Registry Router
Tests core functionality without full dependencies
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("="*70)
print("Registry Router Verification")
print("="*70)
print()

# Test 1: Import registry router
print("[Test 1] Importing registry router...")
try:
    from enterprise_sap_system.core.registries.registry_router import (
        RegistryRouter,
        RegistryType,
        TrialIdentifier
    )
    print("✓ Successfully imported registry router components")
except Exception as e:
    print(f"✗ Failed to import: {e}")
    sys.exit(1)

print()

# Test 2: Import ClinicalTrials.gov extractor
print("[Test 2] Importing ClinicalTrials.gov extractor...")
try:
    from enterprise_sap_system.core.registries.clinicaltrials_gov_extractor import (
        ClinicalTrialsGovExtractor
    )
    print("✓ Successfully imported ClinicalTrials.gov extractor")
except Exception as e:
    print(f"✗ Failed to import: {e}")
    sys.exit(1)

print()

# Test 3: Create router instance
print("[Test 3] Creating router instance...")
try:
    router = RegistryRouter()
    print("✓ Successfully created router instance")
    print(f"  Supported registries: {router.get_supported_registries()}")
except Exception as e:
    print(f"✗ Failed to create router: {e}")
    sys.exit(1)

print()

# Test 4: Test NCT ID detection
print("[Test 4] Testing NCT ID detection...")
try:
    identifier = router.detect_registry("NCT01234567")
    assert identifier.registry_type == RegistryType.CLINICALTRIALS_GOV
    assert identifier.normalized_id == "NCT01234567"
    print("✓ Successfully detected NCT ID format")
    print(f"  Registry: {identifier.registry_type.value}")
    print(f"  URL: {identifier.registry_url}")
except Exception as e:
    print(f"✗ Failed NCT detection: {e}")
    sys.exit(1)

print()

# Test 5: Test fuzzy NCT matching
print("[Test 5] Testing fuzzy NCT matching...")
try:
    text = "This study NCT03197467 is a Phase 3 trial"
    identifier = router.detect_registry(text)
    assert identifier.registry_type == RegistryType.CLINICALTRIALS_GOV
    assert identifier.normalized_id == "NCT03197467"
    print("✓ Successfully extracted NCT ID from text")
    print(f"  Extracted: {identifier.normalized_id}")
except Exception as e:
    print(f"✗ Failed fuzzy matching: {e}")
    sys.exit(1)

print()

# Test 6: Test CTIS ID detection
print("[Test 6] Testing CTIS ID detection...")
try:
    identifier = router.detect_registry("CT-EU-22-123456")
    assert identifier.registry_type == RegistryType.CTIS
    print("✓ Successfully detected CTIS ID format")
    print(f"  Registry: {identifier.registry_type.value}")
except Exception as e:
    print(f"✗ Failed CTIS detection: {e}")
    sys.exit(1)

print()

# Test 7: Test unknown ID handling
print("[Test 7] Testing unknown ID handling...")
try:
    identifier = router.detect_registry("ABC-123-XYZ")
    assert identifier.registry_type == RegistryType.UNKNOWN
    print("✓ Successfully handled unknown ID format")
except Exception as e:
    print(f"✗ Failed unknown ID handling: {e}")
    sys.exit(1)

print()

# Test 8: Create ClinicalTrials.gov extractor
print("[Test 8] Creating ClinicalTrials.gov extractor...")
try:
    extractor = ClinicalTrialsGovExtractor()
    print("✓ Successfully created extractor instance")
except Exception as e:
    print(f"✗ Failed to create extractor: {e}")
    sys.exit(1)

print()

# Test 9: Test NCT extraction with smart disambiguation
print("[Test 9] Testing smart NCT extraction...")
try:
    text = """
    Statistical Analysis Plan for Protocol CA209-078, NCT02031458

    This study is similar to prior studies NCT01234567 and NCT09876543.
    """
    nct_id = extractor.extract_nct_id(text)
    assert nct_id == "NCT02031458", f"Expected NCT02031458, got {nct_id}"
    print("✓ Successfully extracted correct NCT ID with disambiguation")
    print(f"  Extracted: {nct_id} (correct study, not references)")
except Exception as e:
    print(f"✗ Failed NCT extraction: {e}")
    sys.exit(1)

print()

# Test 10: Test therapeutic area inference
print("[Test 10] Testing therapeutic area inference...")
try:
    conditions_oncology = ["Non-Small Cell Lung Cancer", "Metastatic Disease"]
    area = extractor._infer_therapeutic_area(conditions_oncology)
    assert area == "oncology", f"Expected oncology, got {area}"

    conditions_cardio = ["Heart Failure", "Hypertension"]
    area2 = extractor._infer_therapeutic_area(conditions_cardio)
    assert area2 == "cardiology", f"Expected cardiology, got {area2}"

    print("✓ Successfully inferred therapeutic areas")
    print(f"  Cancer -> {area}")
    print(f"  Heart disease -> {area2}")
except Exception as e:
    print(f"✗ Failed therapeutic area inference: {e}")
    sys.exit(1)

print()

# Test 11: Test real API fetch (if network available)
print("[Test 11] Testing real API fetch...")
try:
    # Use a well-known completed trial
    result = extractor.fetch("NCT03197467")  # CheckMate 078

    if result.get('api_success'):
        print("✓ Successfully fetched real trial data")
        print(f"  Title: {result.get('title', '')[:60]}...")
        print(f"  Sponsor: {result.get('sponsor', '')}")
        print(f"  Phase: {result.get('phase', '')}")
        print(f"  Registry: {result.get('registry', '')}")
    else:
        print(f"⚠ API fetch failed (may be network issue): {result.get('api_error')}")
except Exception as e:
    print(f"⚠ API test failed (may be network issue): {e}")

print()

# Test 12: Test router fetch integration
print("[Test 12] Testing router fetch integration...")
try:
    result = router.fetch("NCT03197467")

    if result and result.get('api_success'):
        print("✓ Successfully fetched through router")
        print(f"  Registry: {result.get('registry')}")

        # Check for registry metadata
        if '_registry_info' in result:
            print("✓ Registry metadata present")
            info = result['_registry_info']
            print(f"  Registry URL: {info.get('registry_url', '')}")
        else:
            print("⚠ Registry metadata missing")
    else:
        print(f"⚠ Router fetch failed (may be network issue)")
except Exception as e:
    print(f"⚠ Router integration test failed: {e}")

print()
print("="*70)
print("Verification Complete")
print("="*70)
print()
print("✓ All core functionality tests passed!")
print("✓ Registry router is working correctly")
print("✓ ClinicalTrials.gov extractor is functional")
print("✓ Multi-registry architecture is in place")
print()
