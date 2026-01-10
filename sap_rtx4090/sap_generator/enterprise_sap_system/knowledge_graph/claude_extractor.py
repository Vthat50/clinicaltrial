"""
Claude-Powered Fact Extractor v1.0
==================================

Uses Claude to extract FACTS with FULL PROVENANCE from SAP documents.

Extracts:
- Endpoints (primary, secondary, exploratory) with exact definitions
- Statistical methods with parameters
- Analysis populations with definitions
- Stratification factors with categories
- TFL references
- Exact quotes with page/section

All extractions include:
- exact_quote: The verbatim text from the document
- section: Section number/name where found
- page: Page number (if available)

NO INFERENCE - only facts from the document.
"""

import json
import re
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import hashlib

# Import the factual knowledge graph
from factual_knowledge_graph import (
    FactualKnowledgeGraph, FactExtractor,
    TrialNode, DocumentNode, EndpointNode, MethodNode,
    PopulationNode, StratumNode, QuoteNode, TableNode,
    CensoringRuleNode, MultiplicityNode, VisitNode, EstimandNode,
    Edge, EdgeType
)

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("Warning: anthropic package not installed. Using mock extraction.")


# =============================================================================
# EXTRACTION PROMPTS
# =============================================================================

ENDPOINT_EXTRACTION_PROMPT = """Extract ALL endpoints from this SAP document. For each endpoint, provide:

1. name: The endpoint name (e.g., "Progression-Free Survival", "Overall Survival")
2. type: "primary", "secondary", or "exploratory"
3. definition: The exact definition from the document
4. exact_quote: The verbatim text defining this endpoint (copy exactly)
5. section: The section number or name where this was found

Return as JSON array. Example:
```json
[
  {
    "name": "Progression-Free Survival",
    "type": "primary",
    "definition": "Time from randomization to first documented disease progression per RECIST v1.1 or death from any cause",
    "exact_quote": "The primary endpoint is progression-free survival (PFS), defined as the time from the date of randomization to the date of first documented disease progression as determined by BICR using RECIST v1.1 or death due to any cause, whichever occurs first.",
    "section": "3.1 Primary Endpoint"
  }
]
```

SAP Document:
{content}

Extract ALL endpoints mentioned. Return ONLY valid JSON array."""

METHOD_EXTRACTION_PROMPT = """Extract ALL statistical methods from this SAP document. For each method, provide:

1. name: The method name (e.g., "Stratified Log-Rank Test", "Cox Proportional Hazards")
2. endpoint: Which endpoint this method is used for
3. parameters: Any specific parameters (e.g., stratification factors, tie handling, alpha level)
4. exact_quote: The verbatim text describing this method (copy exactly)
5. section: The section number or name where this was found

Return as JSON array. Example:
```json
[
  {
    "name": "Stratified Log-Rank Test",
    "endpoint": "Progression-Free Survival",
    "parameters": {
      "stratification_factors": ["ECOG PS", "Geographic Region"],
      "alpha": 0.025,
      "one_sided": true
    },
    "exact_quote": "The primary analysis of PFS will be performed using a stratified log-rank test with stratification factors of ECOG performance status (0 vs 1) and geographic region (North America vs Europe vs Rest of World) at a one-sided significance level of 0.025.",
    "section": "5.1.1 Primary Analysis"
  }
]
```

SAP Document:
{content}

Extract ALL statistical methods mentioned. Return ONLY valid JSON array."""

POPULATION_EXTRACTION_PROMPT = """Extract ALL analysis populations from this SAP document. For each population, provide:

1. name: The population name (e.g., "Intent-to-Treat", "Safety Population")
2. abbreviation: Common abbreviation (e.g., "ITT", "SAF")
3. definition: The exact definition
4. exact_quote: The verbatim text defining this population (copy exactly)
5. section: The section number or name where this was found

Return as JSON array. Example:
```json
[
  {
    "name": "Intent-to-Treat Population",
    "abbreviation": "ITT",
    "definition": "All randomized subjects analyzed according to randomized treatment assignment",
    "exact_quote": "The intent-to-treat (ITT) population is defined as all subjects who were randomized, regardless of whether they received study treatment. Subjects will be analyzed according to the treatment to which they were randomized.",
    "section": "4.1 Analysis Populations"
  }
]
```

SAP Document:
{content}

Extract ALL analysis populations mentioned. Return ONLY valid JSON array."""

