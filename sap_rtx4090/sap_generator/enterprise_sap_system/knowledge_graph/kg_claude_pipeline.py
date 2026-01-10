"""
Knowledge Graph Pipeline with Claude API
=========================================

Full pipeline using Claude for:
1. Entity extraction from protocol
2. SAP generation with KG context
3. Provenance tracking

Usage:
    python kg_claude_pipeline.py [protocol_file]
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import hashlib

# Add parent paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import anthropic
except ImportError:
    print("Installing anthropic...")
    os.system("pip install anthropic")
    import anthropic

from kg_pipeline_test import (
    FactualKnowledgeGraphV2,
    FlexibleNode,
    FlexibleEdge
)


# =============================================================================
# CLAUDE-POWERED EXTRACTOR
# =============================================================================

class ClaudeKGExtractor:
    """Extract entities from protocol using Claude API."""

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"  # Use Sonnet for cost efficiency

    def extract_entities(self, content: str, doc_id: str) -> List[Dict]:
        """Extract all entities with confidence and provenance."""

        prompt = f"""Extract ALL statistical analysis elements from this clinical trial document.

For each element, provide:
1. The exact type (endpoint, method, population, stratification, table)
2. The name/value
3. A confidence score (0.0-1.0) based on how clearly it's stated
4. The exact quote from the document where you found it
5. The section where it appears (if identifiable)

Return JSON array with this structure:
[
  {{
    "type": "endpoint",
    "name": "Overall Survival",
    "endpoint_type": "primary",
    "definition": "Time from randomization to death from any cause",
    "confidence": 0.95,
    "source_quote": "The primary endpoint is overall survival, defined as...",
    "section": "Section 3.1"
  }},
  {{
    "type": "method",
    "name": "Stratified Log-Rank Test",
    "description": "Primary hypothesis test for survival comparison",
    "confidence": 0.90,
    "source_quote": "The primary analysis will use a stratified log-rank test...",
    "section": "Section 5.1"
  }},
  {{
    "type": "population",
    "name": "Intent-to-Treat",
    "definition": "All randomized subjects",
    "confidence": 0.95,
    "source_quote": "The ITT population includes all randomized subjects...",
    "section": "Section 4"
  }}
]

Extract EVERYTHING you find - endpoints, methods, populations, stratification factors.
Be thorough. Include secondary and exploratory endpoints too.

DOCUMENT:
{content[:15000]}

Return ONLY valid JSON array, no other text."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text.strip()

            # Clean up response
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            extracted = json.loads(response_text)

            # Add doc_id to all items
            for item in extracted:
                item["source_doc"] = doc_id

            return extracted

        except Exception as e:
            print(f"❌ Extraction error: {e}")
            return []


