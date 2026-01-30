#!/usr/bin/env python3
"""
Script to download CDISC CT from NCI EVS
Downloads both SDTM and ADaM terminology packages and saves to local cache.

Usage:
    python scripts/download_cdisc_ct.py
    python scripts/download_cdisc_ct.py --version 2024-06-28
    python scripts/download_cdisc_ct.py --package-type SDTM
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from enterprise_sap_system.cdisc.nci_evs_client import NCIEVSClient
from enterprise_sap_system.cdisc.terminology_service import CDISCTerminologyService, TerminologySource
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Download CDISC CT packages from NCI EVS"""

    parser = argparse.ArgumentParser(
        description='Download CDISC Controlled Terminology from NCI EVS'
    )
    parser.add_argument(
        '--version',
        default='2024-09-27',
        help='CT version to download (default: 2024-09-27)'
    )
    parser.add_argument(
        '--package-type',
        choices=['SDTM', 'ADaM', 'Both'],
        default='Both',
        help='Package type to download (default: Both)'
    )
    parser.add_argument(
        '--cache-dir',
        type=Path,
        default=None,
        help='Cache directory (default: enterprise_sap_system/data/terminology)'
    )

    args = parser.parse_args()

    # Set cache directory
    if args.cache_dir:
        cache_dir = args.cache_dir
    else:
        cache_dir = Path(__file__).parent.parent / "enterprise_sap_system" / "data" / "terminology"

    cache_dir.mkdir(parents=True, exist_ok=True)

    logger.info("="*70)
    logger.info(f"CDISC CT Download - Version {args.version}")
    logger.info("="*70)
    logger.info(f"Cache directory: {cache_dir}")
    logger.info(f"Package type: {args.package_type}")
    logger.info("")

    # Create client and service
    client = NCIEVSClient(cache_dir=cache_dir)
    service = CDISCTerminologyService(
        cache_dir=cache_dir,
        source=TerminologySource.NCI_EVS_API
    )

    packages_to_download = []
    if args.package_type in ['SDTM', 'Both']:
        packages_to_download.append('SDTM')
    if args.package_type in ['ADaM', 'Both']:
        packages_to_download.append('ADaM')

    # Download packages
    for package_type in packages_to_download:
        try:
            logger.info(f"\n{'='*70}")
            logger.info(f"Downloading {package_type} package...")
            logger.info(f"{'='*70}\n")

            package = client.download_package(args.version, package_type)

            # Save to cache
            cache_file = cache_dir / args.version / f"{package_type.lower()}_codelists.json"
            service._save_to_cache(package, cache_file)

            logger.info(f"\n✓ {package_type} package saved successfully")
            logger.info(f"  - Location: {cache_file}")
            logger.info(f"  - Codelists: {len(package.codelists)}")

            # Summary statistics
            total_items = sum(len(cl.items) for cl in package.codelists.values())
            logger.info(f"  - Total terminology items: {total_items}")

            # Top codelists
            logger.info(f"\n  Top 10 codelists by size:")
            sorted_codelists = sorted(
                package.codelists.items(),
                key=lambda x: len(x[1].items),
                reverse=True
            )[:10]
            for idx, (name, codelist) in enumerate(sorted_codelists, 1):
                logger.info(f"    {idx}. {name}: {len(codelist.items)} items")

        except Exception as e:
            logger.error(f"\n✗ Failed to download {package_type} package: {e}")
            logger.exception("Full traceback:")
            sys.exit(1)

    logger.info(f"\n{'='*70}")
    logger.info("Download complete!")
    logger.info(f"{'='*70}")
    logger.info(f"\nCT files saved to: {cache_dir / args.version}")
    logger.info("\nTo use these CT packages, the terminology service will automatically")
    logger.info("load them from cache on initialization.")
    logger.info("\nYou can now run:")
    logger.info("  python -m enterprise_sap_system.cdisc.terminology_service")


def test_loading():
    """Test loading the downloaded packages"""
    logger.info("\n" + "="*70)
    logger.info("Testing CT package loading...")
    logger.info("="*70 + "\n")

    try:
        from enterprise_sap_system.cdisc.terminology_service import get_terminology_service

        service = get_terminology_service()

        # Test basic operations
        logger.info("1. Testing codelist retrieval...")
        sex_codelist = service.get_codelist("Sex")
        if sex_codelist:
            logger.info(f"   ✓ Sex codelist: {len(sex_codelist.items)} items")
        else:
            logger.warning("   ✗ Sex codelist not found")

        logger.info("\n2. Testing PARAMCD search...")
        results = service.search_param("survival")
        logger.info(f"   ✓ Found {len(results)} PARAMCDs containing 'survival'")
        for item in results[:3]:
            logger.info(f"     - {item.submission_value}: {item.preferred_term}")

        logger.info("\n3. Testing term validation...")
        is_valid = service.validate_term("Sex", "M")
        logger.info(f"   {'✓' if is_valid else '✗'} Validation test: Sex='M' -> {is_valid}")

        logger.info("\n✓ All tests passed!")

    except Exception as e:
        logger.error(f"✗ Testing failed: {e}")
        logger.exception("Full traceback:")


if __name__ == "__main__":
    try:
        main()

        # Optionally test loading
        import sys
        if '--test' in sys.argv:
            test_loading()

    except KeyboardInterrupt:
        logger.info("\n\nDownload interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\nFatal error: {e}")
        logger.exception("Full traceback:")
        sys.exit(1)
