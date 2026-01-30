#!/usr/bin/env python3
"""
Two-Pass SAP Generator - Production Entry Point
================================================

Generates SAPs using the two-pass extraction system:
- Pass 1 (Discovery): Finds ALL statistical elements in the protocol
- Pass 2 (Extraction): Extracts detailed data for each element

Usage:
    python -m enterprise_sap_system.generate_two_pass /path/to/protocol.pdf
    python -m enterprise_sap_system.generate_two_pass /path/to/protocol.pdf -o output.md

Required environment variables:
    ANTHROPIC_API_KEY - For Claude LLM
    LLAMAPARSE_API_KEY - For PDF parsing
"""

import os
import sys
import argparse
import time
import json
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_api_keys():
    """Check that required API keys are set."""
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY')
    llamaparse_key = os.environ.get('LLAMAPARSE_API_KEY')

    if not anthropic_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        print("  export ANTHROPIC_API_KEY='sk-ant-...'")
        return False

    if not llamaparse_key:
        print("WARNING: LLAMAPARSE_API_KEY not set - PDF parsing may fail")
        print("  export LLAMAPARSE_API_KEY='llx-...'")

    print(f"[✓] ANTHROPIC_API_KEY set ({anthropic_key[:20]}...)")
    if llamaparse_key:
        print(f"[✓] LLAMAPARSE_API_KEY set ({llamaparse_key[:10]}...)")

    return True


def generate_sap(protocol_path: str, output_path: str = None, verbose: bool = True):
    """Generate SAP from protocol using two-pass extraction."""
    protocol_path = Path(protocol_path)

    if not protocol_path.exists():
        print(f"ERROR: Protocol file not found: {protocol_path}")
        return None

    # Check file size
    file_size = protocol_path.stat().st_size
    print(f"\n{'='*70}")
    print(f"TWO-PASS SAP GENERATOR")
    print(f"{'='*70}")
    print(f"Input: {protocol_path}")
    print(f"Size: {file_size:,} bytes")

    # Import here to avoid import errors if keys not set
    from enterprise_sap_system.core.sap_rag import SAPRAGIndex, RAGSAPGenerator

    # Create RAG index and generator with two-pass enabled
    print("\n[Init] Creating RAG generator with two-pass extraction...")
    rag_index = SAPRAGIndex()
    generator = RAGSAPGenerator(rag_index, use_two_pass=True)

    if not generator.two_pass_extractor:
        print("ERROR: Two-pass extractor failed to load")
        return None

    # Generate SAP
    print("\n[Generate] Starting two-pass SAP generation...")
    start_time = time.time()

    try:
        if str(protocol_path).endswith('.pdf'):
            sap_content = generator.generate_full_sap_two_pass(str(protocol_path))
        else:
            # If it's a text file, read content and pass the file path in protocol_id
            protocol_text = protocol_path.read_text(encoding='utf-8', errors='ignore')
            print(f"  Protocol text: {len(protocol_text):,} characters")
            sap_content = generator.generate_full_sap_two_pass(protocol_text)

        elapsed = time.time() - start_time

        print(f"\n{'='*70}")
        print(f"GENERATION COMPLETE")
        print(f"{'='*70}")
        print(f"Time: {elapsed:.1f} seconds")
        print(f"SAP Length: {len(sap_content):,} characters")

        # Determine output path
        if not output_path:
            output_dir = Path("/mnt/c/Users/vijay/Desktop/sap_data/section_output")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{protocol_path.stem}_SAP_two_pass.md"
        else:
            output_path = Path(output_path)

        # Save SAP
        output_path.write_text(sap_content, encoding='utf-8')
        print(f"Output: {output_path}")

        # Also save extraction JSON
        json_path = output_path.with_suffix('.json')
        if hasattr(generator, '_last_extraction_result'):
            json_path.write_text(
                json.dumps(generator._last_extraction_result, indent=2),
                encoding='utf-8'
            )
            print(f"Extraction data: {json_path}")

        return sap_content

    except Exception as e:
        print(f"\nERROR: Generation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Generate SAP from protocol using two-pass extraction",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Generate from PDF
    python -m enterprise_sap_system.generate_two_pass protocol.pdf

    # Generate with custom output path
    python -m enterprise_sap_system.generate_two_pass protocol.pdf -o my_sap.md

    # Test with KATHERINE protocol
    python -m enterprise_sap_system.generate_two_pass \\
        /mnt/c/Users/vijay/Desktop/sap_data/ct_downloads/all_protocols/NCT01772472_Protocol.pdf
        """
    )

    parser.add_argument("protocol", help="Path to protocol PDF or text file")
    parser.add_argument("-o", "--output", help="Output path for generated SAP")
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet mode")

    args = parser.parse_args()

    # Check API keys
    if not check_api_keys():
        sys.exit(1)

    # Generate SAP
    result = generate_sap(
        protocol_path=args.protocol,
        output_path=args.output,
        verbose=not args.quiet
    )

    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