STRATIFICATION_EXTRACTION_PROMPT = """Extract ALL stratification factors from this SAP document. For each factor, provide:

1. factor_name: The stratification factor name
2. categories: List of categories/levels
3. source: Where stratification comes from (IXRS, CRF, etc.)
4. exact_quote: The verbatim text describing this stratification (copy exactly)
5. section: The section number or name where this was found

Return as JSON array. Example:
```json
[
  {
    "factor_name": "ECOG Performance Status",
    "categories": ["0", "1"],
    "source": "IXRS",
    "exact_quote": "Randomization will be stratified by ECOG performance status (0 vs 1) as recorded in the IXRS at time of randomization.",
    "section": "2.3 Stratification"
  }
]
```

SAP Document:
{content}

Extract ALL stratification factors mentioned. Return ONLY valid JSON array."""

TFL_EXTRACTION_PROMPT = """Extract ALL Tables, Figures, and Listings (TFLs) mentioned in this SAP document. For each TFL, provide:

1. tfl_id: The table/figure/listing number (e.g., "14.1.1", "Figure 1")
2. title: The full title
3. type: "table", "figure", or "listing"
4. population: Which population this TFL uses
5. section: The section where this TFL is described

Return as JSON array. Example:
```json
[
  {
    "tfl_id": "14.2.1",
    "title": "Summary of Progression-Free Survival (ITT Population)",
    "type": "table",
    "population": "ITT",
    "section": "Section 11 TFL Shells"
  }
]
```

SAP Document:
{content}

Extract ALL TFLs mentioned. Return ONLY valid JSON array."""

BASELINE_VARIABLES_PROMPT = """Extract ALL baseline/demographic variables that will be collected in this study. For each variable, provide:

1. name: The variable name (e.g., "Age", "BMI", "ASA Score", "Country")
2. type: "demographic", "medical_history", "lab_parameter", "vital_sign", or "other"
3. categories: List of categories if categorical (e.g., ["Male", "Female"] for Sex)
4. unit: Unit of measurement if continuous (e.g., "kg/m²" for BMI)
5. exact_quote: The verbatim text mentioning this variable

IMPORTANT: Look for:
- Performance status scales (ECOG, ASA Score, Karnofsky, WHO)
- Country/Region of enrollment
- BMI vs Weight
- Disease-specific variables (mutation status, tumor location, stage)
- Lab parameters collected at baseline

Return as JSON array. Example:
```json
[
  {
    "name": "ASA Physical Status",
    "type": "medical_history",
    "categories": ["1", "2", "3", "4", "5"],
    "unit": null,
    "exact_quote": "ASA physical status classification (1-5) will be recorded at baseline"
  },
  {
    "name": "BMI",
    "type": "vital_sign",
    "categories": null,
    "unit": "kg/m²",
    "exact_quote": "Body mass index (BMI) calculated as weight(kg)/height(m)²"
  },
  {
    "name": "Country",
    "type": "demographic",
    "categories": ["Sweden", "Norway", "Denmark", "Finland"],
    "unit": null,
    "exact_quote": "Subjects enrolled from sites in Sweden, Norway, Denmark, and Finland"
  }
]
```

SAP Document:
{content}

Extract ALL baseline variables mentioned. Return ONLY valid JSON array."""

SAFETY_ASSESSMENT_PROMPT = """Extract safety assessment details from this document. Provide:

1. ae_grading_scale: How AEs are graded (e.g., "CTCAE v5.0", "Mild/Moderate/Severe", "WHO Toxicity")
2. ae_coding: How AEs are coded (e.g., "MedDRA v26.0")
3. sae_categories: List of SAE categories if defined
4. dose_modification: Whether dose modification is applicable
5. exact_quotes: Verbatim text for each

Return as JSON object. Example:
```json
{
  "ae_grading_scale": "Mild/Moderate/Severe",
  "ae_coding": "MedDRA v25.0",
  "sae_categories": ["Death", "Hospitalization", "Life-threatening"],
  "dose_modification": false,
  "exact_quotes": {
    "grading": "Adverse events will be graded as mild, moderate, or severe",
    "coding": "AEs will be coded using MedDRA version 25.0"
  }
}
```

SAP Document:
{content}

Extract safety assessment details. Return ONLY valid JSON object."""

