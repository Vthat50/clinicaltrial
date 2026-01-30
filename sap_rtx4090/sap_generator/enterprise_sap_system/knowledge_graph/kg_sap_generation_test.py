"""
Knowledge Graph SAP Generation Test
====================================

Full pipeline test:
1. Ingest protocol → Extract to KG
2. Query KG for similar trials
3. Generate SAP with KG context
4. Show provenance/tracing

Usage:
    python kg_sap_generation_test.py [protocol_file]
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add parent paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from kg_pipeline_test import (
    FactualKnowledgeGraphV2,
    DualStoragePipeline,
    FlexibleNode,
    FlexibleEdge
)


# =============================================================================
# LOAD EXISTING CLAUDE-EXTRACTED KG
# =============================================================================

def load_existing_kg() -> FactualKnowledgeGraphV2:
    """Load the Claude-extracted KG with 2840 nodes."""
    kg_path = Path(__file__).parent / "output" / "factual_kg_claude.json"

    kg = FactualKnowledgeGraphV2()

    if kg_path.exists():
        with open(kg_path) as f:
            data = json.load(f)

        # Load nodes
        for n in data.get("nodes", []):
            node = FlexibleNode(
                id=n["id"],
                node_type=n["type"],
                properties=n.get("attributes", {}),
            )
            kg.nodes[node.id] = node

        # Load edges
        for e in data.get("edges", []):
            edge = FlexibleEdge(
                source_id=e["source"],
                target_id=e["target"],
                edge_type=e["type"],
                is_factual=True
            )
            kg.edges.append(edge)

        print(f"✅ Loaded existing KG: {len(kg.nodes)} nodes, {len(kg.edges)} edges")
    else:
        print("⚠️ No existing KG found, starting fresh")

    return kg


# =============================================================================
# KG-ENHANCED SAP GENERATOR
# =============================================================================

class KGEnhancedSAPGenerator:
    """
    SAP Generator that uses Knowledge Graph for:
    1. Similar trial lookup (examples, not recommendations)
    2. Provenance tracking
    3. Context enrichment
    """

    def __init__(self, kg: FactualKnowledgeGraphV2):
        self.kg = kg
        self.pipeline = DualStoragePipeline(kg)
        self.extraction_result = None
        self.kg_context = None

    def ingest_protocol(self, protocol_path: str) -> Dict:
        """
        Step 1: Ingest protocol into KG.

        Returns extracted facts with provenance.
        """
        print("\n" + "="*70)
        print("STEP 1: INGEST PROTOCOL INTO KNOWLEDGE GRAPH")
        print("="*70)

        result = self.pipeline.process_document(protocol_path, user_id="test_user")
        self.extraction_result = result

        return result

    def query_kg_for_context(self) -> Dict:
        """
        Step 2: Query KG for similar trials and context.

        IMPORTANT: Returns individual facts, NOT aggregated recommendations.
        """
        print("\n" + "="*70)
        print("STEP 2: QUERY KNOWLEDGE GRAPH FOR CONTEXT")
        print("="*70)

        if not self.extraction_result:
            return {"error": "No protocol ingested yet"}

        # Get extracted endpoints/methods from protocol
        sap_data = self.pipeline.get_sap_generation_data(self.extraction_result["doc_id"])

        extracted_endpoints = [d for d in sap_data if d["type"] == "endpoint"]
        extracted_methods = [d for d in sap_data if d["type"] == "method"]

        print(f"\nExtracted from protocol:")
        for ep in extracted_endpoints:
            print(f"  • Endpoint: {ep['name']} (confidence: {ep['confidence']})")
        for m in extracted_methods:
            print(f"  • Method: {m['name']} (confidence: {m['confidence']})")

        # Query KG for similar trials
        context = {
            "similar_trials": [],
            "method_examples": [],
            "endpoint_examples": []
        }

        # Find trials with similar endpoints
        for ep in extracted_endpoints:
            ep_name_lower = ep["name"].lower()

            for node_id, node in self.kg.nodes.items():
                if node.node_type == "endpoint":
                    node_name = node.properties.get("name", "").lower()
                    if ep_name_lower in node_name or node_name in ep_name_lower:
                        # Find which trial has this endpoint
                        for edge in self.kg.edges:
                            if edge.target_id == node_id and edge.edge_type == "has_endpoint":
                                trial = self.kg.nodes.get(edge.source_id)
                                if trial:
                                    # Get methods used for this endpoint
                                    methods_used = self._get_methods_for_endpoint(node_id)

                                    context["endpoint_examples"].append({
                                        "trial_id": trial.id,
                                        "endpoint": node.properties.get("name"),
                                        "endpoint_type": node.properties.get("endpoint_type"),
                                        "methods_used": methods_used,
                                        # PROBLEM 7: Individual fact, not aggregation
                                        "fact": f"{trial.id} analyzed {node.properties.get('name')} with {', '.join(methods_used) if methods_used else 'unspecified method'}"
                                    })

        # Deduplicate and limit
        seen_trials = set()
        unique_examples = []
        for ex in context["endpoint_examples"]:
            if ex["trial_id"] not in seen_trials:
                seen_trials.add(ex["trial_id"])
                unique_examples.append(ex)
                if len(unique_examples) >= 5:
                    break
        context["endpoint_examples"] = unique_examples

        print(f"\nKG Context (individual facts, NOT aggregated):")
        for ex in context["endpoint_examples"]:
            print(f"  ✅ {ex['fact']}")

        print(f"\n⚠️ Note: These are examples from similar trials, NOT recommendations")

        self.kg_context = context
        return context

    def _get_methods_for_endpoint(self, endpoint_id: str) -> List[str]:
        """Get methods linked to an endpoint."""
        methods = []
        for edge in self.kg.edges:
            if edge.source_id == endpoint_id and edge.edge_type == "analyzed_with":
                method = self.kg.nodes.get(edge.target_id)
                if method:
                    methods.append(method.properties.get("name", method.id))
        return methods

    def generate_sap(self, use_kg_context: bool = True) -> str:
        """
        Step 3: Generate SAP using extracted data + KG context.

        In production, this would call Claude. For testing, we generate a template.
        """
        print("\n" + "="*70)
        print("STEP 3: GENERATE SAP WITH KG CONTEXT")
        print("="*70)

        if not self.extraction_result:
            return "Error: No protocol ingested"

        sap_data = self.pipeline.get_sap_generation_data(self.extraction_result["doc_id"])

        # Build SAP content
        sap_lines = []
        sap_lines.append("# STATISTICAL ANALYSIS PLAN")
        sap_lines.append(f"\nGenerated: {datetime.now().isoformat()}")
        sap_lines.append(f"Source: {self.extraction_result['doc_id']}")
        sap_lines.append("\n---\n")

        # Section 1: Study Information (from extraction)
        sap_lines.append("## 1. STUDY INFORMATION")
        sap_lines.append(f"\nExtracted {len(sap_data)} facts from protocol.")
        sap_lines.append("")

        # Section 3: Endpoints (from extraction with provenance)
        sap_lines.append("## 3. ENDPOINTS")
        endpoints = [d for d in sap_data if d["type"] == "endpoint"]

        for ep in endpoints:
            sap_lines.append(f"\n### {ep['name']}")
            sap_lines.append(f"- Type: {ep.get('endpoint_type', 'Not specified')}")
            sap_lines.append(f"- Confidence: {ep['confidence']}")
            sap_lines.append(f"- Source: {ep['source_quote'][:100]}...")
            sap_lines.append(f"<!-- PROVENANCE: {ep['source_doc']} -->")

        # Section 5: Statistical Methods
        sap_lines.append("\n## 5. STATISTICAL METHODS")

        methods = [d for d in sap_data if d["type"] == "method"]
        if methods:
            for m in methods:
                sap_lines.append(f"\n### {m['name']}")
                sap_lines.append(f"- Confidence: {m['confidence']}")
                sap_lines.append(f"- Source: {m['source_quote'][:100]}...")
        else:
            sap_lines.append("\nNo methods explicitly specified in protocol.")

        # KG Context Section (if enabled)
        if use_kg_context and self.kg_context:
            sap_lines.append("\n## APPENDIX: KNOWLEDGE GRAPH CONTEXT")
            sap_lines.append("\n**Note: These are examples from similar trials for REFERENCE only.**")
            sap_lines.append("**The protocol-specified methods take precedence.**\n")

            for ex in self.kg_context.get("endpoint_examples", []):
                sap_lines.append(f"- {ex['fact']}")

            sap_lines.append("\n<!-- KG context provided for tracing, not for decision-making -->")

        # Section 12: TLF Shells
        sap_lines.append("\n## 12. APPENDICES - TLF SHELLS")
        sap_lines.append("\n(TLF tables would be injected here)")

        sap_content = "\n".join(sap_lines)

        print("\n✅ SAP Generated")
        print(f"   Length: {len(sap_content)} chars")
        print(f"   Endpoints: {len(endpoints)}")
        print(f"   Methods: {len(methods)}")
        print(f"   KG Context: {'Included' if use_kg_context else 'Excluded'}")

        return sap_content

    def show_provenance(self) -> Dict:
        """
        Step 4: Show full provenance/tracing for UI.
        """
        print("\n" + "="*70)
        print("STEP 4: PROVENANCE/TRACING FOR UI")
        print("="*70)

        if not self.extraction_result:
            return {}

        sap_data = self.pipeline.get_sap_generation_data(self.extraction_result["doc_id"])

        provenance = {
            "document": self.extraction_result["doc_id"],
            "extraction_time": datetime.now().isoformat(),
            "facts": []
        }

        print("\n┌─────────────────────────────────────────────────────────────┐")
        print("│                    PROVENANCE VIEWER                         │")
        print("├─────────────────────────────────────────────────────────────┤")

        for item in sap_data:
            fact = {
                "type": item["type"],
                "value": item["name"],
                "confidence": item["confidence"],
                "source_quote": item["source_quote"],
                "source_doc": item["source_doc"],
                "editable": True
            }
            provenance["facts"].append(fact)

            print(f"│ {item['type'].upper()}: {item['name'][:40]}")
            print(f"│   📎 Confidence: {item['confidence']}")
            print(f"│   📄 Quote: \"{item['source_quote'][:50]}...\"")
            print(f"│   🔗 Source: {item['source_doc']}")
            print(f"│   ✏️  Editable: Yes")
            print("│")

        print("└─────────────────────────────────────────────────────────────┘")

        return provenance


# =============================================================================
# MAIN TEST
# =============================================================================

def test_full_pipeline(protocol_path: str = None):
    """Test the full KG-enhanced SAP generation pipeline."""

    print("\n" + "="*70)
    print("KNOWLEDGE GRAPH SAP GENERATION TEST")
    print("="*70)

    # Load existing KG (2840 nodes from Claude extraction)
    kg = load_existing_kg()

    # Initialize generator
    generator = KGEnhancedSAPGenerator(kg)

    # Find test protocol
    if protocol_path:
        test_file = Path(protocol_path)
    else:
        # Use a protocol file with survival endpoints
        test_files = [
            Path(__file__).parent.parent.parent / "data/all_pairs/NCT00938041_protocol.txt",
            Path(__file__).parent.parent.parent / "data/all_pairs/NCT00942162_protocol.txt",
        ]
        test_file = next((f for f in test_files if f.exists()), None)

        if not test_file:
            # Fall back to SAP file for testing
            test_files = [
                Path(__file__).parent.parent.parent / "data/all_pairs/NCT00938041_sap.txt",
            ]
            test_file = next((f for f in test_files if f.exists()), None)

    if not test_file or not test_file.exists():
        print(f"❌ No test file found")
        return False

    print(f"\n📄 Test Protocol: {test_file.name}")

    # Step 1: Ingest protocol
    result = generator.ingest_protocol(str(test_file))

    if result["status"] != "success":
        print(f"❌ Ingestion failed: {result}")
        return False

    # Step 2: Query KG for context
    context = generator.query_kg_for_context()

    # Step 3: Generate SAP
    sap_content = generator.generate_sap(use_kg_context=True)

    # Step 4: Show provenance
    provenance = generator.show_provenance()

    # Save outputs
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    # Save generated SAP
    sap_path = output_dir / "kg_generated_sap.md"
    sap_path.write_text(sap_content)
    print(f"\n📄 SAP saved to: {sap_path}")

    # Save provenance
    prov_path = output_dir / "kg_provenance.json"
    with open(prov_path, 'w') as f:
        json.dump(provenance, f, indent=2)
    print(f"📄 Provenance saved to: {prov_path}")

    # Summary
    print("\n" + "="*70)
    print("PIPELINE COMPLETE ✅")
    print("="*70)
    print("""
    Flow:
    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
    │   Protocol   │ ──▶ │  Extract to  │ ──▶ │  Query KG    │
    │   (input)    │     │     KG       │     │  (context)   │
    └──────────────┘     └──────────────┘     └──────────────┘
                                                     │
                                                     ▼
    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
    │  Provenance  │ ◀── │   Generate   │ ◀── │  KG Context  │
    │   (trace)    │     │     SAP      │     │  (examples)  │
    └──────────────┘     └──────────────┘     └──────────────┘

    Key Points:
    ✅ Protocol facts are SOURCE OF TRUTH
    ✅ KG provides examples, NOT recommendations
    ✅ Every fact has provenance (source, quote, confidence)
    ✅ No inference edges used
    ✅ User can edit/correct extracted facts
    """)

    return True


if __name__ == "__main__":
    protocol_path = sys.argv[1] if len(sys.argv) > 1 else None
    success = test_full_pipeline(protocol_path)
    sys.exit(0 if success else 1)