class ClaudeSAPGenerator:
    """Generate SAP using Claude with KG context."""

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"

    def generate_sap(self, extracted_facts: List[Dict], kg_context: List[Dict], protocol_content: str) -> str:
        """Generate full SAP from extracted facts and KG context."""

        # Format extracted facts
        facts_text = json.dumps(extracted_facts, indent=2)

        # Format KG context (individual examples, not aggregated)
        context_text = "\n".join([
            f"- {ex['trial_id']}: {ex['fact']}"
            for ex in kg_context[:5]
        ]) if kg_context else "No similar trials found in knowledge graph."

        prompt = f"""Generate a complete Statistical Analysis Plan (SAP) based on these extracted facts.

EXTRACTED FACTS FROM PROTOCOL:
{facts_text}

EXAMPLES FROM SIMILAR TRIALS (for reference only, protocol takes precedence):
{context_text}

PROTOCOL EXCERPT:
{protocol_content[:8000]}

Generate a complete SAP with these sections:
1. STUDY INFORMATION
2. STUDY OBJECTIVES AND ENDPOINTS
3. STUDY DESIGN
4. ANALYSIS POPULATIONS
5. STATISTICAL METHODS
6. SAMPLE SIZE
7. INTERIM ANALYSES (if applicable)
8. MISSING DATA HANDLING
9. SENSITIVITY ANALYSES
10. SUBGROUP ANALYSES
11. SAFETY ANALYSES
12. APPENDICES - TLF SHELLS (describe key tables)

IMPORTANT RULES:
- Use the protocol's specified methods, NOT inferred from similar trials
- KG examples are for CONTEXT only, not for decision-making
- Include provenance comments showing where each fact came from
- Mark any inferred/assumed information with [INFERRED]
- Be specific about statistical tests, alpha levels, and analysis details

Generate the complete SAP now:"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}]
            )

            return response.content[0].text

        except Exception as e:
            print(f"❌ Generation error: {e}")
            return f"Error generating SAP: {e}"


# =============================================================================
# FULL PIPELINE
# =============================================================================

class ClaudeKGPipeline:
    """Full pipeline: Protocol → KG → SAP with Claude."""

    def __init__(self, api_key: str):
        self.extractor = ClaudeKGExtractor(api_key)
        self.generator = ClaudeSAPGenerator(api_key)
        self.kg = FactualKnowledgeGraphV2()
        self.load_existing_kg()

    def load_existing_kg(self):
        """Load existing Claude-extracted KG."""
        kg_path = Path(__file__).parent / "output" / "factual_kg_claude.json"

        if kg_path.exists():
            with open(kg_path) as f:
                data = json.load(f)

            for n in data.get("nodes", []):
                node = FlexibleNode(
                    id=n["id"],
                    node_type=n["type"],
                    properties=n.get("attributes", {}),
                )
                self.kg.nodes[node.id] = node

            for e in data.get("edges", []):
                edge = FlexibleEdge(
                    source_id=e["source"],
                    target_id=e["target"],
                    edge_type=e["type"],
                    is_factual=True
                )
                self.kg.edges.append(edge)

            print(f"✅ Loaded existing KG: {len(self.kg.nodes)} nodes, {len(self.kg.edges)} edges")

    def process_protocol(self, protocol_path: str) -> Dict:
        """Full pipeline: extract → store in KG → query context → generate SAP."""

        print("\n" + "="*70)
        print("CLAUDE KG PIPELINE")
        print("="*70)

        # Read protocol
        protocol_content = Path(protocol_path).read_text(encoding='utf-8', errors='ignore')
        filename = Path(protocol_path).name
        doc_id = f"doc:{hashlib.md5(filename.encode()).hexdigest()[:8]}"

        print(f"\n📄 Protocol: {filename}")
        print(f"📄 Length: {len(protocol_content)} chars")

        # Step 1: Extract entities with Claude
        print("\n" + "-"*50)
        print("STEP 1: CLAUDE EXTRACTION")
        print("-"*50)

        extracted = self.extractor.extract_entities(protocol_content, doc_id)
        print(f"✅ Extracted {len(extracted)} entities")

        for item in extracted:
            print(f"   • {item['type']}: {item['name']} (conf: {item.get('confidence', 'N/A')})")

        # Step 2: Store in KG
        print("\n" + "-"*50)
        print("STEP 2: STORE IN KNOWLEDGE GRAPH")
        print("-"*50)

        self._store_in_kg(extracted, doc_id)
        print(f"✅ Stored in KG (now {len(self.kg.nodes)} nodes)")

        # Step 3: Query KG for context
        print("\n" + "-"*50)
        print("STEP 3: QUERY KG FOR SIMILAR TRIALS")
        print("-"*50)

        kg_context = self._query_kg_context(extracted)
        print(f"✅ Found {len(kg_context)} similar trial examples")

        for ex in kg_context[:3]:
            print(f"   • {ex['fact']}")

        # Step 4: Generate SAP
        print("\n" + "-"*50)
        print("STEP 4: GENERATE SAP WITH CLAUDE")
        print("-"*50)

        sap_content = self.generator.generate_sap(extracted, kg_context, protocol_content)
        print(f"✅ Generated SAP ({len(sap_content)} chars)")

        # Step 5: Create provenance
        provenance = {
            "document": doc_id,
            "filename": filename,
            "extraction_time": datetime.now().isoformat(),
            "facts": extracted,
            "kg_context": kg_context,
            "model": "claude-sonnet-4-20250514"
        }

        return {
            "sap": sap_content,
            "provenance": provenance,
            "extracted": extracted,
            "kg_context": kg_context
        }

    def _store_in_kg(self, extracted: List[Dict], doc_id: str):
        """Store extracted entities in KG."""

        # Create document node
        doc_node = FlexibleNode(
            id=doc_id,
            node_type="document",
            properties={"doc_id": doc_id}
        )
        self.kg.add_node(doc_node)

        for item in extracted:
            node_id = f"{item['type']}:{hashlib.md5(item['name'].encode()).hexdigest()[:8]}"

            node = FlexibleNode(
                id=node_id,
                node_type=item["type"],
                properties={
                    "name": item["name"],
                    "definition": item.get("definition", ""),
                    "description": item.get("description", "")
                },
                confidence=item.get("confidence", 0.5),
                source_quote=item.get("source_quote", ""),
                source_section=item.get("section", ""),
                source_doc=doc_id,
                editable=True
            )
            self.kg.add_node(node)

            # Create provenance edge
            edge = FlexibleEdge(
                source_id=node_id,
                target_id=doc_id,
                edge_type="extracted_from",
                is_factual=True
            )
            self.kg.add_edge(edge)

    def _query_kg_context(self, extracted: List[Dict]) -> List[Dict]:
        """Query KG for similar trials - returns individual facts, NOT aggregations."""

        context = []
        seen_trials = set()

        # Get endpoint names from extraction
        endpoint_names = [
            item["name"].lower()
            for item in extracted
            if item["type"] == "endpoint"
        ]

        # Find similar trials in KG
        for node_id, node in self.kg.nodes.items():
            if node.node_type == "endpoint":
                node_name = node.properties.get("name", "").lower()

                # Check for similarity
                for ep_name in endpoint_names:
                    if ep_name in node_name or node_name in ep_name:
                        # Find trial with this endpoint
                        for edge in self.kg.edges:
                            if edge.target_id == node_id and edge.edge_type == "has_endpoint":
                                trial = self.kg.nodes.get(edge.source_id)
                                if trial and trial.id not in seen_trials:
                                    seen_trials.add(trial.id)

                                    # Get methods for this endpoint
                                    methods = self._get_methods_for_endpoint(node_id)

                                    # Individual fact, NOT aggregation
                                    context.append({
                                        "trial_id": trial.id,
                                        "endpoint": node.properties.get("name"),
                                        "methods": methods,
                                        "fact": f"{trial.id} analyzed {node.properties.get('name')} with {', '.join(methods) if methods else 'unspecified method'}"
                                    })

                        if len(context) >= 5:
                            break

        return context[:5]

    def _get_methods_for_endpoint(self, endpoint_id: str) -> List[str]:
        """Get methods linked to endpoint."""
        methods = []
        for edge in self.kg.edges:
            if edge.source_id == endpoint_id and edge.edge_type == "analyzed_with":
                method = self.kg.nodes.get(edge.target_id)
                if method:
                    methods.append(method.properties.get("name", method.id))
        return methods


# =============================================================================
# MAIN
# =============================================================================

def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY environment variable not set")
        return

    # Find test protocol
    if len(sys.argv) > 1:
        protocol_path = sys.argv[1]
    else:
        # Use default test protocol
        test_files = [
            Path(__file__).parent.parent.parent / "data/all_pairs/NCT00938041_protocol.txt",
            Path(__file__).parent.parent.parent / "data/all_pairs/NCT00942162_protocol.txt",
        ]
        protocol_path = next((f for f in test_files if f.exists()), None)

        if not protocol_path:
            # Fall back to SAP file
            protocol_path = Path(__file__).parent.parent.parent / "data/all_pairs/NCT00938041_sap.txt"

    if not Path(protocol_path).exists():
        print(f"❌ File not found: {protocol_path}")
        return

    # Run pipeline
    pipeline = ClaudeKGPipeline(api_key)
    result = pipeline.process_protocol(str(protocol_path))

    # Save outputs
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    # Save SAP
    sap_path = output_dir / "claude_kg_generated_sap.md"
    sap_path.write_text(result["sap"])
    print(f"\n📄 SAP saved: {sap_path}")

    # Save provenance
    prov_path = output_dir / "claude_kg_provenance.json"
    with open(prov_path, 'w') as f:
        json.dump(result["provenance"], f, indent=2)
    print(f"📄 Provenance saved: {prov_path}")

    # Print SAP preview
    print("\n" + "="*70)
    print("GENERATED SAP PREVIEW")
    print("="*70)
    print(result["sap"][:2000])
    print("\n... (truncated)")

    print("\n" + "="*70)
    print("PIPELINE COMPLETE ✅")
    print("="*70)


if __name__ == "__main__":
    main()