TRIAL_METADATA_PROMPT = """Extract trial metadata from this SAP document. Provide:

1. phase: The trial phase (e.g., "Phase 1", "Phase 2", "Phase 3", "Phase 1/2", "Phase 2/3")
2. indication: The disease/condition being studied
3. treatment: The investigational treatment
4. comparator: The comparator arm (if any)
5. design: Study design (e.g., "randomized, double-blind, placebo-controlled")

Return as JSON object. Example:
```json
{
  "phase": "Phase 3",
  "indication": "Non-small cell lung cancer",
  "treatment": "Pembrolizumab",
  "comparator": "Docetaxel",
  "design": "Randomized, open-label, multicenter"
}
```

SAP Document:
{content}

Extract trial metadata. Return ONLY valid JSON object."""

CENSORING_RULES_PROMPT = """Extract ALL censoring rules from this SAP document. For each rule, provide:

1. endpoint: Which endpoint this applies to (e.g., "PFS", "OS")
2. scenario: The scenario/situation (e.g., "No documented progression and alive", "Lost to follow-up")
3. event_status: "event" or "censored"
4. date_used: What date is used (e.g., "Date of last tumor assessment", "Date of randomization")
5. exact_quote: The verbatim text describing this rule

Return as JSON array. Example:
```json
[
  {
    "endpoint": "PFS",
    "scenario": "Death without prior documented progression",
    "event_status": "event",
    "date_used": "Date of death",
    "exact_quote": "Death without prior documented progression will be considered a PFS event, with the date of death used as the event date."
  },
  {
    "endpoint": "PFS",
    "scenario": "No documented progression and alive",
    "event_status": "censored",
    "date_used": "Date of last adequate tumor assessment",
    "exact_quote": "Subjects without documented progression and who are alive will be censored at the date of their last adequate tumor assessment."
  },
  {
    "endpoint": "PFS",
    "scenario": "Started new anticancer therapy before progression",
    "event_status": "censored",
    "date_used": "Date of last tumor assessment before new therapy",
    "exact_quote": "Subjects who start new anticancer therapy without documented progression will be censored at the date of last tumor assessment before initiation of new therapy."
  }
]
```

SAP Document:
{content}

Extract ALL censoring rules. Return ONLY valid JSON array."""

MULTIPLICITY_PROMPT = """Extract multiplicity adjustment strategy from this SAP document. Provide:

1. method: The adjustment method (e.g., "Fixed-sequence", "Hochberg", "Holm", "Graphical", "Bonferroni", "Hierarchical")
2. overall_alpha: The overall Type I error rate (e.g., 0.05, 0.025 one-sided)
3. endpoints_in_strategy: List of endpoints included in the multiplicity strategy
4. alpha_allocation: How alpha is allocated (if applicable)
5. testing_sequence: The order of hypothesis testing (if sequential)
6. exact_quote: The verbatim text describing the strategy
7. section: Section where this was found

Return as JSON object. Example:
```json
{
  "method": "Fixed-sequence",
  "overall_alpha": 0.025,
  "one_sided": true,
  "endpoints_in_strategy": ["PFS", "OS"],
  "alpha_allocation": {"PFS": 0.025, "OS": 0.025},
  "testing_sequence": ["PFS", "OS"],
  "gatekeeping": "OS tested only if PFS is significant",
  "exact_quote": "A fixed-sequence testing procedure will be used to control the overall Type I error at 0.025 (one-sided). PFS will be tested first at alpha=0.025. If PFS is statistically significant, OS will be tested at alpha=0.025.",
  "section": "5.1 Multiplicity Adjustment"
}
```

SAP Document:
{content}

Extract multiplicity adjustment strategy. Return ONLY valid JSON object (or empty object if none found)."""

