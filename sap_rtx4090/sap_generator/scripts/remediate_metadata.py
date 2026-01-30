#!/usr/bin/env python3
"""
Production-Grade Metadata Remediation Script
=============================================

CRITICAL: This script fixes the metadata problem in your ChromaDB collections.

Problem: 90% of chunks have null metadata, making it impossible to distinguish
         regulatory rules from SAP examples.

Solution: Re-analyze all chunks and add proper source_type metadata:
- "regulatory_authority" for ICH/FDA/EMA documents
- "sap_example" for real clinical trial SAPs
- "standard" for CTCAE, RECIST, etc.

Run: python scripts/remediate_metadata.py
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import Counter
from dataclasses import dataclass

try:
    import chromadb
    from chromadb.config import Settings
except ImportError:
    print("ERROR: chromadb not installed. Run: pip install chromadb")
    exit(1)

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("ERROR: sentence-transformers not installed. Run: pip install sentence-transformers")
    exit(1)


@dataclass
class SourceClassification:
    """Classification result for a document chunk."""
    source_type: str  # regulatory_authority, sap_example, standard, unknown
    document_name: str
    authority: str  # ICH, FDA, EMA, etc.
    binding: str  # required, recommended, guidance, example
    confidence: float
    indicators: List[str]


class MetadataRemediator:
    """
    Analyzes and fixes metadata in ChromaDB collections.

    Key classifications:
    - regulatory_authority: ICH E9, FDA Guidances, EMA Guidelines
    - sap_example: Real SAPs from clinical trials
    - standard: CTCAE, RECIST, CONSORT, CDISC
    """

    # Regulatory authority indicators
    REGULATORY_PATTERNS = {
        'ich_e9': {
            'patterns': [
                r'ICH\s*E9', r'E9\s*\(R1\)', r'Statistical Principles',
                r'ICH Harmonised', r'ICH Guidelines?'
            ],
            'authority': 'ICH',
            'document': 'ICH E9',
            'binding': 'required'
        },
        'ich_e9r1': {
            'patterns': [
                r'E9\s*\(R1\)', r'Estimand', r'intercurrent event',
                r'estimand framework'
            ],
            'authority': 'ICH',
            'document': 'ICH E9(R1)',
            'binding': 'required'
        },
        'ich_e10': {
            'patterns': [
                r'ICH\s*E10', r'Choice of Control', r'control group selection'
            ],
            'authority': 'ICH',
            'document': 'ICH E10',
            'binding': 'required'
        },
        'ich_e17': {
            'patterns': [
                r'ICH\s*E17', r'Multi-Regional', r'MRCT', r'regional consistency'
            ],
            'authority': 'ICH',
            'document': 'ICH E17',
            'binding': 'required'
        },
        'fda_guidance': {
            'patterns': [
                r'FDA\s+[Gg]uidance', r'Food and Drug Administration',
                r'CDER', r'CBER', r'FDA recommends', r'FDA expects',
                r'Guidance for Industry'
            ],
            'authority': 'FDA',
            'document': 'FDA Guidance',
            'binding': 'guidance'
        },
        'fda_review': {
            'patterns': [
                r'STATISTICAL REVIEW', r'BLA\d+', r'NDA\d+',
                r'statistical reviewer', r'OFFICE OF BIOSTATISTICS'
            ],
            'authority': 'FDA',
            'document': 'FDA Statistical Review',
            'binding': 'example'
        },
        'ema_guideline': {
            'patterns': [
                r'EMA', r'European Medicines Agency', r'CHMP',
                r'Committee for Human Medicinal Products'
            ],
            'authority': 'EMA',
            'document': 'EMA Guideline',
            'binding': 'guidance'
        }
    }

    # Standard document indicators
    STANDARD_PATTERNS = {
        'ctcae': {
            'patterns': [
                r'CTCAE', r'Common Terminology Criteria',
                r'Adverse Event.*[Gg]rade', r'Grade\s*[1-5]'
            ],
            'authority': 'NCI',
            'document': 'CTCAE v5.0',
            'binding': 'standard'
        },
        'recist': {
            'patterns': [
                r'RECIST', r'Response Evaluation Criteria',
                r'target lesion', r'measurable disease'
            ],
            'authority': 'EORTC',
            'document': 'RECIST 1.1',
            'binding': 'standard'
        },
        'consort': {
            'patterns': [
                r'CONSORT', r'Consolidated Standards',
                r'flow diagram', r'reporting guideline'
            ],
            'authority': 'CONSORT',
            'document': 'CONSORT',
            'binding': 'standard'
        },
        'cdisc': {
            'patterns': [
                r'CDISC', r'SDTM', r'ADaM', r'Clinical Data Interchange'
            ],
            'authority': 'CDISC',
            'document': 'CDISC Standards',
            'binding': 'standard'
        }
    }

    # SAP example indicators
    SAP_PATTERNS = {
        'nct_trial': {
            'patterns': [
                r'NCT\d{8}', r'Study\s+NCT', r'Protocol\s+NCT',
                r'ClinicalTrials\.gov'
            ]
        },
        'sap_document': {
            'patterns': [
                r'Statistical Analysis Plan', r'SAP\s+Version',
                r'Primary Efficacy Analysis', r'Analysis Sets',
                r'Table\s+\d+', r'Listing\s+\d+', r'Figure\s+\d+'
            ]
        },
        'trial_name': {
            'patterns': [
                r'KEYNOTE-\d+', r'CheckMate\s*-?\d+', r'IMpower\d+',
                r'HIMALAYA', r'RATIONALE', r'DESTINY', r'TOPAZ',
                r'ORIENT', r'ATTRACTION', r'AURA'
            ]
        }
    }

    def __init__(self, chroma_path: Path):
        """Initialize with ChromaDB path."""
        self.chroma_path = Path(chroma_path)
        self.client = chromadb.PersistentClient(
            path=str(self.chroma_path),
            settings=Settings(anonymized_telemetry=False)
        )
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')

    def classify_chunk(self, content: str, existing_metadata: Dict) -> SourceClassification:
        """
        Classify a chunk's source type based on content analysis.

        Returns SourceClassification with:
        - source_type: regulatory_authority, sap_example, standard, unknown
        - document_name: specific document identified
        - authority: ICH, FDA, EMA, NCI, etc.
        - binding: required, recommended, guidance, example
        - confidence: 0.0-1.0
        - indicators: list of matched patterns
        """
        content_lower = content.lower()
        content_preview = content[:2000]  # Analyze first 2000 chars

        indicators = []
        matches = {'regulatory': [], 'standard': [], 'sap': []}

        # Check regulatory patterns
        for doc_type, info in self.REGULATORY_PATTERNS.items():
            for pattern in info['patterns']:
                if re.search(pattern, content_preview, re.IGNORECASE):
                    matches['regulatory'].append((doc_type, info))
                    indicators.append(f"regulatory:{pattern}")
                    break

        # Check standard patterns
        for doc_type, info in self.STANDARD_PATTERNS.items():
            for pattern in info['patterns']:
                if re.search(pattern, content_preview, re.IGNORECASE):
                    matches['standard'].append((doc_type, info))
                    indicators.append(f"standard:{pattern}")
                    break

        # Check SAP patterns
        for doc_type, info in self.SAP_PATTERNS.items():
            for pattern in info['patterns']:
                if re.search(pattern, content_preview, re.IGNORECASE):
                    matches['sap'].append(doc_type)
                    indicators.append(f"sap:{pattern}")
                    break

        # Extract NCT ID if present
        nct_match = re.search(r'(NCT\d{8})', content)
        nct_id = nct_match.group(1) if nct_match else None

        # Extract trial name if present
        trial_name = None
        for pattern in [r'KEYNOTE-\d+', r'CheckMate\s*-?\d+', r'IMpower\d+',
                       r'HIMALAYA', r'RATIONALE-\d+', r'DESTINY', r'TOPAZ',
                       r'ORIENT-\d+', r'ATTRACTION-\d+']:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                trial_name = match.group(0)
                break

        # Decision logic: Priority is regulatory > standard > sap
        if matches['regulatory']:
            # Regulatory authority document
            doc_type, info = matches['regulatory'][0]
            return SourceClassification(
                source_type='regulatory_authority',
                document_name=info['document'],
                authority=info['authority'],
                binding=info['binding'],
                confidence=0.9 if len(matches['regulatory']) > 1 else 0.8,
                indicators=indicators
            )

        elif matches['standard']:
            # Standard document (CTCAE, RECIST, etc.)
            doc_type, info = matches['standard'][0]
            return SourceClassification(
                source_type='standard',
                document_name=info['document'],
                authority=info['authority'],
                binding=info['binding'],
                confidence=0.85,
                indicators=indicators
            )

        elif matches['sap'] or nct_id or trial_name:
            # SAP example from real trial
            doc_name = trial_name or nct_id or 'Unknown Trial SAP'
            return SourceClassification(
                source_type='sap_example',
                document_name=doc_name,
                authority='trial_data',
                binding='example',
                confidence=0.9 if nct_id else 0.7,
                indicators=indicators
            )

        else:
            # Unknown - check existing metadata for clues
            if existing_metadata:
                source = existing_metadata.get('source', '')
                if 'NCT' in str(source):
                    return SourceClassification(
                        source_type='sap_example',
                        document_name=source,
                        authority='trial_data',
                        binding='example',
                        confidence=0.6,
                        indicators=['from_existing_metadata']
                    )

            return SourceClassification(
                source_type='unknown',
                document_name='',
                authority='',
                binding='',
                confidence=0.0,
                indicators=indicators
            )

    def analyze_collection(self, collection_name: str) -> Dict[str, Any]:
        """Analyze a single collection and return classification stats."""
        try:
            collection = self.client.get_collection(collection_name)
        except Exception as e:
            print(f"  Error getting collection {collection_name}: {e}")
            return {}

        count = collection.count()
        if count == 0:
            return {'name': collection_name, 'count': 0, 'classifications': {}}

        # Get all documents
        results = collection.get(include=['documents', 'metadatas'])

        classifications = Counter()
        samples = {'regulatory_authority': [], 'sap_example': [], 'standard': [], 'unknown': []}

        for i, (doc, meta) in enumerate(zip(results['documents'], results['metadatas'])):
            classification = self.classify_chunk(doc, meta or {})
            classifications[classification.source_type] += 1

            # Store first 3 samples of each type
            if len(samples[classification.source_type]) < 3:
                samples[classification.source_type].append({
                    'preview': doc[:200],
                    'classification': classification,
                    'existing_metadata': meta
                })

        return {
            'name': collection_name,
            'count': count,
            'classifications': dict(classifications),
            'samples': samples
        }

    def analyze_all_collections(self) -> List[Dict]:
        """Analyze all collections in the database."""
        collections = self.client.list_collections()
        results = []

        print(f"\nAnalyzing {len(collections)} collections...\n")

        for coll in collections:
            print(f"  Analyzing: {coll.name}...")
            analysis = self.analyze_collection(coll.name)
            if analysis:
                results.append(analysis)

        return results

    def remediate_collection(self, collection_name: str, dry_run: bool = True) -> Dict[str, int]:
        """
        Add proper metadata to all chunks in a collection.

        Args:
            collection_name: Name of collection to remediate
            dry_run: If True, only analyze without making changes

        Returns:
            Dict with counts of each source_type
        """
        try:
            collection = self.client.get_collection(collection_name)
        except Exception as e:
            print(f"  Error: {e}")
            return {}

        count = collection.count()
        if count == 0:
            return {}

        # Get all documents
        results = collection.get(include=['documents', 'metadatas', 'embeddings'])

        updated_ids = []
        updated_metadatas = []
        stats = Counter()

        for i, (doc_id, doc, meta, embedding) in enumerate(zip(
            results['ids'],
            results['documents'],
            results['metadatas'],
            results.get('embeddings', [None] * count)
        )):
            # Classify the chunk
            classification = self.classify_chunk(doc, meta or {})
            stats[classification.source_type] += 1

            # Build new metadata
            new_meta = dict(meta) if meta else {}

            # Add source classification metadata
            new_meta['source_type'] = classification.source_type
            new_meta['document_name'] = classification.document_name
            new_meta['authority'] = classification.authority
            new_meta['binding'] = classification.binding
            new_meta['classification_confidence'] = classification.confidence

            # Preserve existing useful fields
            if 'nct_id' not in new_meta:
                nct_match = re.search(r'(NCT\d{8})', doc)
                if nct_match:
                    new_meta['nct_id'] = nct_match.group(1)

            updated_ids.append(doc_id)
            updated_metadatas.append(new_meta)

            if (i + 1) % 500 == 0:
                print(f"    Processed {i + 1}/{count} chunks...")

        if not dry_run and updated_ids:
            # Update in batches of 1000
            batch_size = 1000
            for i in range(0, len(updated_ids), batch_size):
                batch_ids = updated_ids[i:i+batch_size]
                batch_metas = updated_metadatas[i:i+batch_size]

                try:
                    collection.update(
                        ids=batch_ids,
                        metadatas=batch_metas
                    )
                    print(f"    Updated batch {i//batch_size + 1}/{(len(updated_ids)-1)//batch_size + 1}")
                except Exception as e:
                    print(f"    Error updating batch: {e}")

        return dict(stats)

    def remediate_all(self, dry_run: bool = True):
        """Remediate all collections."""
        collections = self.client.list_collections()

        print(f"\n{'='*70}")
        print(f"METADATA REMEDIATION {'(DRY RUN)' if dry_run else '(LIVE)'}")
        print(f"{'='*70}")
        print(f"\nFound {len(collections)} collections to process\n")

        total_stats = Counter()

        for coll in collections:
            print(f"\n{'─'*50}")
            print(f"Collection: {coll.name}")
            print(f"{'─'*50}")

            stats = self.remediate_collection(coll.name, dry_run=dry_run)

            for source_type, count in stats.items():
                total_stats[source_type] += count
                print(f"  {source_type}: {count}")

        print(f"\n{'='*70}")
        print("TOTAL SUMMARY")
        print(f"{'='*70}")

        for source_type, count in sorted(total_stats.items()):
            pct = count / sum(total_stats.values()) * 100 if total_stats else 0
            print(f"  {source_type}: {count} ({pct:.1f}%)")

        print(f"\nTotal chunks: {sum(total_stats.values())}")

        if dry_run:
            print(f"\n⚠️  This was a DRY RUN - no changes were made.")
            print(f"   To apply changes, run with: --apply")
        else:
            print(f"\n✅ Metadata remediation complete!")

        return dict(total_stats)

    def generate_report(self, output_path: Path = None):
        """Generate detailed analysis report."""
        results = self.analyze_all_collections()

        report = []
        report.append("=" * 80)
        report.append("CHROMADB METADATA ANALYSIS REPORT")
        report.append("=" * 80)
        report.append("")

        total_regulatory = 0
        total_sap = 0
        total_standard = 0
        total_unknown = 0
        total_chunks = 0

        for analysis in results:
            report.append(f"\n{'─'*60}")
            report.append(f"Collection: {analysis['name']}")
            report.append(f"Total Chunks: {analysis['count']}")
            report.append(f"{'─'*60}")

            for source_type, count in analysis.get('classifications', {}).items():
                pct = count / analysis['count'] * 100 if analysis['count'] else 0
                report.append(f"  {source_type}: {count} ({pct:.1f}%)")

                if source_type == 'regulatory_authority':
                    total_regulatory += count
                elif source_type == 'sap_example':
                    total_sap += count
                elif source_type == 'standard':
                    total_standard += count
                else:
                    total_unknown += count

            total_chunks += analysis['count']

            # Show samples
            for source_type, samples in analysis.get('samples', {}).items():
                if samples:
                    report.append(f"\n  Sample {source_type}:")
                    for s in samples[:2]:
                        report.append(f"    - {s['preview'][:100]}...")
                        report.append(f"      Classification: {s['classification'].document_name}")

        report.append(f"\n{'='*80}")
        report.append("OVERALL SUMMARY")
        report.append(f"{'='*80}")
        report.append(f"Total Chunks: {total_chunks}")
        report.append(f"  Regulatory Authority: {total_regulatory} ({total_regulatory/total_chunks*100:.1f}%)")
        report.append(f"  SAP Examples: {total_sap} ({total_sap/total_chunks*100:.1f}%)")
        report.append(f"  Standards: {total_standard} ({total_standard/total_chunks*100:.1f}%)")
        report.append(f"  Unknown: {total_unknown} ({total_unknown/total_chunks*100:.1f}%)")

        report.append(f"\n{'='*80}")
        report.append("PRODUCTION READINESS ASSESSMENT")
        report.append(f"{'='*80}")

        if total_regulatory > 0:
            report.append(f"✅ Have regulatory authority chunks: {total_regulatory}")
        else:
            report.append(f"❌ MISSING regulatory authority chunks")

        if total_sap > 0:
            report.append(f"✅ Have SAP example chunks: {total_sap}")
        else:
            report.append(f"❌ MISSING SAP example chunks")

        if total_unknown > total_chunks * 0.1:
            report.append(f"⚠️  HIGH unknown chunks: {total_unknown} ({total_unknown/total_chunks*100:.1f}%)")

        report_text = '\n'.join(report)

        if output_path:
            output_path = Path(output_path)
            output_path.write_text(report_text)
            print(f"\nReport saved to: {output_path}")

        return report_text


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Remediate ChromaDB metadata for production-grade knowledge graph"
    )
    parser.add_argument(
        '--chroma-path',
        type=str,
        default='/mnt/c/Users/vijay/OneDrive/Documents/Github/clinicaltrial/sap_rtx4090/sap_generator/data/chroma_db',
        help='Path to ChromaDB directory'
    )
    parser.add_argument(
        '--analyze',
        action='store_true',
        help='Analyze collections without making changes'
    )
    parser.add_argument(
        '--report',
        type=str,
        help='Generate detailed report to file'
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Apply metadata remediation (default is dry run)'
    )

    args = parser.parse_args()

    chroma_path = Path(args.chroma_path)
    if not chroma_path.exists():
        print(f"ERROR: ChromaDB path not found: {chroma_path}")
        exit(1)

    remediator = MetadataRemediator(chroma_path)

    if args.analyze or args.report:
        report = remediator.generate_report(
            output_path=Path(args.report) if args.report else None
        )
        print(report)
    else:
        # Run remediation
        dry_run = not args.apply
        remediator.remediate_all(dry_run=dry_run)


if __name__ == '__main__':
    main()
