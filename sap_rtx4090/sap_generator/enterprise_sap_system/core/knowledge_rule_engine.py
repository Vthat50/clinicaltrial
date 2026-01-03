#!/usr/bin/env python3
"""
Knowledge Graph Rule Engine for SAP Generation
===============================================

Uses extracted knowledge rules to make decisions about:
- Which statistical methods to use
- Which analyses to include
- How to handle special cases (NPH, multiplicity, interim)

This replaces/augments hardcoded decision trees with data-driven rules.
"""

import json
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Set
from collections import defaultdict


@dataclass
class RuleMatch:
    """Result of a rule match."""
    rule_id: str
    method: str
    confidence: float
    reason: str
    sources: List[str]


class KnowledgeRuleEngine:
    """
    Applies knowledge graph rules to protocol facts to recommend
    statistical methods and analyses.
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
        self.rules = self.graph.get('rules', [])
        self.nodes = {n['node_id']: n for n in self.graph.get('nodes', [])}
        self.edges = self.graph.get('edges', [])

        # Index rules by condition type for fast lookup
        self.rules_by_condition: Dict[str, List[Dict]] = defaultdict(list)
        for rule in self.rules:
            condition_type = rule.get('condition', {}).get('type', '')
            if condition_type:
                self.rules_by_condition[condition_type].append(rule)

    def _load_graph(self, path: Path) -> Dict[str, Any]:
        """Load knowledge graph from JSON."""
        if not path.exists():
            print(f"[KnowledgeRuleEngine] Warning: No graph at {path}")
            return {'rules': [], 'nodes': [], 'edges': []}

        try:
            return json.loads(path.read_text())
        except Exception as e:
            print(f"[KnowledgeRuleEngine] Error loading graph: {e}")
            return {'rules': [], 'nodes': [], 'edges': []}

    def detect_conditions(self, protocol_facts: Dict[str, Any]) -> Set[str]:
        """
        Detect which conditions are present in the protocol.

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

        # Check for immunotherapy
        drug = str(protocol_facts.get('drug_name', '')).lower()
        therapeutic = str(protocol_facts.get('therapeutic_area', '')).lower()
        protocol_text = str(protocol_facts.get('raw_text', '')).lower()

        io_keywords = [
            'immunotherapy', 'checkpoint', 'pd-1', 'pd-l1', 'ctla-4',
            'pembrolizumab', 'nivolumab', 'atezolizumab', 'durvalumab',
            'ipilimumab', 'tislelizumab', 'sintilimab', 'camrelizumab'
        ]

        if any(kw in drug or kw in therapeutic or kw in protocol_text
               for kw in io_keywords):
            conditions.add('immunotherapy')

        # Check for interim analysis (multiple flag names)
        if protocol_facts.get('has_interim_analysis') or protocol_facts.get('interim_analysis'):
            conditions.add('interim_analysis')
        if 'interim' in protocol_text:
            conditions.add('interim_analysis')

        # Check for multiple endpoints
        if protocol_facts.get('has_hierarchical_testing'):
            conditions.add('multiple_endpoints')
        if protocol_facts.get('secondary_endpoints'):
            if len(protocol_facts.get('secondary_endpoints', [])) > 0:
                conditions.add('multiple_endpoints')

        # Check for stratified randomization
        if protocol_facts.get('stratification_factors'):
            conditions.add('stratified')
        if 'stratif' in protocol_text:
            conditions.add('stratified')

        # Check for randomization
        design = str(protocol_facts.get('design_type', '')).lower()
        if 'random' in design or protocol_facts.get('is_randomized'):
            conditions.add('randomized')

        # Check for non-proportional hazards expectation
        if 'delayed' in protocol_text or 'non-proportional' in protocol_text:
            conditions.add('non_proportional_hazards')
        if any(term in protocol_text for term in ['nph', 'crossing curves', 'late separation']):
            conditions.add('non_proportional_hazards')

        # Check for delayed effect (more specific than NPH)
        if any(term in protocol_text for term in
               ['delayed effect', 'late onset', 'delayed treatment effect']):
            conditions.add('delayed_effect')
        # Immunotherapy trials typically have delayed effects
        if 'immunotherapy' in conditions:
            conditions.add('delayed_effect')

        # Check for crossover / treatment switching
        # Check boolean flags first
        if protocol_facts.get('crossover_permitted') or protocol_facts.get('has_crossover'):
            conditions.add('crossover')
            conditions.add('treatment_switching')
        # Then check text mentions
        if any(term in protocol_text for term in
               ['crossover', 'cross-over', 'treatment switch', 'switched to']):
            conditions.add('crossover')
            conditions.add('treatment_switching')
        if 'subsequent therapy' in protocol_text or 'post-progression' in protocol_text:
            conditions.add('treatment_switching')

        # Check phase
        phase = str(protocol_facts.get('phase', ''))
        if '3' in phase or 'III' in phase:
            conditions.add('phase3')

        return conditions

    def get_recommended_methods(
        self,
        protocol_facts: Dict[str, Any],
        min_confidence: float = 0.3
    ) -> List[RuleMatch]:
        """
        Get recommended statistical methods based on protocol facts.

        Args:
            protocol_facts: Extracted protocol facts
            min_confidence: Minimum confidence threshold

        Returns:
            List of RuleMatch objects sorted by confidence
        """
        conditions = self.detect_conditions(protocol_facts)
        matches: List[RuleMatch] = []

        print(f"[KnowledgeRuleEngine] Detected conditions: {conditions}")

        # Find matching rules
        for condition in conditions:
            for rule in self.rules_by_condition.get(condition, []):
                confidence = rule.get('confidence', 0)

                if confidence < min_confidence:
                    continue

                method = rule.get('conclusion', {}).get('method', '')
                if not method:
                    continue

                # Build reason string
                rule_type = rule.get('rule_type', 'unknown')
                sources = rule.get('sources', [])

                if rule_type == 'domain_expert':
                    reason = f"Domain expert rule: IF {condition} THEN use {method}"
                else:
                    reason = (
                        f"Data-driven rule: {condition} -> {method} "
                        f"(seen in {len(sources)} SAPs: {', '.join(sources[:3])})"
                    )

                matches.append(RuleMatch(
                    rule_id=rule.get('rule_id', ''),
                    method=method,
                    confidence=confidence,
                    reason=reason,
                    sources=sources
                ))

        # Sort by confidence (highest first)
        matches.sort(key=lambda m: m.confidence, reverse=True)

        return matches

    def get_primary_analysis_methods(
        self,
        protocol_facts: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get recommended primary analysis methods with full specifications.

        Returns a structured recommendation for the methods section.
        """
        matches = self.get_recommended_methods(protocol_facts)
        conditions = self.detect_conditions(protocol_facts)

        # Group methods by type
        survival_methods = []
        multiplicity_methods = []
        interim_methods = []
        treatment_switching_methods = []
        nph_methods = []

        for match in matches:
            method = match.method

            if method in ['stratified_logrank', 'unstratified_logrank',
                          'cox_ph', 'kaplan_meier']:
                survival_methods.append(match)

            elif method in ['fleming_harrington', 'rmst', 'landmark_analysis',
                            'piecewise_cox', 'maxcombo', 'weighted_logrank']:
                nph_methods.append(match)

            elif method in ['hierarchical_testing', 'hochberg', 'bonferroni']:
                multiplicity_methods.append(match)

            elif method in ['lan_demets', 'obrien_fleming']:
                interim_methods.append(match)

            elif method in ['rpsft', 'ipcw', 'iptw', 'two_stage']:
                treatment_switching_methods.append(match)

        # Build recommendations
        recommendations = {
            'conditions_detected': list(conditions),
            'primary_test': None,
            'sensitivity_analyses': [],
            'supportive_analyses': [],
            'multiplicity_adjustment': None,
            'interim_analysis_method': None,
            'treatment_switching_methods': [],
            'nph_methods': [],
            'delayed_effect_rationale': None,
            'reasoning': []
        }

        # Primary test selection
        # =================================================================
        # CRITICAL: Check for PROTOCOL-EXTRACTED method FIRST
        # =================================================================
        protocol_method = protocol_facts.get('statistical_method', '') or \
                         protocol_facts.get('statistical_method_details', '')

        if protocol_method:
            # USE WHAT THE PROTOCOL SAYS - don't infer!
            print(f"[KnowledgeRuleEngine] Using PROTOCOL-SPECIFIED method: {protocol_method}")
            recommendations['primary_test'] = {
                'method': 'protocol_specified',
                'description': protocol_method,
                'reason': f'Method extracted from protocol: {protocol_method}'
            }
            # Don't override with inference
        elif 'time_to_event' in conditions:
            # FALLBACK: Use stratified log-rank as default (most common standard method)
            # DO NOT assume Fleming-Harrington for immunotherapy - protocol must specify it
            if 'stratified' in conditions:
                recommendations['primary_test'] = {
                    'method': 'stratified_logrank',
                    'description': 'Stratified log-rank test',
                    'reason': 'Time-to-event endpoint with stratified randomization'
                }
            else:
                recommendations['primary_test'] = {
                    'method': 'logrank',
                    'description': 'Log-rank test',
                    'reason': 'Time-to-event endpoint'
                }

            # Always add Kaplan-Meier for TTE
            recommendations['supportive_analyses'].append({
                'method': 'kaplan_meier',
                'description': 'Kaplan-Meier survival curves and median estimates'
            })

            # Add Cox for HR estimation
            recommendations['supportive_analyses'].append({
                'method': 'cox_ph',
                'description': 'Cox proportional hazards model for hazard ratio estimation'
            })

        # NPH-specific methods for immunotherapy
        if 'immunotherapy' in conditions and 'time_to_event' in conditions:
            # Note: Fleming-Harrington is now PRIMARY, so don't add as sensitivity
            # Only add RMST and landmark as additional sensitivity analyses
            recommendations['sensitivity_analyses'].extend([
                {
                    'method': 'rmst',
                    'description': 'Restricted Mean Survival Time difference',
                    'reason': 'Robust to non-proportional hazards'
                },
                {
                    'method': 'landmark_analysis',
                    'description': 'Milestone survival at 12, 18, 24 months',
                    'reason': 'Captures late separation of curves'
                }
            ])

            recommendations['reasoning'].append(
                "Immunotherapy trial with time-to-event endpoint: "
                "Fleming-Harrington as primary test, with RMST and landmarks as sensitivity"
            )

        # Multiplicity adjustment
        if multiplicity_methods:
            top = multiplicity_methods[0]
            recommendations['multiplicity_adjustment'] = {
                'method': top.method,
                'confidence': top.confidence,
                'reason': top.reason
            }

        # Interim analysis
        if interim_methods:
            top = interim_methods[0]
            recommendations['interim_analysis_method'] = {
                'method': top.method,
                'confidence': top.confidence,
                'reason': top.reason
            }

            # Add O'Brien-Fleming if Lan-DeMets present
            if 'interim_analysis' in conditions:
                recommendations['reasoning'].append(
                    "Interim analysis planned: Using Lan-DeMets alpha spending "
                    "with O'Brien-Fleming boundaries"
                )

        # Treatment switching / crossover adjustments
        if 'crossover' in conditions or 'treatment_switching' in conditions:
            recommendations['treatment_switching_methods'] = [
                {
                    'method': 'rpsft',
                    'description': 'Rank Preserving Structural Failure Time (RPSFT)',
                    'reason': 'NICE TSD16 recommended for treatment switching adjustment'
                },
                {
                    'method': 'ipcw',
                    'description': 'Inverse Probability of Censoring Weighting (IPCW)',
                    'reason': 'Sensitivity analysis for crossover bias'
                }
            ]
            recommendations['reasoning'].append(
                "Treatment switching/crossover detected: Added RPSFT and IPCW analyses "
                "(per NICE TSD16 guidance)"
            )

        # NPH-specific methods from knowledge graph
        if nph_methods:
            recommendations['nph_methods'] = [
                {
                    'method': m.method,
                    'confidence': m.confidence,
                    'reason': m.reason
                }
                for m in nph_methods[:5]  # Top 5
            ]

        # Delayed effect rationale (documentation requirement)
        if 'immunotherapy' in conditions or 'delayed_effect' in conditions:
            recommendations['delayed_effect_rationale'] = {
                'required': True,
                'reason': 'ICH E9(R1) requires pre-specification of delayed effect assumption',
                'suggested_text': (
                    "Due to the immunotherapy mechanism of action, a delayed treatment "
                    "effect is anticipated. The primary analysis using log-rank test "
                    "will be supplemented with analyses robust to non-proportional hazards."
                )
            }
            recommendations['reasoning'].append(
                "Delayed effect expected: Added delayed_effect_rationale documentation requirement"
            )

        return recommendations

    def format_methods_section(
        self,
        protocol_facts: Dict[str, Any]
    ) -> str:
        """
        Generate formatted methods section text based on rules.

        Args:
            protocol_facts: Extracted protocol facts

        Returns:
            Formatted markdown text for methods section
        """
        rec = self.get_primary_analysis_methods(protocol_facts)

        lines = ["## Statistical Methods\n"]
        lines.append("### Primary Analysis\n")

        if rec['primary_test']:
            pt = rec['primary_test']
            lines.append(f"The primary efficacy analysis will use the **{pt['description']}**.")
            lines.append(f"Rationale: {pt['reason']}\n")

        # Supportive analyses
        if rec['supportive_analyses']:
            lines.append("\n### Supportive Analyses\n")
            for i, sa in enumerate(rec['supportive_analyses'], 1):
                lines.append(f"{i}. **{sa['description']}**")

        # Sensitivity analyses
        if rec['sensitivity_analyses']:
            lines.append("\n### Sensitivity Analyses\n")
            for i, sa in enumerate(rec['sensitivity_analyses'], 1):
                lines.append(f"{i}. **{sa['description']}**")
                if sa.get('reason'):
                    lines.append(f"   - {sa['reason']}")

        # Multiplicity
        if rec['multiplicity_adjustment']:
            ma = rec['multiplicity_adjustment']
            lines.append("\n### Multiplicity Adjustment\n")
            lines.append(f"**{ma['method'].replace('_', ' ').title()}** will be used.")
            lines.append(f"Confidence: {ma['confidence']:.0%}")

        # Interim
        if rec['interim_analysis_method']:
            ia = rec['interim_analysis_method']
            lines.append("\n### Interim Analysis\n")
            lines.append(f"Alpha spending will use **{ia['method'].replace('_', ' ').title()}**.")

        # Reasoning
        if rec['reasoning']:
            lines.append("\n### Method Selection Rationale\n")
            for r in rec['reasoning']:
                lines.append(f"- {r}")

        return '\n'.join(lines)


    # ==========================================================================
    # NEW ARCHITECTURE: Rules provide CONTEXT, not DECISIONS
    # ==========================================================================

    def get_method_context(
        self,
        protocol_facts: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        NEW ARCHITECTURE: Return CONTEXT about the protocol conditions,
        not METHOD DECISIONS. The extracted protocol method is the source of truth.

        Args:
            protocol_facts: Extracted protocol facts

        Returns:
            Dictionary with:
            - conditions_detected: What conditions were found
            - considerations: Scientific context for each condition
            - protocol_method: What the protocol actually specifies (SOURCE OF TRUTH)
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
            'scientific_context': {}
        }

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
                    'Standard log-rank remains statistically valid under non-proportional hazards, '
                    'though it may have reduced power. Protocol authors may choose log-rank for '
                    'regulatory familiarity or if early separation is expected.'
                ),
                'sources': ['ICH E9 R1', 'PMC9196085', 'arXiv:2007.04767']
            })
            context['scientific_context']['immunotherapy'] = {
                'delayed_effect_expected': True,
                'nph_likely': True,
                'common_methods': ['Fleming-Harrington', 'stratified log-rank', 'RMST'],
                'note': 'Method choice depends on expected separation pattern'
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

        # Check for discrepancies between protocol method and typical approaches
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
        These are NOTES, not ERRORS - the protocol is the source of truth.

        Returns:
            List of discrepancy notes (informational, not corrective)
        """
        notes = []
        protocol_method_lower = protocol_method.lower()

        # Immunotherapy + log-rank (not Fleming-Harrington)
        if 'immunotherapy' in conditions:
            if protocol_method and 'fleming' not in protocol_method_lower and 'weighted' not in protocol_method_lower:
                if 'log-rank' in protocol_method_lower or 'logrank' in protocol_method_lower:
                    notes.append({
                        'type': 'method_choice_note',
                        'observation': (
                            f'Protocol specifies "{protocol_method}" for an immunotherapy trial. '
                            'Immunotherapy trials often show delayed effects where weighted log-rank '
                            '(Fleming-Harrington) may provide better power.'
                        ),
                        'protocol_rationale': (
                            'The protocol authors may have chosen standard log-rank for: '
                            '(1) regulatory familiarity, (2) expected early separation, '
                            '(3) conservative approach, or (4) pre-specified in the protocol.'
                        ),
                        'action': 'PROCEED with protocol-specified method. This is informational only.',
                        'severity': 'info'
                    })

        # Interim analysis without alpha spending mentioned
        if 'interim_analysis' in conditions:
            has_interim = protocol_facts.get('has_interim_analysis', False)
            num_interim = protocol_facts.get('num_interim_analyses', 0)
            interim_method = protocol_facts.get('interim_analysis_method', '')

            if has_interim and not interim_method:
                notes.append({
                    'type': 'missing_detail',
                    'observation': (
                        f'Protocol has {num_interim} interim analyses but alpha spending method '
                        'was not extracted.'
                    ),
                    'action': 'Verify alpha spending method is specified in protocol.',
                    'severity': 'warning'
                })

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

        return notes

    def get_context_for_generation(
        self,
        protocol_facts: Dict[str, Any]
    ) -> str:
        """
        Generate a context string that can be passed to the LLM during SAP generation.
        This provides scientific background WITHOUT making method decisions.

        Args:
            protocol_facts: Extracted protocol facts

        Returns:
            Formatted context string for LLM prompt
        """
        ctx = self.get_method_context(protocol_facts)

        lines = [
            "## Scientific Context (Informational - Protocol is Source of Truth)",
            ""
        ]

        # Protocol method (source of truth)
        if ctx['protocol_method']:
            lines.append(f"**Protocol-Specified Method:** {ctx['protocol_method']}")
            lines.append("(This is the source of truth - use this method in the SAP)")
            lines.append("")
        else:
            lines.append("**Protocol-Specified Method:** [NOT EXTRACTED - NEEDS REVIEW]")
            lines.append("")

        # Conditions detected
        lines.append(f"**Conditions Detected:** {', '.join(ctx['conditions_detected'])}")
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
    """Test the rule engine with sample protocol facts."""

    print("=" * 70)
    print("Testing Knowledge Rule Engine")
    print("=" * 70)

    engine = KnowledgeRuleEngine()

    # Test case 1: IO trial with PFS endpoint
    print("\n" + "-" * 50)
    print("Test 1: Immunotherapy trial with PFS endpoint")
    print("-" * 50)

    facts1 = {
        'primary_endpoint': 'Progression-Free Survival (PFS)',
        'endpoint_type': 'time_to_event',
        'drug_name': 'pembrolizumab',
        'therapeutic_area': 'oncology',
        'has_interim_analysis': True,
        'stratification_factors': ['PD-L1 status', 'ECOG PS'],
        'design_type': 'randomized, double-blind',
        'is_randomized': True,
    }

    conditions = engine.detect_conditions(facts1)
    print(f"Detected conditions: {conditions}")

    matches = engine.get_recommended_methods(facts1)
    print(f"\nRecommended methods ({len(matches)} matches):")
    for m in matches[:10]:
        print(f"  - {m.method}: {m.confidence:.0%} ({m.reason[:50]}...)")

    print("\nFormatted methods section:")
    print(engine.format_methods_section(facts1))

    # Test case 2: Chemotherapy trial without interim
    print("\n" + "-" * 50)
    print("Test 2: Chemotherapy trial, no interim")
    print("-" * 50)

    facts2 = {
        'primary_endpoint': 'Overall Response Rate (ORR)',
        'endpoint_type': 'binary',
        'drug_name': 'docetaxel',
        'therapeutic_area': 'oncology',
        'has_interim_analysis': False,
        'design_type': 'randomized',
        'is_randomized': True,
    }

    conditions = engine.detect_conditions(facts2)
    print(f"Detected conditions: {conditions}")

    matches = engine.get_recommended_methods(facts2)
    print(f"\nRecommended methods ({len(matches)} matches):")
    for m in matches[:5]:
        print(f"  - {m.method}: {m.confidence:.0%}")


if __name__ == "__main__":
    test_rule_engine()