VISIT_SCHEDULE_PROMPT = """Extract the visit/assessment schedule from this SAP document. For each visit or assessment timepoint, provide:

1. visit_name: Name of the visit (e.g., "Screening", "Baseline", "Week 8", "End of Treatment")
2. timing: When the visit occurs (e.g., "Day 1", "Week 8", "Every 6 weeks")
3. window: Allowed window (e.g., "± 3 days", "± 7 days")
4. assessments: What assessments are performed (e.g., ["Tumor assessment", "Labs", "ECG"])
5. tumor_assessment: true/false if tumor imaging is done at this visit

Return as JSON array. Example:
```json
[
  {
    "visit_name": "Screening",
    "timing": "Day -28 to Day -1",
    "window": "",
    "assessments": ["CT/MRI scan", "Labs", "ECG", "ECOG PS"],
    "tumor_assessment": true
  },
  {
    "visit_name": "Week 8",
    "timing": "Week 8",
    "window": "± 7 days",
    "assessments": ["CT/MRI scan", "Labs", "AE assessment"],
    "tumor_assessment": true
  },
  {
    "visit_name": "Tumor Assessment",
    "timing": "Every 8 weeks for first 48 weeks, then every 12 weeks",
    "window": "± 7 days",
    "assessments": ["CT/MRI scan per RECIST v1.1"],
    "tumor_assessment": true
  }
]
```

SAP Document:
{content}

Extract visit schedule. Return ONLY valid JSON array."""

ESTIMAND_PROMPT = """Extract estimand definitions from this SAP document (ICH E9(R1) framework). For each estimand, provide:

1. endpoint: The variable being measured
2. population: Target population
3. treatment_condition: Treatment being compared
4. summary_measure: Effect measure (e.g., "Hazard ratio", "Difference in proportions", "Odds ratio")
5. intercurrent_events: List of intercurrent events and their handling strategies
   - event: The intercurrent event (e.g., "Treatment discontinuation", "Use of rescue medication", "Death")
   - strategy: How it's handled ("treatment_policy", "composite", "hypothetical", "principal_stratum", "while_on_treatment")
6. exact_quote: Verbatim text describing this estimand

Return as JSON array. Example:
```json
[
  {
    "endpoint": "Progression-Free Survival",
    "population": "ITT population",
    "treatment_condition": "Drug A vs Placebo",
    "summary_measure": "Hazard ratio",
    "intercurrent_events": [
      {"event": "Treatment discontinuation due to AE", "strategy": "treatment_policy"},
      {"event": "Use of subsequent anticancer therapy", "strategy": "treatment_policy"},
      {"event": "Death", "strategy": "composite"}
    ],
    "exact_quote": "The primary estimand for PFS is defined using the treatment policy strategy for intercurrent events...",
    "section": "3.2 Estimands"
  }
]
```

SAP Document:
{content}

Extract estimand definitions. Return ONLY valid JSON array (or empty array if not defined)."""


# =============================================================================
# CLAUDE EXTRACTOR
# =============================================================================

