#!/usr/bin/env python3
"""
Enterprise SAP Generation System - Main Entry Point
=====================================================

Production-grade CLI for generating Statistical Analysis Plans from protocols.

Usage:
    # Generate SAP from a single protocol
    python -m enterprise_sap_system.main generate path/to/protocol.txt

    # Generate SAPs for multiple protocols
    python -m enterprise_sap_system.main batch path/to/protocols/

    # Test the system
    python -m enterprise_sap_system.main test

    # Show system info
    python -m enterprise_sap_system.main info
"""

import os
import sys
import json
import argparse
import time
from pathlib import Path
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from enterprise_sap_system.core import (
    get_config, create_parser, ParsedProtocol, EndpointType
)

# New KG Pipeline - Production SAP Generator
from enterprise_sap_system.knowledge_graph.kg_enhanced_pipeline import EnhancedKGPipeline
from enterprise_sap_system.knowledge_graph.regulatory_standards import get_standard_versions

# Legacy imports (kept for backward compatibility)
try:
    from enterprise_sap_system.knowledge_graph import create_graph_rag
    from enterprise_sap_system.agents import create_orchestrator, GenerationResult
    from enterprise_sap_system.few_shot import create_sap_database
    from enterprise_sap_system.cdisc import create_cdisc_mapper
    from enterprise_sap_system.templates import create_template_manager
    LEGACY_AVAILABLE = True
except ImportError:
    LEGACY_AVAILABLE = False


