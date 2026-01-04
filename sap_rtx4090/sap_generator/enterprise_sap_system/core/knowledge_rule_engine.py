#!/usr/bin/env python3
"""
Knowledge Graph Rule Engine for SAP Generation
===============================================

REFACTORED ARCHITECTURE (2025-01):
==================================
This engine provides CONTEXT, not DECISIONS. The protocol is the source of truth.

What this engine DOES:
- Detect conditions present in the protocol (immunotherapy, interim analysis, etc.)
- Provide scientific context for those conditions
- Flag discrepancies for human review

What this engine does NOT do:
- Select statistical methods based on drug class
- Override protocol-specified methods
- Make any method decisions

All method choices come from EXTRACTION, not inference.
"""

import json
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Set


@dataclass
class ConditionContext:
    """Context information for a detected condition."""
    condition: str
    note: str
    implication: Optional[str] = None
    common_methods: Optional[List[str]] = None
    sources: Optional[List[str]] = None


class KnowledgeRuleEngine:
    """
    Provides scientific CONTEXT for protocol conditions.

    CRITICAL: This engine does NOT make method decisions.
    Protocol extraction is the source of truth for all method choices.

    The 99 rules in the knowledge graph provide:
    - Background on what methods are commonly used with conditions
    - Evidence sources (NCT IDs, FDA guidances, literature)
    - Co-occurrence patterns for method combinations

    This is INFORMATIONAL context for LLM prompts, NOT decision-making.
    """

    def __init__(self, knowledge_graph_path: Path = None):
        """
        Initialize rule engine with knowledge graph.

        Args:
            knowledge_graph_path: Path to sap_knowledge_graph.json
        """
        if knowledge_graph_path is None:
            knowledge_graph_path = (
                Path(__file__).parent.parent.parent /
                "knowledge_graph" / "sap_knowledge_graph.json"
            )

        self.graph = self._load_graph(knowledge_graph_path)
        # We keep nodes/edges/rules for context lookup, but NOT for method selection
        self.nodes = {n['node_id']: n for n in self.graph.get('nodes', [])}
        self.edges = self.graph.get('edges', [])
        self.rules = self.graph.get('rules', [])

        # Index rules by condition type for quick context lookup
        self._condition_rules: Dict[str, List[Dict]] = {}
        for rule in self.rules:
            if rule.get('rule_type') == 'condition_method':
                cond_type = rule.get('condition', {}).get('type', '')
                if cond_type:
                    if cond_type not in self._condition_rules:
                        self._condition_rules[cond_type] = []
                    self._condition_rules[cond_type].append(rule)

    def _load_graph(self, path: Path) -> Dict[str, Any]:
        """Load knowledge graph from JSON."""
        if not path.exists():
            print(f"[KnowledgeRuleEngine] Warning: No graph at {path}")
            return {'nodes': [], 'edges': [], 'rules': []}

        try:
            graph = json.loads(path.read_text())
            stats = graph.get('stats', {})
            print(f"[KnowledgeRuleEngine] Loaded graph: {stats.get('total_nodes', 0)} nodes, "
                  f"{stats.get('total_edges', 0)} edges, {stats.get('total_rules', 0)} rules")
            return graph
        except Exception as e:
            print(f"[KnowledgeRuleEngine] Error loading graph: {e}")
            return {'nodes': [], 'edges': [], 'rules': []}

    def get_methods_for_condition(self, condition_type: str) -> List[Dict[str, Any]]:
        """
        Get methods commonly associated with a condition (for CONTEXT only).

        This returns what methods are documented in literature/trials for this condition,
        NOT a recommendation. The protocol-specified method is always the source of truth.

        Args:
            condition_type: e.g., 'immunotherapy', 'interim_analysis', 'stratified'

        Returns:
            List of method info dicts with: method, confidence, sources
        """
        rules = self._condition_rules.get(condition_type, [])
        methods = []
        for rule in rules:
            method = rule.get('conclusion', {}).get('method', '')
            if method:
                methods.append({
                    'method': method.replace('_', ' ').title(),
                    'confidence': rule.get('confidence', 0),
                    'sources': rule.get('sources', []),
                    'note': 'Common in literature - NOT a recommendation'
                })
        # Sort by confidence descending
        methods.sort(key=lambda x: x['confidence'], reverse=True)
        return methods

    def detect_conditions(self, protocol_facts: Dict[str, Any]) -> Set[str]:
        """
        Detect which conditions are present in the protocol.

        NOTE: This is for CONTEXT only, not method selection.

        Args:
            protocol_facts: Dictionary of extracted protocol facts

        Returns:
            Set of condition types that are present
        """
        conditions = set()

        # Check for time-to-event endpoints
        endpoint = str(protocol_facts.get('primary_endpoint', '')).lower()
        endpoint_type = str(protocol_facts.get('endpoint_type', '')).lower()

        if any(term in endpoint or term in endpoint_type for term in
               ['survival', 'pfs', 'os', 'dfs', 'rfs', 'time', 'event']):
            conditions.add('time_to_event')

        # Check for immunotherapy (for context, NOT method selection)
        drug = str(protocol_facts.get('drug_name', '')).lower()
        therapeutic = str(protocol_facts.get('therapeutic_area', '')).lower()

        io_keywords = [
            'immunotherapy', 'checkpoint', 'pd-1', 'pd-l1', 'ctla-4',
            'pembrolizumab', 'nivolumab', 'atezolizumab', 'durvalumab',
            'ipilimumab', 'tislelizumab', 'sintilimab', 'camrelizumab'
        ]

        if any(kw in drug or kw in therapeutic for kw in io_keywords):
            conditions.add('immunotherapy')

        # Check for interim analysis
        if protocol_facts.get('has_interim_analysis'):
            conditions.add('interim_analysis')

        # Check for stratified randomization
        if protocol_facts.get('stratification_factors'):
            conditions.add('stratified')

        # Check for randomization
        if protocol_facts.get('is_randomized'):
            conditions.add('randomized')

        # Check for crossover / treatment switching
        if protocol_facts.get('crossover_permitted') or protocol_facts.get('has_crossover'):
            conditions.add('crossover')
            conditions.add('treatment_switching')

        # Check phase
        phase = str(protocol_facts.get('phase', ''))
        if '3' in phase or 'III' in phase:
            conditions.add('phase3')

        # Check treatment setting
        setting = str(protocol_facts.get('treatment_setting', '')).lower()
        if 'neoadjuvant' in setting:
            conditions.add('neoadjuvant')
        elif 'adjuvant' in setting:
            conditions.add('adjuvant')

        return conditions

    def get_method_context(
        self,
        protocol_facts: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Return CONTEXT about the protocol conditions,
        not METHOD DECISIONS. The extracted protocol method is the source of truth.

        Uses the 99 rules from knowledge graph to provide background on what methods
        are commonly documented in literature for each condition.

        Args:
            protocol_facts: Extracted protocol facts

        Returns:
            Dictionary with:
            - conditions_detected: What conditions were found
            - considerations: Scientific context for each condition
            - protocol_method: What the protocol actually specifies (SOURCE OF TRUTH)
            - common_methods_by_condition: What literature documents (NOT recommendations)
            - discrepancy_notes: Flags if protocol differs from typical approaches
        """
        conditions = self.detect_conditions(protocol_facts)
        protocol_method = (
            protocol_facts.get('statistical_method', '') or
            protocol_facts.get('statistical_method_details', '')
        )

        context = {
            'conditions_detected': list(conditions),
            'protocol_method': protocol_method,
            'considerations': [],
            'discrepancy_notes': [],
            'scientific_context': {},
            'common_methods_by_condition': {},  # From 99 rules - for CONTEXT only
            'total_rules_available': len(self.rules)
        }

        # Get methods from 99 rules for each detected condition (CONTEXT only)
        for condition in conditions:
            rule_methods = self.get_methods_for_condition(condition)
            if rule_methods:
                context['common_methods_by_condition'][condition] = rule_methods

        # Immunotherapy context (INFORM, don't decide)
        if 'immunotherapy' in conditions:
            context['considerations'].append({
                'condition': 'immunotherapy',
                'note': (
                    'Immunotherapy trials often show delayed treatment effects due to '
                    'the indirect mechanism of action (immune activation → proliferation → tumor impact). '
                    'This can cause delayed separation of survival curves.'
                ),
                'implication': (
                    'Weighted log-rank tests (e.g., Fleming-Harrington) may provide better power '
                    'than standard log-rank when delayed effects are expected.'
                ),
                'but': (
                    'Standard log-rank remains statistically valid under non-proportional hazards. '
                    'Protocol authors may choose log-rank for regulatory familiarity.'
                ),
                'sources': ['ICH E9 R1', 'PMC9196085']
            })
            context['scientific_context']['immunotherapy'] = {
                'delayed_effect_expected': True,
                'nph_likely': True,
                'note': 'Method choice depends on expected separation pattern - USE PROTOCOL METHOD'
            }

        # Time-to-event context
        if 'time_to_event' in conditions:
            context['considerations'].append({
                'condition': 'time_to_event',
                'note': 'Time-to-event endpoints (PFS, OS, DFS) typically use log-rank tests.',
                'common_methods': ['stratified log-rank', 'unstratified log-rank', 'Cox PH'],
                'sources': ['ICH E9', 'FDA Oncology Guidance']
            })

        # Interim analysis context
        if 'interim_analysis' in conditions:
            context['considerations'].append({
                'condition': 'interim_analysis',
                'note': (
                    'Interim analyses require alpha spending to control overall Type I error. '
                    'Lan-DeMets with O\'Brien-Fleming boundaries is most common.'
                ),
                'common_methods': ['Lan-DeMets', 'O\'Brien-Fleming', 'Pocock'],
                'sources': ['FDA Adaptive Design Guidance', 'ICH E9']
            })

        # Stratification context
        if 'stratified' in conditions:
            context['considerations'].append({
                'condition': 'stratified',
                'note': (
                    'Stratified randomization should be reflected in the analysis. '
                    'Use stratified log-rank and stratified Cox models.'
                ),
                'sources': ['ICH E9', 'EMA Guideline on Adjustment for Baseline Covariates']
            })

        # Treatment switching context
        if 'treatment_switching' in conditions or 'crossover' in conditions:
            context['considerations'].append({
                'condition': 'treatment_switching',
                'note': (
                    'Treatment switching/crossover can bias OS estimates. '
                    'Consider sensitivity analyses adjusting for crossover.'
                ),
                'common_methods': ['RPSFT', 'IPCW', 'Two-stage'],
                'sources': ['NICE TSD16', 'FDA Guidance on Complex Innovative Designs']
            })

        # Neoadjuvant context
        if 'neoadjuvant' in conditions:
            context['considerations'].append({
                'condition': 'neoadjuvant',
                'note': (
                    'Neoadjuvant setting: treatment before surgery. '
                    'Primary endpoint often pathologic complete response (pCR) or event-free survival (EFS). '
                    'Time origin may be from surgery rather than randomization.'
                ),
                'sources': ['FDA Guidance on Neoadjuvant Treatment']
            })

        # Check for discrepancies
        context['discrepancy_notes'] = self._check_discrepancies(
            protocol_method, conditions, protocol_facts
        )

        return context

    def _check_discrepancies(
        self,
        protocol_method: str,
        conditions: Set[str],
        protocol_facts: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Flag discrepancies between protocol-specified method and typical approaches.
        These are INFO NOTES, not ERRORS - the protocol is the source of truth.
        """
        notes = []

        # No method specified at all
        if not protocol_method:
            notes.append({
                'type': 'extraction_gap',
                'observation': 'Statistical method was not extracted from the protocol.',
                'action': (
                    'Review protocol to identify the primary statistical test. '
                    'Do NOT infer based on drug class or conditions.'
                ),
                'severity': 'warning'
            })

        # Interim analysis without alpha spending mentioned
        if 'interim_analysis' in conditions:
            has_interim = protocol_facts.get('has_interim_analysis', False)
            interim_method = protocol_facts.get('interim_analysis_method', '')

            if has_interim and not interim_method:
                notes.append({
                    'type': 'missing_detail',
                    'observation': 'Protocol has interim analysis but alpha spending method not extracted.',
                    'action': 'Verify alpha spending method is specified in protocol.',
                    'severity': 'warning'
                })

        return notes

    def get_context_for_generation(
        self,
        protocol_facts: Dict[str, Any]
    ) -> str:
        """
        Generate a context string for LLM during SAP generation.
        Provides scientific background WITHOUT making method decisions.

        Leverages the 99 rules from knowledge graph to show what methods
        are documented in literature (for CONTEXT, not recommendation).

        Args:
            protocol_facts: Extracted protocol facts

        Returns:
            Formatted context string for LLM prompt
        """
        ctx = self.get_method_context(protocol_facts)

        lines = [
            "## Scientific Context (Informational - Protocol is Source of Truth)",
            f"(Based on {ctx.get('total_rules_available', 0)} evidence-based rules from knowledge graph)",
            ""
        ]

        # Protocol method (source of truth) - EMPHASIZED
        lines.append("=" * 60)
        if ctx['protocol_method']:
            lines.append(f"**PROTOCOL-SPECIFIED METHOD:** {ctx['protocol_method']}")
            lines.append(">>> THIS IS THE SOURCE OF TRUTH - USE THIS METHOD IN THE SAP <<<")
        else:
            lines.append("**PROTOCOL-SPECIFIED METHOD:** [NOT EXTRACTED - NEEDS REVIEW]")
            lines.append(">>> DO NOT INFER A METHOD - FLAG FOR HUMAN REVIEW <<<")
        lines.append("=" * 60)
        lines.append("")

        # Conditions detected
        lines.append(f"**Conditions Detected:** {', '.join(ctx['conditions_detected'])}")
        lines.append("")

        # Methods from 99 rules (CONTEXT only, not recommendations)
        if ctx.get('common_methods_by_condition'):
            lines.append("### Literature Context (NOT Recommendations)")
            lines.append("The following methods are documented in literature for these conditions.")
            lines.append("This is BACKGROUND INFORMATION - the protocol method takes precedence.")
            lines.append("")
            for condition, methods in ctx['common_methods_by_condition'].items():
                cond_label = condition.replace('_', ' ').title()
                lines.append(f"**{cond_label}:**")
                # Show top 3 methods with highest confidence
                for m in methods[:3]:
                    sources_str = ', '.join(m['sources'][:2]) if m['sources'] else 'domain knowledge'
                    lines.append(f"  - {m['method']} (conf: {m['confidence']:.1f}, sources: {sources_str})")
            lines.append("")

        # Considerations
        if ctx['considerations']:
            lines.append("### Background Considerations")
            for c in ctx['considerations']:
                lines.append(f"\n**{c['condition'].replace('_', ' ').title()}:**")
                lines.append(f"- {c['note']}")
                if c.get('implication'):
                    lines.append(f"- Implication: {c['implication']}")
                if c.get('but'):
                    lines.append(f"- Note: {c['but']}")

        # Discrepancy notes
        if ctx['discrepancy_notes']:
            lines.append("\n### Notes")
            for note in ctx['discrepancy_notes']:
                lines.append(f"- [{note['severity'].upper()}] {note['observation']}")
                lines.append(f"  Action: {note['action']}")

        return '\n'.join(lines)


def test_rule_engine():
    """Test the refactored rule engine."""
    print("=" * 70)
    print("Testing Knowledge Rule Engine (Context-Only Mode)")
    print("=" * 70)

    engine = KnowledgeRuleEngine()

    # Test case: IO trial with PFS endpoint
    facts = {
        'primary_endpoint': 'Progression-Free Survival (PFS)',
        'drug_name': 'pembrolizumab',
        'statistical_method': 'stratified log-rank test',  # Protocol specifies this
        'has_interim_analysis': True,
        'stratification_factors': ['PD-L1 status', 'ECOG PS'],
        'is_randomized': True,
    }

    print("\nTest: Immunotherapy trial with PFS endpoint")
    print("-" * 50)

    conditions = engine.detect_conditions(facts)
    print(f"Detected conditions: {conditions}")

    context = engine.get_method_context(facts)
    print(f"\nProtocol method (source of truth): {context['protocol_method']}")
    print(f"Discrepancy notes: {len(context['discrepancy_notes'])}")

    print("\n" + engine.get_context_for_generation(facts))


if __name__ == "__main__":
    test_rule_engine()