class ClaudeFactExtractor:
    """
    Uses Claude to extract facts with full provenance from SAP documents.
    """

    def __init__(self, graph: FactualKnowledgeGraph, api_key: str = None):
        self.graph = graph
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

        if ANTHROPIC_AVAILABLE and self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        else:
            self.client = None

    def extract_with_claude(self, prompt: str, content: str) -> List[Dict]:
        """Call Claude API to extract facts."""
        if not self.client:
            return []

        # Truncate content if too long (keep first 80k chars to leave room for prompt)
        if len(content) > 80000:
            content = content[:80000] + "\n...[truncated]..."

        full_prompt = prompt.replace("{content}", content)

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{"role": "user", "content": full_prompt}]
            )

            # Parse JSON from response
            response_text = response.content[0].text

            # Try to extract JSON array from response
            # First try to find a code block with JSON
            code_block_match = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', response_text)
            if code_block_match:
                return json.loads(code_block_match.group(1))

            # Then try to find raw JSON array
            json_match = re.search(r'\[\s*\{[\s\S]*?\}\s*\]', response_text)
            if json_match:
                return json.loads(json_match.group())

            # Try parsing the entire response as JSON
            try:
                parsed = json.loads(response_text)
                if isinstance(parsed, list):
                    return parsed
            except:
                pass

            # If response looks like it might be JSON but parsing failed
            if '[' in response_text and ']' in response_text:
                # Try to clean up common issues
                start = response_text.find('[')
                end = response_text.rfind(']') + 1
                try:
                    return json.loads(response_text[start:end])
                except:
                    pass

        except Exception as e:
            print(f"Claude extraction error: {e}")

        return []

    def extract_all_facts(self, sap_content: str, nct_id: str, filename: str) -> Dict:
        """
        Extract all facts from a SAP document using Claude.
        Returns extraction statistics.
        """
        stats = {
            "endpoints": 0,
            "methods": 0,
            "populations": 0,
            "stratification": 0,
            "tfls": 0,
            "quotes": 0,
            "censoring_rules": 0,
            "multiplicity": 0,
            "visits": 0,
            "estimands": 0
        }

        # Extract trial metadata first
        metadata = self.extract_with_claude(TRIAL_METADATA_PROMPT, sap_content)
        if isinstance(metadata, list) and len(metadata) > 0:
            metadata = metadata[0]
        elif not isinstance(metadata, dict):
            metadata = {}

        # Create trial node with metadata
        trial = TrialNode(
            nct_id=nct_id,
            phase=metadata.get("phase", ""),
            indication=metadata.get("indication", ""),
            title=metadata.get("treatment", "")
        )
        trial_id = self.graph.add_node(trial)

        # Create document node
        doc = DocumentNode(filename=filename, doc_type="SAP", trial_id=nct_id)
        doc_id = self.graph.add_node(doc)

        # Link trial to document
        self.graph.add_edge(Edge(
            source_id=trial_id,
            target_id=doc_id,
            edge_type=EdgeType.EXTRACTED_FROM
        ))

        # Extract endpoints
        endpoints = self.extract_with_claude(ENDPOINT_EXTRACTION_PROMPT, sap_content)
        for ep in endpoints:
            endpoint_node = EndpointNode(
                name=ep.get("name", ""),
                endpoint_type=ep.get("type", ""),
                definition=ep.get("definition", "")
            )
            endpoint_id = self.graph.add_node(endpoint_node)

            # Link trial to endpoint (FACTUAL)
            self.graph.add_edge(Edge(
                source_id=trial_id,
                target_id=endpoint_id,
                edge_type=EdgeType.HAS_ENDPOINT,
                attributes={"provenance": doc_id}
            ))

            # Add quote provenance
            if ep.get("exact_quote"):
                quote = QuoteNode(
                    text=ep["exact_quote"],
                    section=ep.get("section", ""),
                    page=""
                )
                quote_id = self.graph.add_node(quote)

                self.graph.add_edge(Edge(
                    source_id=endpoint_id,
                    target_id=quote_id,
                    edge_type=EdgeType.QUOTED_AS,
                    attributes={"document": doc_id}
                ))
                stats["quotes"] += 1

            stats["endpoints"] += 1

        # Extract methods
        methods = self.extract_with_claude(METHOD_EXTRACTION_PROMPT, sap_content)
        for m in methods:
            method_node = MethodNode(
                name=m.get("name", ""),
                description=json.dumps(m.get("parameters", {}))
            )
            method_id = self.graph.add_node(method_node)

            # Find matching endpoint and link
            endpoint_name = m.get("endpoint", "")
            for ep in endpoints:
                ep_name = ep.get("name", "")
                ep_type = ep.get("type", "")
                if ep_name.lower() in endpoint_name.lower() or endpoint_name.lower() in ep_name.lower():
                    endpoint_id = f"endpoint:{hashlib.md5(f'{ep_name}:{ep_type}'.encode()).hexdigest()[:8]}"
                    if endpoint_id in self.graph.nodes:
                        self.graph.add_edge(Edge(
                            source_id=endpoint_id,
                            target_id=method_id,
                            edge_type=EdgeType.ANALYZED_WITH,
                            attributes={"provenance": doc_id}
                        ))

            # Add quote provenance
            if m.get("exact_quote"):
                quote = QuoteNode(
                    text=m["exact_quote"],
                    section=m.get("section", ""),
                    page=""
                )
                quote_id = self.graph.add_node(quote)

                self.graph.add_edge(Edge(
                    source_id=method_id,
                    target_id=quote_id,
                    edge_type=EdgeType.QUOTED_AS,
                    attributes={"document": doc_id}
                ))
                stats["quotes"] += 1

            stats["methods"] += 1

        # Extract populations
        populations = self.extract_with_claude(POPULATION_EXTRACTION_PROMPT, sap_content)
        for pop in populations:
            pop_node = PopulationNode(
                name=pop.get("name", ""),
                definition=pop.get("definition", "")
            )
            pop_id = self.graph.add_node(pop_node)

            self.graph.add_edge(Edge(
                source_id=trial_id,
                target_id=pop_id,
                edge_type=EdgeType.HAS_POPULATION,
                attributes={"provenance": doc_id}
            ))

            # Add quote provenance
            if pop.get("exact_quote"):
                quote = QuoteNode(
                    text=pop["exact_quote"],
                    section=pop.get("section", ""),
                    page=""
                )
                quote_id = self.graph.add_node(quote)

                self.graph.add_edge(Edge(
                    source_id=pop_id,
                    target_id=quote_id,
                    edge_type=EdgeType.QUOTED_AS,
                    attributes={"document": doc_id}
                ))
                stats["quotes"] += 1

            stats["populations"] += 1

        # Extract stratification
        strats = self.extract_with_claude(STRATIFICATION_EXTRACTION_PROMPT, sap_content)
        for strat in strats:
            strat_node = StratumNode(
                factor_name=strat.get("factor_name", ""),
                categories=strat.get("categories", [])
            )
            strat_id = self.graph.add_node(strat_node)

            self.graph.add_edge(Edge(
                source_id=trial_id,
                target_id=strat_id,
                edge_type=EdgeType.STRATIFIED_BY,
                attributes={"provenance": doc_id, "source": strat.get("source", "")}
            ))

            # Add quote provenance
            if strat.get("exact_quote"):
                quote = QuoteNode(
                    text=strat["exact_quote"],
                    section=strat.get("section", ""),
                    page=""
                )
                quote_id = self.graph.add_node(quote)

                self.graph.add_edge(Edge(
                    source_id=strat_id,
                    target_id=quote_id,
                    edge_type=EdgeType.QUOTED_AS,
                    attributes={"document": doc_id}
                ))
                stats["quotes"] += 1

            stats["stratification"] += 1

        # Extract TFLs
        tfls = self.extract_with_claude(TFL_EXTRACTION_PROMPT, sap_content)
        for tfl in tfls:
            tfl_node = TableNode(
                table_id=tfl.get("tfl_id", ""),
                title=tfl.get("title", ""),
                table_type=tfl.get("type", "table")
            )
            tfl_id = self.graph.add_node(tfl_node)

            self.graph.add_edge(Edge(
                source_id=trial_id,
                target_id=tfl_id,
                edge_type=EdgeType.USES_TEMPLATE,
                attributes={"provenance": doc_id, "population": tfl.get("population", "")}
            ))

            stats["tfls"] += 1

        # Extract censoring rules
        censoring_rules = self.extract_with_claude(CENSORING_RULES_PROMPT, sap_content)
        for rule in censoring_rules:
            rule_node = CensoringRuleNode(
                endpoint=rule.get("endpoint", ""),
                event_type=rule.get("event_status", ""),
                censoring_reason=rule.get("scenario", ""),
                censoring_date=rule.get("date_used", "")
            )
            rule_id = self.graph.add_node(rule_node)

            # Link to endpoint if we can find it
            endpoint_name = rule.get("endpoint", "").lower()
            for ep in endpoints:
                if endpoint_name in ep.get("name", "").lower():
                    ep_name = ep.get("name", "")
                    ep_type = ep.get("type", "")
                    endpoint_id = f"endpoint:{hashlib.md5(f'{ep_name}:{ep_type}'.encode()).hexdigest()[:8]}"
                    if endpoint_id in self.graph.nodes:
                        self.graph.add_edge(Edge(
                            source_id=endpoint_id,
                            target_id=rule_id,
                            edge_type=EdgeType.CENSORED_BY,
                            attributes={"provenance": doc_id}
                        ))
                    break

            # Add quote provenance
            if rule.get("exact_quote"):
                quote = QuoteNode(
                    text=rule["exact_quote"],
                    section="Censoring Rules",
                    page=""
                )
                quote_id = self.graph.add_node(quote)
                self.graph.add_edge(Edge(
                    source_id=rule_id,
                    target_id=quote_id,
                    edge_type=EdgeType.QUOTED_AS,
                    attributes={"document": doc_id}
                ))
                stats["quotes"] += 1

            stats["censoring_rules"] += 1

        # Extract multiplicity adjustment
        multiplicity = self.extract_with_claude(MULTIPLICITY_PROMPT, sap_content)
        if isinstance(multiplicity, list) and len(multiplicity) > 0:
            multiplicity = multiplicity[0]
        if isinstance(multiplicity, dict) and multiplicity.get("method"):
            mult_node = MultiplicityNode(
                method=multiplicity.get("method", ""),
                endpoints=multiplicity.get("endpoints_in_strategy", []),
                alpha=multiplicity.get("overall_alpha", 0.05),
                allocation=multiplicity.get("alpha_allocation", {}),
                sequence=multiplicity.get("testing_sequence", [])
            )
            mult_id = self.graph.add_node(mult_node)

            self.graph.add_edge(Edge(
                source_id=trial_id,
                target_id=mult_id,
                edge_type=EdgeType.ADJUSTED_BY,
                attributes={"provenance": doc_id}
            ))

            # Add quote provenance
            if multiplicity.get("exact_quote"):
                quote = QuoteNode(
                    text=multiplicity["exact_quote"],
                    section=multiplicity.get("section", "Multiplicity"),
                    page=""
                )
                quote_id = self.graph.add_node(quote)
                self.graph.add_edge(Edge(
                    source_id=mult_id,
                    target_id=quote_id,
                    edge_type=EdgeType.QUOTED_AS,
                    attributes={"document": doc_id}
                ))
                stats["quotes"] += 1

            stats["multiplicity"] += 1

        # Extract visit schedule
        visits = self.extract_with_claude(VISIT_SCHEDULE_PROMPT, sap_content)
        for visit in visits:
            visit_node = VisitNode(
                visit_name=visit.get("visit_name", ""),
                timing=visit.get("timing", ""),
                window=visit.get("window", ""),
                assessments=visit.get("assessments", [])
            )
            visit_id = self.graph.add_node(visit_node)

            self.graph.add_edge(Edge(
                source_id=trial_id,
                target_id=visit_id,
                edge_type=EdgeType.HAS_VISIT,
                attributes={"provenance": doc_id, "tumor_assessment": visit.get("tumor_assessment", False)}
            ))

            stats["visits"] += 1

        # Extract estimands
        estimands = self.extract_with_claude(ESTIMAND_PROMPT, sap_content)
        for est in estimands:
            est_node = EstimandNode(
                endpoint=est.get("endpoint", ""),
                population=est.get("population", ""),
                treatment=est.get("treatment_condition", ""),
                summary_measure=est.get("summary_measure", ""),
                intercurrent_events=est.get("intercurrent_events", [])
            )
            est_id = self.graph.add_node(est_node)

            self.graph.add_edge(Edge(
                source_id=trial_id,
                target_id=est_id,
                edge_type=EdgeType.HAS_ESTIMAND,
                attributes={"provenance": doc_id}
            ))

            # Add quote provenance
            if est.get("exact_quote"):
                quote = QuoteNode(
                    text=est["exact_quote"],
                    section=est.get("section", "Estimands"),
                    page=""
                )
                quote_id = self.graph.add_node(quote)
                self.graph.add_edge(Edge(
                    source_id=est_id,
                    target_id=quote_id,
                    edge_type=EdgeType.QUOTED_AS,
                    attributes={"document": doc_id}
                ))
                stats["quotes"] += 1

            stats["estimands"] += 1

        return stats