def test_protocol_parser():
    """Test the protocol parser with a sample protocol"""
    print("\n" + "="*60)
    print("Testing Protocol Parser")
    print("="*60)

    # Load a sample protocol
    config = get_config()
    data_dir = config.paths.all_pairs_dir

    # Find first protocol file
    protocol_files = list(data_dir.glob("*_protocol.txt"))
    if not protocol_files:
        print("ERROR: No protocol files found in data directory")
        return False

    protocol_path = protocol_files[0]
    nct_id = protocol_path.stem.replace("_protocol", "")

    print(f"\nLoading protocol: {nct_id}")

    try:
        protocol_text = protocol_path.read_text(encoding='utf-8', errors='ignore')
        print(f"Protocol length: {len(protocol_text):,} characters")

        # Parse protocol
        parser = create_parser()
        parsed = parser.parse(protocol_text, nct_id)

        print(f"\nParsed Protocol Results:")
        print(f"  NCT ID: {parsed.nct_id}")
        print(f"  Phase: {parsed.phase.value if hasattr(parsed.phase, 'value') else parsed.phase}")
        print(f"  Therapeutic Area: {parsed.therapeutic_area}")
        print(f"  Design: {parsed.design_type.value if hasattr(parsed.design_type, 'value') else parsed.design_type}")
        print(f"  Blinding: {parsed.blinding.value if hasattr(parsed.blinding, 'value') else parsed.blinding}")
        print(f"  Randomization: {parsed.randomization_ratio}")

        if parsed.primary_estimand:
            print(f"\n  Primary Endpoint:")
            print(f"    Type: {parsed.primary_estimand.variable_type.value}")
            print(f"    Variable: {parsed.primary_estimand.variable[:80]}...")

        print(f"\n  Extraction Confidence:")
        for key, conf in parsed.extraction_confidence.items():
            print(f"    {key}: {conf:.2f}")

        print("\n[PASS] Protocol parser test successful")
        return True

    except Exception as e:
        print(f"\n[FAIL] Protocol parser test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_knowledge_graph():
    """Test the knowledge graph and GraphRAG"""
    print("\n" + "="*60)
    print("Testing Knowledge Graph & GraphRAG")
    print("="*60)

    try:
        # Create GraphRAG
        print("\nInitializing GraphRAG...")
        graph_rag = create_graph_rag()

        # Check knowledge graph
        kg = graph_rag.knowledge_graph
        print(f"Knowledge graph has {kg.graph.number_of_nodes()} nodes and {kg.graph.number_of_edges()} edges")

        # Test entity retrieval
        os_entity = kg.get_entity("OS")
        if os_entity:
            print(f"\nOS Entity:")
            print(f"  Name: {os_entity.name}")
            print(f"  Type: {os_entity.entity_type}")
            print(f"  Description: {os_entity.description[:80]}...")

        # Test method retrieval for endpoint
        methods = graph_rag.get_methods_for_endpoint(EndpointType.OS)
        print(f"\nMethods for OS endpoint: {methods}")

        # Test ADaM mapping
        adam_mapping = graph_rag.get_adam_mapping(EndpointType.OS)
        print(f"ADaM mapping for OS: {adam_mapping}")

        print("\n[PASS] Knowledge graph test successful")
        return True

    except Exception as e:
        print(f"\n[FAIL] Knowledge graph test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_few_shot_database():
    """Test the few-shot example database"""
    print("\n" + "="*60)
    print("Testing Few-Shot Example Database")
    print("="*60)

    try:
        # Create database with limited pairs for testing
        print("\nLoading SAP pair database (max 50 pairs for test)...")
        database = create_sap_database()
        database.load_pairs(max_pairs=50)

        # Get statistics
        stats = database.get_statistics()
        print(f"\nDatabase Statistics:")
        print(f"  Total pairs: {stats['total_pairs']}")
        print(f"  By endpoint: {stats['by_endpoint']}")
        print(f"  By phase: {stats['by_phase']}")
        print(f"  Average quality: {stats['avg_quality_score']:.2f}")

        if stats['total_pairs'] > 0:
            # Test finding similar pairs
            print("\nTesting similarity search...")

            # Create a mock parsed protocol
            from enterprise_sap_system.core.schemas import Estimand
            mock_protocol = ParsedProtocol(
                nct_id="NCT00000000",
                phase=get_config().paths,  # Will be fixed
                therapeutic_area="Oncology"
            )
            mock_protocol.primary_estimand = Estimand(
                objective="Test",
                population="Test",
                treatment="Test",
                variable="PFS",
                variable_type=EndpointType.PFS,
                intercurrent_events=[],
                summary_measure="HR",
                analysis_method="Cox"
            )

            similar = database.find_similar(mock_protocol, n=3)
            print(f"Found {len(similar)} similar pairs")

            if similar:
                print(f"  Most similar: {similar[0].nct_id}")
                print(f"    Endpoint: {similar[0].endpoint_type}")
                print(f"    Sections extracted: {len(similar[0].sap_sections)}")

        print("\n[PASS] Few-shot database test successful")
        return True

    except Exception as e:
        print(f"\n[FAIL] Few-shot database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cdisc_mapper():
    """Test the CDISC mapper"""
    print("\n" + "="*60)
    print("Testing CDISC Mapper")
    print("="*60)

    try:
        mapper = create_cdisc_mapper()

        # Test OS mapping
        os_mapping = mapper.get_mapping(EndpointType.OS)
        print(f"\nOS Endpoint Mapping:")
        print(f"  Primary Dataset: {os_mapping.primary_dataset}")
        print(f"  Key Variables: {list(os_mapping.key_variables.keys())[:5]}")
        print(f"  Source SDTM: {os_mapping.source_sdtm}")

        # Test ADTTE dataset spec
        adtte = mapper.get_dataset_spec("ADTTE")
        print(f"\nADTTE Dataset:")
        print(f"  Label: {adtte.label}")
        print(f"  Structure: {adtte.structure}")
        print(f"  Key Variables: {adtte.key_variables}")
        print(f"  Variable count: {len(adtte.variables)}")

        # Test traceability generation
        from enterprise_sap_system.core.schemas import Estimand
        test_estimand = Estimand(
            objective="Test OS",
            population="All patients",
            treatment="Drug A vs Placebo",
            variable="Overall Survival",
            variable_type=EndpointType.OS,
            intercurrent_events=[],
            summary_measure="Hazard Ratio",
            analysis_method="Cox PH"
        )

        traceability = mapper.generate_traceability_section([test_estimand])
        print(f"\nGenerated traceability section ({len(traceability)} chars)")
        print(traceability[:500] + "...")

        print("\n[PASS] CDISC mapper test successful")
        return True

    except Exception as e:
        print(f"\n[FAIL] CDISC mapper test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_pipeline():
    """Test the full SAP generation pipeline"""
    print("\n" + "="*60)
    print("Testing Full SAP Generation Pipeline")
    print("="*60)

    # Check for API key
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("\nWARNING: GROQ_API_KEY not set. Skipping LLM-based tests.")
        print("Set GROQ_API_KEY to enable full pipeline testing.")
        return True  # Not a failure, just skipped

    try:
        # Load a protocol
        config = get_config()
        data_dir = config.paths.all_pairs_dir

        protocol_files = list(data_dir.glob("*_protocol.txt"))
        if not protocol_files:
            print("ERROR: No protocol files found")
            return False

        # Use a smaller protocol for faster testing
        protocol_files.sort(key=lambda p: p.stat().st_size)
        protocol_path = protocol_files[0]
        nct_id = protocol_path.stem.replace("_protocol", "")

        print(f"\nUsing protocol: {nct_id}")
        print(f"File size: {protocol_path.stat().st_size:,} bytes")

        protocol_text = protocol_path.read_text(encoding='utf-8', errors='ignore')

        # Create orchestrator
        print("\nInitializing orchestrator...")
        orchestrator = create_orchestrator(use_rag=True)

        # Generate SAP (with reduced sections for speed)
        print("\nGenerating SAP (this may take a few minutes)...")
        start_time = time.time()

        result = orchestrator.generate_sap(
            protocol_text=protocol_text[:50000],  # Limit size for speed
            nct_id=nct_id,
            use_few_shot=False,  # Disable for speed
            parallel_sections=False,
            verbose=True
        )

        elapsed = time.time() - start_time

        print(f"\n{'='*40}")
        print(f"Generation completed in {elapsed:.1f} seconds")
        print(f"Success: {result.success}")

        if result.success:
            print(f"SAP length: {len(result.sap_document.full_document):,} characters")
            print(f"Sections generated: {len(result.sap_document.sections)}")
            print(f"Quality score: {result.quality_report.overall_score:.1f}/100")

            if result.quality_report.issues:
                print(f"Issues: {result.quality_report.issues[:2]}")

            # Save the generated SAP
            output_dir = config.paths.output_dir / "test_outputs"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{nct_id}_generated_sap.md"
            output_path.write_text(result.sap_document.full_document, encoding='utf-8')
            print(f"\nSAP saved to: {output_path}")

            print("\n[PASS] Full pipeline test successful")
            return True
        else:
            print(f"Errors: {result.errors}")
            print("\n[FAIL] Full pipeline test failed")
            return False

    except Exception as e:
        print(f"\n[FAIL] Full pipeline test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*70)
    print("  ENTERPRISE SAP GENERATION SYSTEM - TEST SUITE")
    print("="*70)

    results = {}

    # Test 1: Protocol Parser
    results["Protocol Parser"] = test_protocol_parser()

    # Test 2: Knowledge Graph
    results["Knowledge Graph"] = test_knowledge_graph()

    # Test 3: Few-Shot Database
    results["Few-Shot Database"] = test_few_shot_database()

    # Test 4: CDISC Mapper
    results["CDISC Mapper"] = test_cdisc_mapper()

    # Test 5: Full Pipeline (if API key available)
    results["Full Pipeline"] = test_full_pipeline()

    # Summary
    print("\n" + "="*70)
    print("  TEST SUMMARY")
    print("="*70)

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {name}")

    print(f"\n  Total: {passed}/{total} tests passed")
    print("="*70)

    return passed == total


def generate_sap_cli(protocol_path: str, output_path: str = None, verbose: bool = True):
    """Generate SAP from a protocol file using Enhanced KG Pipeline"""
    protocol_path = Path(protocol_path)

    if not protocol_path.exists():
        print(f"ERROR: Protocol file not found: {protocol_path}")
        return False

    # Default output path
    if not output_path:
        output_dir = Path("output/generated_saps")
        output_dir.mkdir(parents=True, exist_ok=True)
        nct_id = protocol_path.stem.replace("_protocol", "")
        output_path = output_dir / f"{nct_id}_sap.md"

    print(f"\n{'='*70}")
    print("  ENHANCED KG PIPELINE - SAP GENERATOR")
    print(f"{'='*70}")
    print(f"\nProtocol: {protocol_path}")
    print(f"Output: {output_path}")

    # Get API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set")
        return False

    # Show regulatory standards
    versions = get_standard_versions()
    print(f"\nRegulatory Standards:")
    print(f"  MedDRA: {versions['MedDRA']}")
    print(f"  CTCAE: {versions['CTCAE']}")
    print(f"  WHO-DD: {versions['WHO_Drug']}")

    try:
        # Create Enhanced KG Pipeline
        pipeline = EnhancedKGPipeline(api_key)

        # Generate SAP
        result = pipeline.process_protocol(str(protocol_path))

        # Save SAP
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result["sap"])

        # Save provenance
        provenance_path = output_path.with_suffix('.provenance.json')
        with open(provenance_path, 'w') as f:
            json.dump(result["provenance"], f, indent=2)

        print(f"\n{'='*70}")
        print("  GENERATION COMPLETE")
        print(f"{'='*70}")
        print(f"\n✅ SAP saved to: {output_path}")
        print(f"✅ Provenance saved to: {provenance_path}")
        print(f"\nVerification:")
        print(f"  Score: {result['verification'].score:.2f}")
        print(f"  Passed: {result['verification'].passed}")
        print(f"  Entities extracted: {len(result['extracted'])}")

        return True

    except Exception as e:
        print(f"\nERROR: SAP generation failed: {e}")
        import traceback
        if verbose:
            traceback.print_exc()
        return False


def show_info():
    """Show system information"""
    print("\n" + "="*70)
    print("  ENHANCED KG PIPELINE - SAP GENERATION SYSTEM v2.0")
    print("="*70)

    # Show regulatory standards
    versions = get_standard_versions()

    print(f"\n  Pipeline: Enhanced Knowledge Graph + Claude")
    print(f"  Model: Claude Sonnet 4")

    print(f"\n  Regulatory Standards:")
    print(f"    MedDRA: {versions['MedDRA']}")
    print(f"    CTCAE: {versions['CTCAE']}")
    print(f"    WHO Drug Dictionary: {versions['WHO_Drug']}")

    # Check for API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    print(f"\n  API Key Status: {'✅ Set' if api_key else '❌ NOT SET'}")

    config = get_config()
    print(f"\n  Data Directory: {config.paths.all_pairs_dir}")

    # Count available pairs
    if config.paths.all_pairs_dir.exists():
        protocol_count = len(list(config.paths.all_pairs_dir.glob("*_protocol.txt")))
        print(f"  Available protocols: {protocol_count}")

    print("\n  Pipeline Components:")
    print("    [✓] Claude KG Extraction (with provenance)")
    print("    [✓] Power/Sample Size Calculator (scipy)")
    print("    [✓] Regulatory Knowledge Base (13 TEAE types)")
    print("    [✓] SELF-RAG Verification Loop")
    print("    [✓] Correction/Regeneration Loop")

    print("\n  Features:")
    print("    • Full provenance tracking for every fact")
    print("    • [INFERRED] markers for assumed content")
    print("    • Automatic phase/therapeutic area detection")
    print("    • 13 standard TEAE summary table types")
    print("    • ICH E9 R1 estimand framework support")

    print("\n" + "="*70)


def main():
    parser = argparse.ArgumentParser(
        description="Enterprise SAP Generation System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run tests
    python -m enterprise_sap_system.main test

    # Generate SAP from protocol
    python -m enterprise_sap_system.main generate protocol.txt -o output_sap.md

    # Show system info
    python -m enterprise_sap_system.main info
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Test command
    test_parser = subparsers.add_parser("test", help="Run system tests")

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate SAP from protocol")
    gen_parser.add_argument("protocol", help="Path to protocol file")
    gen_parser.add_argument("-o", "--output", help="Output path for generated SAP")
    gen_parser.add_argument("-q", "--quiet", action="store_true", help="Quiet mode")

    # Info command
    info_parser = subparsers.add_parser("info", help="Show system information")

    args = parser.parse_args()

    if args.command == "test":
        success = run_all_tests()
        sys.exit(0 if success else 1)

    elif args.command == "generate":
        success = generate_sap_cli(
            protocol_path=args.protocol,
            output_path=args.output,
            verbose=not args.quiet
        )
        sys.exit(0 if success else 1)

    elif args.command == "info":
        show_info()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
