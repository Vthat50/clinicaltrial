# save as: fix_metadata.py
import chromadb
from pathlib import Path
import re

class MetadataFixer:

    def __init__(self, db_path):
        self.client = chromadb.PersistentClient(path=db_path)

    def identify_document_type(self, doc_text):
        """Identify what type of document this is"""

        # Check first 1000 chars for classification
        header = doc_text[:1000].upper()

        # ICH Guidelines
        if "ICH HARMONISED" in header or "ICH E9" in header:
            if "E9(R1)" in header or "ESTIMAND" in header:
                return {
                    "source_type": "regulatory_authority",
                    "authority": "ICH",
                    "document": "ICH E9(R1) - Estimands and Sensitivity Analysis",
                    "binding": "required",
                    "tier": 1,
                    "citation_format": "ICH E9(R1)"
                }
            elif "E9" in header and "STATISTICAL PRINCIPLES" in header:
                return {
                    "source_type": "regulatory_authority",
                    "authority": "ICH",
                    "document": "ICH E9 - Statistical Principles for Clinical Trials",
                    "binding": "required",
                    "tier": 1,
                    "citation_format": "ICH E9"
                }
            elif "E10" in header:
                return {
                    "source_type": "regulatory_authority",
                    "authority": "ICH",
                    "document": "ICH E10 - Choice of Control Group",
                    "binding": "required",
                    "tier": 1,
                    "citation_format": "ICH E10"
                }
            elif "E17" in header:
                return {
                    "source_type": "regulatory_authority",
                    "authority": "ICH",
                    "document": "ICH E17 - Multi-Regional Clinical Trials",
                    "binding": "required",
                    "tier": 1,
                    "citation_format": "ICH E17"
                }
            elif "E5" in header:
                return {
                    "source_type": "regulatory_authority",
                    "authority": "ICH",
                    "document": "ICH E5(R1) - Ethnic Factors",
                    "binding": "required",
                    "tier": 1,
                    "citation_format": "ICH E5(R1)"
                }

        # FDA Guidances - check various formats
        if ("GUIDANCE FOR INDUSTRY" in header or
            ("FDA" in header and "GUIDANCE" in header) or
            "GUIDANCE DOCUMENT" in header):
            if "OVERALL SURVIVAL" in header:
                return {
                    "source_type": "regulatory_authority",
                    "authority": "FDA",
                    "document": "FDA Guidance - Overall Survival in Oncology Trials",
                    "binding": "should_follow",
                    "tier": 1,
                    "citation_format": "FDA OS Guidance"
                }
            elif "CLINICAL TRIAL ENDPOINTS" in header:
                return {
                    "source_type": "regulatory_authority",
                    "authority": "FDA",
                    "document": "FDA Guidance - Clinical Trial Endpoints",
                    "binding": "should_follow",
                    "tier": 1,
                    "citation_format": "FDA Endpoints Guidance"
                }
            elif "MULTIPLE ENDPOINTS" in header:
                return {
                    "source_type": "regulatory_authority",
                    "authority": "FDA",
                    "document": "FDA Guidance - Multiple Endpoints",
                    "binding": "should_follow",
                    "tier": 1,
                    "citation_format": "FDA Multiple Endpoints Guidance"
                }
            else:
                # Generic FDA Guidance
                return {
                    "source_type": "regulatory_authority",
                    "authority": "FDA",
                    "document": "FDA Guidance (General)",
                    "binding": "should_follow",
                    "tier": 1,
                    "citation_format": "FDA Guidance"
                }

        # EMA Guidances
        if "EMA" in header or "CHMP" in header:
            if "ANTICANCER" in header:
                return {
                    "source_type": "regulatory_authority",
                    "authority": "EMA",
                    "document": "EMA Guideline - Clinical Evaluation of Anticancer Products",
                    "binding": "required_for_eu",
                    "tier": 1,
                    "citation_format": "EMA Anticancer Guideline"
                }

        # FDA Statistical Reviews
        if "STATISTICAL REVIEW" in header and "CENTER FOR DRUG EVALUATION" in header:
            # Extract BLA number
            bla_match = re.search(r'(\d{6})Orig', header)
            bla_num = bla_match.group(1) if bla_match else "Unknown"
            return {
                "source_type": "regulatory_reference",
                "authority": "FDA",
                "document": f"FDA Statistical Review - BLA {bla_num}",
                "binding": "reference_example",
                "tier": 2,
                "citation_format": f"FDA Review BLA {bla_num}"
            }

        # Research Papers
        if "NEW ENGLAND JOURNAL" in header or "NEJM" in header:
            if "MULTIPLICITY" in header:
                return {
                    "source_type": "peer_reviewed_research",
                    "authority": "Academic",
                    "document": "NEJM - Multiplicity Considerations (Dmitrienko & D'Agostino)",
                    "binding": "best_practice",
                    "tier": 3,
                    "citation_format": "Dmitrienko & D'Agostino, NEJM"
                }

        if "NON-PROPORTIONAL HAZARD" in header or "NON -PROPORTIONAL" in header:
            return {
                "source_type": "peer_reviewed_research",
                "authority": "Academic",
                "document": "Alternative Analysis Methods for NPH",
                "binding": "best_practice",
                "tier": 3,
                "citation_format": "Lin et al."
            }

        # SAP Examples (SHOULD NOT BE IN sap_methods!)
        # Detect SAPs by various patterns
        is_sap = (
            "STATISTICAL ANALYSIS PLAN" in header or
            "SAP VERSION" in header or
            header.startswith("STATISTICAL ANALYSIS PLAN") or
            "STUDY:" in header and "RANDOMIZED" in header or
            "STUDY:" in header and "DOUBLE-BLIND" in header or
            "STUDY:" in header and "PLACEBO" in header
        )

        if is_sap:
            nct_match = re.search(r'NCT\d+', doc_text[:5000])  # Check first 5000 chars
            nct_id = nct_match.group(0) if nct_match else "Unknown"
            return {
                "source_type": "sap_example",
                "authority": "None",
                "document": f"SAP Example - {nct_id}",
                "binding": "reference_only",
                "tier": 4,
                "citation_format": f"NCT {nct_id}" if nct_id != "Unknown" else "Unknown SAP",
                "WARNING": "This should be in SAP collections, not regulatory!"
            }

        # Unknown
        return {
            "source_type": "unknown",
            "authority": "Unknown",
            "document": "Unclassified Document",
            "binding": "unknown",
            "tier": 5,
            "citation_format": "Unknown"
        }

    def fix_sap_methods_collection(self):
        """Re-index sap_methods with proper metadata"""

        print("=" * 80)
        print("RE-INDEXING SAP_METHODS COLLECTION")
        print("=" * 80)

        # Get existing collection
        old_coll = self.client.get_collection("sap_methods")
        results = old_coll.get(include=['documents', 'metadatas'])

        # Create new collection with metadata
        try:
            self.client.delete_collection("sap_methods_backup")
        except:
            pass

        # Backup old collection
        backup_coll = self.client.create_collection("sap_methods_backup")

        # Analyze and categorize
        regulatory_docs = []
        sap_examples = []

        print(f"\nAnalyzing {len(results['documents'])} documents...\n")

        for i, (doc_id, doc, old_meta) in enumerate(zip(
            results['ids'],
            results['documents'],
            results['metadatas']
        )):
            # Identify document type
            new_meta = self.identify_document_type(doc)

            # Add original metadata if exists
            if old_meta:
                new_meta['original_metadata'] = str(old_meta)

            # Categorize
            if new_meta['source_type'] == 'sap_example':
                sap_examples.append({
                    'id': doc_id,
                    'document': doc,
                    'metadata': new_meta
                })
                print(f"[{i+1}] ⚠️  SAP Example found (should move): {new_meta['document']}")
            elif new_meta['tier'] <= 2:
                regulatory_docs.append({
                    'id': doc_id,
                    'document': doc,
                    'metadata': new_meta
                })
                print(f"[{i+1}] ✅ {new_meta['authority']}: {new_meta['document']}")
            else:
                regulatory_docs.append({
                    'id': doc_id,
                    'document': doc,
                    'metadata': new_meta
                })
                print(f"[{i+1}] 📄 Reference: {new_meta['document']}")

        # Create new properly organized collections
        print(f"\n{'=' * 80}")
        print(f"CREATING CLEAN COLLECTIONS")
        print(f"{'=' * 80}\n")

        # Delete old sap_methods
        self.client.delete_collection("sap_methods")

        # Create new sap_methods (regulatory only)
        new_regulatory = self.client.create_collection("sap_methods")

        if regulatory_docs:
            new_regulatory.add(
                ids=[d['id'] for d in regulatory_docs],
                documents=[d['document'] for d in regulatory_docs],
                metadatas=[d['metadata'] for d in regulatory_docs]
            )
            print(f"✅ Created sap_methods: {len(regulatory_docs)} regulatory documents")

        # Move SAP examples to proper collection
        if sap_examples:
            print(f"\n⚠️  Found {len(sap_examples)} SAP examples in sap_methods")
            print(f"   These should be in sap_statistical_methods collection")
            print(f"   Moving them now...")

            # Add to appropriate SAP collection
            try:
                sap_coll = self.client.get_collection("sap_statistical_methods")
                sap_coll.add(
                    ids=[d['id'] for d in sap_examples],
                    documents=[d['document'] for d in sap_examples],
                    metadatas=[d['metadata'] for d in sap_examples]
                )
                print(f"   ✅ Moved to sap_statistical_methods")
            except Exception as e:
                print(f"   ❌ Error moving: {e}")

        return {
            'regulatory_count': len(regulatory_docs),
            'sap_examples_moved': len(sap_examples)
        }

    def generate_summary_report(self):
        """Generate summary of what's in each collection"""

        print(f"\n{'=' * 80}")
        print("COLLECTION SUMMARY REPORT")
        print(f"{'=' * 80}\n")

        coll = self.client.get_collection("sap_methods")
        results = coll.get(include=['metadatas'])

        # Group by authority and tier
        by_authority = {}
        by_tier = {}

        for meta in results['metadatas']:
            if meta:
                auth = meta.get('authority', 'Unknown')
                tier = meta.get('tier', 5)

                by_authority[auth] = by_authority.get(auth, 0) + 1
                by_tier[tier] = by_tier.get(tier, 0) + 1

        print("BY REGULATORY AUTHORITY:")
        for auth, count in sorted(by_authority.items()):
            print(f"  {auth}: {count} documents")

        print("\nBY TIER:")
        tier_names = {
            1: "Tier 1 - Regulatory Authorities (ICH/FDA/EMA)",
            2: "Tier 2 - FDA Statistical Reviews",
            3: "Tier 3 - Peer-Reviewed Research",
            4: "Tier 4 - SAP Examples (shouldn't be here)",
            5: "Tier 5 - Unknown/Unclassified"
        }
        for tier, count in sorted(by_tier.items()):
            print(f"  {tier_names.get(tier, f'Tier {tier}')}: {count} documents")

        print(f"\n{'=' * 80}")
        print("PRODUCTION READINESS ASSESSMENT")
        print(f"{'=' * 80}\n")

        tier1_count = by_tier.get(1, 0)
        tier4_count = by_tier.get(4, 0)

        if tier1_count >= 8:
            print("✅ EXCELLENT: Strong regulatory foundation")
        elif tier1_count >= 5:
            print("⚠️  GOOD: Adequate regulatory coverage")
        else:
            print("❌ INSUFFICIENT: Need more regulatory documents")

        print(f"   Tier 1 Documents: {tier1_count}")

        if tier4_count > 0:
            print(f"\n⚠️  WARNING: {tier4_count} SAP examples in regulatory collection")
            print("   Recommendation: Move to appropriate SAP collections")


# USAGE
if __name__ == "__main__":
    DB_PATH = "/mnt/c/Users/vijay/OneDrive/Documents/Github/clinicaltrial/sap_rtx4090/sap_generator/data/chroma_db"

    fixer = MetadataFixer(DB_PATH)

    # Fix the collection
    results = fixer.fix_sap_methods_collection()

    # Generate report
    fixer.generate_summary_report()

    print(f"\n{'=' * 80}")
    print("NEXT STEPS")
    print(f"{'=' * 80}\n")

    print("1. ✅ Metadata structure created")
    print("2. 📋 Review summary report above")
    print("3. 🔍 Test queries by authority/tier")
    print("4. 📥 Download missing critical documents:")
    print("   - CTCAE v5.0 (NCI)")
    print("   - RECIST 1.1")
    print("   - iRECIST")
    print("   - CONSORT 2025")
    print("5. 🔄 Re-index SAP collections with proper metadata")
    print("6. 🚀 Build decision engine using tier-based priority")