# =============================================================================
# BATCH EXTRACTION
# =============================================================================

def extract_from_all_saps(sap_directory: Path, output_path: Path, max_files: int = None) -> FactualKnowledgeGraph:
    """
    Extract facts from all SAP files using Claude.

    Args:
        sap_directory: Directory containing SAP .txt files
        output_path: Path to save the knowledge graph JSON
        max_files: Maximum number of files to process (None = all)
    """
    graph = FactualKnowledgeGraph()
    extractor = ClaudeFactExtractor(graph)

    if not extractor.client:
        print("⚠️  No Claude API available. Set ANTHROPIC_API_KEY environment variable.")
        print("    Falling back to regex extraction.")
        # Fall back to regex extraction
        from factual_knowledge_graph import build_factual_graph_from_saps
        return build_factual_graph_from_saps(sap_directory)

    sap_files = list(sap_directory.glob("*_sap.txt"))
    if max_files:
        sap_files = sap_files[:max_files]

    total_stats = {
        "files_processed": 0,
        "endpoints": 0,
        "methods": 0,
        "populations": 0,
        "stratification": 0,
        "tfls": 0,
        "quotes": 0,
        "censoring_rules": 0,
        "multiplicity": 0,
        "visits": 0,
        "estimands": 0
    }

    print(f"Processing {len(sap_files)} SAP files with Claude extraction...", flush=True)

    for i, sap_file in enumerate(sap_files):
        filename = sap_file.name
        nct_id = filename.split("_")[0]

        print(f"  [{i+1}/{len(sap_files)}] Processing {nct_id}...", end=" ", flush=True)

        try:
            content = sap_file.read_text(encoding='utf-8', errors='ignore')
            stats = extractor.extract_all_facts(content, nct_id, filename)

            total_stats["files_processed"] += 1
            for key in ["endpoints", "methods", "populations", "stratification", "tfls", "quotes",
                        "censoring_rules", "multiplicity", "visits", "estimands"]:
                total_stats[key] += stats.get(key, 0)

            print(f"✓ (ep:{stats['endpoints']} meth:{stats['methods']} cens:{stats['censoring_rules']} est:{stats['estimands']})")

        except Exception as e:
            import traceback
            print(f"✗ Error: {e}")
            traceback.print_exc()

    # Export graph
    graph.export_json(output_path)

    print("\n" + "=" * 80)
    print("CLAUDE EXTRACTION COMPLETE")
    print("=" * 80)
    print(f"Files processed: {total_stats['files_processed']}")
    print(f"Endpoints extracted: {total_stats['endpoints']}")
    print(f"Methods extracted: {total_stats['methods']}")
    print(f"Populations extracted: {total_stats['populations']}")
    print(f"Stratification factors: {total_stats['stratification']}")
    print(f"TFLs extracted: {total_stats['tfls']}")
    print(f"Censoring rules: {total_stats['censoring_rules']}")
    print(f"Multiplicity adjustments: {total_stats['multiplicity']}")
    print(f"Visit schedules: {total_stats['visits']}")
    print(f"Estimands: {total_stats['estimands']}")
    print(f"Quotes with provenance: {total_stats['quotes']}")
    print("=" * 80)

    return graph


# =============================================================================
# QUERY INTERFACE
# =============================================================================

class KnowledgeGraphQuery:
    """
    Query interface for the factual knowledge graph.
    Returns facts with provenance - NO INFERENCE.
    """

    def __init__(self, graph: FactualKnowledgeGraph):
        self.graph = graph

    def get_similar_trials(self, indication: str, phase: str) -> List[Dict]:
        """
        Find similar trials by indication and phase.
        Returns facts about what those trials did - not recommendations.
        """
        similar = []
        for node_id, node in self.graph.nodes.items():
            if node.node_type.value == "trial":
                attrs = node.attributes
                if (indication.lower() in attrs.get("indication", "").lower() or
                    phase.lower() in attrs.get("phase", "").lower()):
                    similar.append(self.graph.query_by_trial(node_id))
        return similar

    def get_method_examples(self, method_name: str) -> List[Dict]:
        """
        Find all trials that used a specific method.
        Returns factual examples with provenance.
        """
        return self.graph.query_method_usage(method_name)

    def get_endpoint_definitions(self, endpoint_name: str) -> List[Dict]:
        """
        Find all definitions of an endpoint across trials.
        Returns exact quotes with sources.
        """
        results = []
        for node_id, node in self.graph.nodes.items():
            if node.node_type.value == "endpoint":
                if endpoint_name.lower() in node.attributes.get("name", "").lower():
                    # Get quotes for this endpoint
                    quotes = []
                    for edge in self.graph.get_edges_from(node_id, EdgeType.QUOTED_AS):
                        quote_node = self.graph.get_node(edge.target_id)
                        if quote_node:
                            quotes.append({
                                "text": quote_node.attributes.get("text", ""),
                                "section": quote_node.attributes.get("section", ""),
                                "document": edge.attributes.get("document", "")
                            })

                    results.append({
                        "endpoint": node.to_dict(),
                        "quotes": quotes
                    })
        return results


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    # Find SAP directory
    sap_dir = Path(__file__).parent.parent.parent / "data" / "all_pairs"

    if not sap_dir.exists():
        print(f"SAP directory not found: {sap_dir}")
        exit(1)

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("=" * 80)
        print("ANTHROPIC_API_KEY not set")
        print("=" * 80)
        print("To run Claude extraction, set the environment variable:")
        print("  export ANTHROPIC_API_KEY='your-api-key'")
        print("")
        print("Without API key, falling back to regex extraction.")
        print("=" * 80)

    # Extract from SAP files
    # Set max_files=None to process all files
    graph = extract_from_all_saps(
        sap_directory=sap_dir,
        output_path=output_dir / "factual_kg_claude.json",
        max_files=None  # Process all files
    )

    print(f"\nGraph saved to: {output_dir / 'factual_kg_claude.json'}")
