#!/usr/bin/env python3
"""
RAG Agents for SAP Generation
=============================
Specialized agents that use retrieved SAP examples to improve generation.

Architecture:
- SAPRetriever: Core retrieval from vector store
- EndpointExtractionAgent: Extracts endpoints using similar trials
- MethodSelectionAgent: Selects statistical methods from examples
- StratificationParserAgent: Parses stratification factors
- RAGOrchestrator: Coordinates all agents
"""

import os
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .vector_store import SAPVectorStore, RetrievalResult, create_vector_store


@dataclass
class RAGContext:
    """Context from RAG retrieval for generation"""
    query: str
    retrieved_examples: List[RetrievalResult]
    therapeutic_area: Optional[str] = None
    endpoint_type: Optional[str] = None
    phase: Optional[str] = None

    def to_prompt_context(self) -> str:
        """Format retrieved examples for prompt injection"""
        if not self.retrieved_examples:
            return ""

        context_parts = ["## Similar SAP Examples:\n"]
        for i, example in enumerate(self.retrieved_examples[:3], 1):
            context_parts.append(f"### Example {i} ({example.nct_id}):")
            context_parts.append(f"Relevance: {example.relevance_score:.2f}")
            # Truncate long content
            content = example.content[:1500] if len(example.content) > 1500 else example.content
            context_parts.append(content)
            context_parts.append("")

        return "\n".join(context_parts)


class SAPRetriever:
    """
    Core retrieval component for SAP RAG system.

    Handles:
    - Query formulation from protocol data
    - Multi-section retrieval
    - Relevance filtering
    """

    def __init__(self, vector_store: SAPVectorStore = None):
        self.vector_store = vector_store or create_vector_store()
        self.min_relevance_threshold = 0.3

    def retrieve_for_endpoints(
        self,
        protocol_data: Dict[str, Any],
        n_results: int = 5
    ) -> RAGContext:
        """
        Retrieve similar endpoint sections.

        Args:
            protocol_data: Parsed protocol information
            n_results: Number of results to retrieve

        Returns:
            RAGContext with retrieved examples
        """
        # Build query from protocol data
        query_parts = []

        # Add indication/condition
        if protocol_data.get('indication'):
            query_parts.append(protocol_data['indication'])
        if protocol_data.get('condition'):
            query_parts.append(protocol_data['condition'])

        # Add primary endpoint if available
        if protocol_data.get('primary_endpoint'):
            query_parts.append(f"primary endpoint: {protocol_data['primary_endpoint']}")

        # Add phase
        if protocol_data.get('phase'):
            query_parts.append(f"Phase {protocol_data['phase']}")

        query = " ".join(query_parts) if query_parts else "clinical trial endpoints"

        # Build filters
        filters = {}
        if protocol_data.get('therapeutic_area'):
            filters['therapeutic_area'] = protocol_data['therapeutic_area']

        # Retrieve
        results = self.vector_store.query(
            section_type="endpoints",
            query_text=query,
            n_results=n_results,
            filters=filters if filters else None
        )

        # Filter by relevance threshold
        filtered = [r for r in results if r.relevance_score >= self.min_relevance_threshold]

        return RAGContext(
            query=query,
            retrieved_examples=filtered,
            therapeutic_area=protocol_data.get('therapeutic_area'),
            endpoint_type=protocol_data.get('endpoint_type'),
            phase=protocol_data.get('phase')
        )

    def retrieve_for_methods(
        self,
        endpoint_info: Dict[str, Any],
        n_results: int = 5
    ) -> RAGContext:
        """
        Retrieve similar statistical methods sections.

        Args:
            endpoint_info: Information about the endpoint
            n_results: Number of results

        Returns:
            RAGContext with retrieved method examples
        """
        # Build query focusing on endpoint type and analysis
        query_parts = []

        if endpoint_info.get('endpoint_type'):
            query_parts.append(f"{endpoint_info['endpoint_type']} endpoint analysis")
        if endpoint_info.get('primary_endpoint'):
            query_parts.append(endpoint_info['primary_endpoint'])
        if endpoint_info.get('statistical_test'):
            query_parts.append(endpoint_info['statistical_test'])

        query = " ".join(query_parts) if query_parts else "statistical analysis methods"

        # Build filters
        filters = {}
        if endpoint_info.get('endpoint_type'):
            filters['endpoint_type'] = endpoint_info['endpoint_type']

        results = self.vector_store.query(
            section_type="methods",
            query_text=query,
            n_results=n_results,
            filters=filters if filters else None
        )

        filtered = [r for r in results if r.relevance_score >= self.min_relevance_threshold]

        return RAGContext(
            query=query,
            retrieved_examples=filtered,
            endpoint_type=endpoint_info.get('endpoint_type')
        )

    def retrieve_for_stratification(
        self,
        protocol_data: Dict[str, Any],
        n_results: int = 5
    ) -> RAGContext:
        """
        Retrieve similar stratification sections.
        """
        query_parts = []

        if protocol_data.get('indication'):
            query_parts.append(protocol_data['indication'])
        if protocol_data.get('randomization'):
            query_parts.append(f"randomization stratification")
        if protocol_data.get('stratification_factors'):
            query_parts.extend(protocol_data['stratification_factors'][:3])

        query = " ".join(query_parts) if query_parts else "stratification factors randomization"

        filters = {}
        if protocol_data.get('therapeutic_area'):
            filters['therapeutic_area'] = protocol_data['therapeutic_area']

        results = self.vector_store.query(
            section_type="stratification",
            query_text=query,
            n_results=n_results,
            filters=filters if filters else None
        )

        filtered = [r for r in results if r.relevance_score >= self.min_relevance_threshold]

        return RAGContext(
            query=query,
            retrieved_examples=filtered,
            therapeutic_area=protocol_data.get('therapeutic_area')
        )

    def retrieve_multi_section(
        self,
        protocol_data: Dict[str, Any],
        section_types: List[str] = None,
        n_results_per_section: int = 3
    ) -> Dict[str, RAGContext]:
        """
        Retrieve from multiple section types at once.

        Returns:
            Dictionary mapping section_type to RAGContext
        """
        if section_types is None:
            section_types = ["endpoints", "methods", "stratification"]

        results = {}

        for section_type in section_types:
            if section_type == "endpoints":
                results[section_type] = self.retrieve_for_endpoints(
                    protocol_data, n_results_per_section
                )
            elif section_type == "methods":
                results[section_type] = self.retrieve_for_methods(
                    protocol_data, n_results_per_section
                )
            elif section_type == "stratification":
                results[section_type] = self.retrieve_for_stratification(
                    protocol_data, n_results_per_section
                )
            else:
                # Generic retrieval for other sections
                query = protocol_data.get('indication', '') + " " + section_type
                raw_results = self.vector_store.query(
                    section_type=section_type,
                    query_text=query,
                    n_results=n_results_per_section
                )
                results[section_type] = RAGContext(
                    query=query,
                    retrieved_examples=[r for r in raw_results if r.relevance_score >= self.min_relevance_threshold]
                )

        return results


class EndpointExtractionAgent:
    """
    Agent that extracts endpoints using retrieved SAP examples.

    Uses RAG to:
    1. Find similar trials with well-defined endpoints
    2. Learn endpoint structure patterns
    3. Extract and classify endpoints from protocol
    """

    def __init__(self, retriever: SAPRetriever = None):
        self.retriever = retriever or SAPRetriever()

    def extract_endpoints(
        self,
        protocol_text: str,
        protocol_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract endpoints using RAG-enhanced processing.

        Args:
            protocol_text: Raw protocol text
            protocol_data: Parsed protocol metadata

        Returns:
            Dictionary with extracted endpoints
        """
        # Get similar endpoint sections
        rag_context = self.retriever.retrieve_for_endpoints(protocol_data)

        # Extract patterns from retrieved examples
        patterns = self._extract_patterns_from_examples(rag_context.retrieved_examples)

        # Apply patterns to extract endpoints
        endpoints = self._extract_with_patterns(protocol_text, patterns)

        # Classify endpoint types based on examples
        for endpoint in endpoints.get('primary', []):
            endpoint['type'] = self._classify_endpoint_type(
                endpoint['description'],
                rag_context.retrieved_examples
            )

        return {
            'primary_endpoints': endpoints.get('primary', []),
            'secondary_endpoints': endpoints.get('secondary', []),
            'exploratory_endpoints': endpoints.get('exploratory', []),
            'rag_context': {
                'query': rag_context.query,
                'num_examples': len(rag_context.retrieved_examples),
                'example_nct_ids': [r.nct_id for r in rag_context.retrieved_examples[:3]]
            }
        }

    def _extract_patterns_from_examples(
        self,
        examples: List[RetrievalResult]
    ) -> Dict[str, List[str]]:
        """Extract endpoint patterns from retrieved examples"""
        patterns = {
            'primary_patterns': [],
            'analysis_patterns': [],
            'timepoint_patterns': []
        }

        for example in examples:
            content = example.content

            # Extract primary endpoint patterns
            primary_matches = re.findall(
                r'primary\s+(?:endpoint|outcome|efficacy)[:\s]+([^.]+\.)',
                content, re.IGNORECASE
            )
            patterns['primary_patterns'].extend(primary_matches[:2])

            # Extract analysis patterns
            analysis_matches = re.findall(
                r'(?:analyzed?\s+using|analysis\s+(?:will|shall)\s+(?:be|use))[:\s]+([^.]+\.)',
                content, re.IGNORECASE
            )
            patterns['analysis_patterns'].extend(analysis_matches[:2])

            # Extract timepoint patterns
            timepoint_matches = re.findall(
                r'(?:at\s+)?(?:week|month|day)\s+\d+|baseline|end\s+of\s+(?:treatment|study)',
                content, re.IGNORECASE
            )
            patterns['timepoint_patterns'].extend(timepoint_matches[:3])

        return patterns

    def _extract_with_patterns(
        self,
        protocol_text: str,
        patterns: Dict[str, List[str]]
    ) -> Dict[str, List[Dict]]:
        """Apply learned patterns to extract endpoints"""
        endpoints = {'primary': [], 'secondary': [], 'exploratory': []}

        # Find primary endpoints
        primary_section = re.search(
            r'(?:primary\s+(?:endpoint|outcome|efficacy|objective)s?)[:\s]*(.+?)(?=secondary|exploratory|$)',
            protocol_text, re.IGNORECASE | re.DOTALL
        )

        if primary_section:
            primary_text = primary_section.group(1)[:2000]
            # Extract individual endpoints
            endpoint_matches = re.findall(
                r'(?:^|\n)\s*[-•]\s*(.+?)(?=\n|$)',
                primary_text
            )
            if endpoint_matches:
                for match in endpoint_matches[:3]:
                    endpoints['primary'].append({
                        'description': match.strip(),
                        'type': 'unknown',
                        'timepoint': self._extract_timepoint(match)
                    })
            else:
                # Take first sentence as primary endpoint
                first_sentence = re.match(r'([^.]+\.)', primary_text.strip())
                if first_sentence:
                    endpoints['primary'].append({
                        'description': first_sentence.group(1).strip(),
                        'type': 'unknown',
                        'timepoint': self._extract_timepoint(first_sentence.group(1))
                    })

        # Find secondary endpoints
        secondary_section = re.search(
            r'(?:secondary\s+(?:endpoint|outcome|efficacy|objective)s?)[:\s]*(.+?)(?=exploratory|safety|$)',
            protocol_text, re.IGNORECASE | re.DOTALL
        )

        if secondary_section:
            secondary_text = secondary_section.group(1)[:2000]
            endpoint_matches = re.findall(
                r'(?:^|\n)\s*[-•]\s*(.+?)(?=\n|$)',
                secondary_text
            )
            for match in endpoint_matches[:5]:
                endpoints['secondary'].append({
                    'description': match.strip(),
                    'type': 'unknown',
                    'timepoint': self._extract_timepoint(match)
                })

        return endpoints

    def _extract_timepoint(self, text: str) -> Optional[str]:
        """Extract timepoint from endpoint text"""
        match = re.search(
            r'(?:at\s+)?(?:week|month|day)\s+\d+|baseline|end\s+of\s+(?:treatment|study)',
            text, re.IGNORECASE
        )
        return match.group(0) if match else None

    def _classify_endpoint_type(
        self,
        endpoint_desc: str,
        examples: List[RetrievalResult]
    ) -> str:
        """Classify endpoint type based on description and examples"""
        desc_lower = endpoint_desc.lower()

        # Time-to-event indicators
        if any(term in desc_lower for term in [
            'survival', 'time to', 'progression-free', 'pfs', 'os', 'dfs',
            'event-free', 'duration', 'efs', 'ttf', 'time-to-'
        ]):
            return 'time_to_event'

        # Binary/response indicators
        if any(term in desc_lower for term in [
            'response rate', 'orr', 'objective response', 'complete response',
            'partial response', 'dcr', 'cbr', 'remission rate', 'responder'
        ]):
            return 'binary'

        # Continuous indicators
        if any(term in desc_lower for term in [
            'change from baseline', 'mean change', 'reduction', 'improvement',
            'score', 'level', 'concentration', 'cfb', 'percent change'
        ]):
            return 'continuous'

        # Count indicators
        if any(term in desc_lower for term in [
            'number of', 'count', 'frequency', 'incidence', 'rate of'
        ]):
            return 'count'

        # Check examples for similar endpoints
        for example in examples:
            if endpoint_desc[:30].lower() in example.content.lower():
                # Try to extract type from example
                if 'time-to-event' in example.content.lower():
                    return 'time_to_event'
                if 'binary' in example.content.lower():
                    return 'binary'
                if 'continuous' in example.content.lower():
                    return 'continuous'

        return 'unknown'


class MethodSelectionAgent:
    """
    Agent that selects appropriate statistical methods using RAG.

    Uses retrieved SAP examples to:
    1. Match endpoint types to standard methods
    2. Learn method selection patterns
    3. Suggest appropriate analysis approaches
    """

    # Standard method mappings
    METHOD_MAP = {
        'time_to_event': {
            'primary': 'Kaplan-Meier with log-rank test',
            'sensitivity': 'Cox proportional hazards model',
            'subgroup': 'Forest plot of hazard ratios'
        },
        'binary': {
            'primary': 'Cochran-Mantel-Haenszel test',
            'sensitivity': 'Logistic regression',
            'ci_method': 'Clopper-Pearson exact confidence interval'
        },
        'continuous': {
            'primary': 'ANCOVA with baseline as covariate',
            'sensitivity': 'MMRM (Mixed Model Repeated Measures)',
            'missing_data': 'Multiple imputation'
        },
        'count': {
            'primary': 'Negative binomial regression',
            'sensitivity': 'Poisson regression with overdispersion',
            'rate_ratio': 'Rate ratio with 95% CI'
        },
        'ordinal': {
            'primary': 'Proportional odds model',
            'sensitivity': 'Wilcoxon rank-sum test',
            'visualization': 'Stacked bar chart'
        }
    }

    def __init__(self, retriever: SAPRetriever = None):
        self.retriever = retriever or SAPRetriever()

    def select_methods(
        self,
        endpoint_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Select statistical methods for endpoints.

        Args:
            endpoint_info: Endpoint information including type

        Returns:
            Dictionary with recommended methods
        """
        # Get similar method sections
        rag_context = self.retriever.retrieve_for_methods(endpoint_info)

        # Get base methods from mapping
        endpoint_type = endpoint_info.get('endpoint_type', 'continuous')
        base_methods = self.METHOD_MAP.get(endpoint_type, self.METHOD_MAP['continuous'])

        # Enhance with patterns from retrieved examples
        enhanced_methods = self._enhance_with_examples(
            base_methods,
            endpoint_info,
            rag_context.retrieved_examples
        )

        return {
            'endpoint_type': endpoint_type,
            'primary_analysis': enhanced_methods.get('primary'),
            'sensitivity_analyses': enhanced_methods.get('sensitivity', []),
            'multiplicity_adjustment': self._get_multiplicity_method(endpoint_info),
            'missing_data_handling': enhanced_methods.get('missing_data'),
            'rag_context': {
                'query': rag_context.query,
                'num_examples': len(rag_context.retrieved_examples),
                'example_nct_ids': [r.nct_id for r in rag_context.retrieved_examples[:3]]
            }
        }

    def _enhance_with_examples(
        self,
        base_methods: Dict[str, str],
        endpoint_info: Dict[str, Any],
        examples: List[RetrievalResult]
    ) -> Dict[str, Any]:
        """Enhance method selection with retrieved examples"""
        enhanced = dict(base_methods)
        sensitivity_analyses = [base_methods.get('sensitivity')]

        for example in examples:
            content = example.content.lower()

            # Look for additional sensitivity analyses
            if 'tipping point' in content:
                sensitivity_analyses.append('Tipping point analysis')
            if 'per protocol' in content or 'per-protocol' in content:
                sensitivity_analyses.append('Per-protocol population analysis')
            if 'subgroup' in content:
                sensitivity_analyses.append('Pre-specified subgroup analyses')
            if 'multiple imputation' in content:
                enhanced['missing_data'] = 'Multiple imputation under MAR assumption'
            if 'pattern mixture' in content:
                sensitivity_analyses.append('Pattern mixture model')

        # Remove duplicates and None
        sensitivity_analyses = list(set(filter(None, sensitivity_analyses)))
        enhanced['sensitivity'] = sensitivity_analyses[:5]

        return enhanced

    def _get_multiplicity_method(self, endpoint_info: Dict[str, Any]) -> str:
        """Select appropriate multiplicity adjustment"""
        num_endpoints = endpoint_info.get('num_secondary_endpoints', 0)

        if num_endpoints == 0:
            return "No adjustment required (single primary endpoint)"
        elif num_endpoints <= 3:
            return "Hochberg procedure for secondary endpoints"
        else:
            return "Hierarchical testing with gatekeeping procedure"


class StratificationParserAgent:
    """
    Agent that parses stratification factors using RAG.

    Uses retrieved examples to:
    1. Identify common stratification factors for therapeutic area
    2. Learn factor categorization patterns
    3. Suggest stratification scheme
    """

    # Common stratification factors by therapeutic area
    COMMON_FACTORS = {
        'oncology': ['ECOG performance status', 'Prior therapy', 'Disease stage', 'Geographic region'],
        'gi': ['Disease severity', 'Prior biologic use', 'Corticosteroid use', 'Geographic region'],
        'rheumatology': ['Prior biologic use', 'Baseline disease activity', 'Methotrexate use', 'Geographic region'],
        'neurology': ['Baseline severity', 'Prior medication', 'Age group', 'Geographic region'],
        'cardiology': ['NYHA class', 'Prior MI', 'Diabetes status', 'Geographic region'],
        'immunology': ['Disease severity', 'Prior therapy', 'Steroid use', 'Geographic region'],
        'dermatology': ['BSA involvement', 'Prior biologic use', 'Disease severity', 'Geographic region'],
        'respiratory': ['Baseline FEV1', 'Exacerbation history', 'ICS use', 'Geographic region'],
        'metabolic': ['Baseline HbA1c', 'Prior therapy', 'BMI category', 'Geographic region'],
        'infectious': ['Baseline viral load', 'Treatment history', 'Fibrosis stage', 'Geographic region'],
        'hematology': ['Disease risk', 'Prior lines of therapy', 'Cytogenetic risk', 'Geographic region'],
        'rare_disease': ['Mutation type', 'Disease severity', 'Age group', 'Geographic region']
    }

    def __init__(self, retriever: SAPRetriever = None):
        self.retriever = retriever or SAPRetriever()

    def parse_stratification(
        self,
        protocol_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Parse and recommend stratification factors.

        Args:
            protocol_data: Protocol information

        Returns:
            Stratification scheme
        """
        # Get similar stratification sections
        rag_context = self.retriever.retrieve_for_stratification(protocol_data)

        # Get base factors for therapeutic area
        therapeutic_area = protocol_data.get('therapeutic_area', 'oncology').lower()
        base_factors = self.COMMON_FACTORS.get(therapeutic_area, self.COMMON_FACTORS['oncology'])

        # Extract factors from examples
        example_factors = self._extract_factors_from_examples(rag_context.retrieved_examples)

        # Merge and prioritize factors
        recommended_factors = self._merge_factors(base_factors, example_factors, protocol_data)

        return {
            'randomization_ratio': protocol_data.get('randomization_ratio', '1:1'),
            'stratification_factors': recommended_factors,
            'blocking': self._recommend_blocking(protocol_data),
            'rag_context': {
                'query': rag_context.query,
                'num_examples': len(rag_context.retrieved_examples),
                'example_nct_ids': [r.nct_id for r in rag_context.retrieved_examples[:3]]
            }
        }

    def _extract_factors_from_examples(
        self,
        examples: List[RetrievalResult]
    ) -> List[Dict[str, Any]]:
        """Extract stratification factors from examples"""
        factors = []

        for example in examples:
            content = example.content

            # Extract factor mentions
            factor_matches = re.findall(
                r'(?:stratif(?:y|ied)\s+by|stratification\s+factors?)[:\s]*([^.]+)',
                content, re.IGNORECASE
            )

            for match in factor_matches:
                # Split by common delimiters
                individual_factors = re.split(r'[,;]|\band\b', match)
                for factor in individual_factors:
                    factor = factor.strip()
                    if len(factor) > 3 and len(factor) < 100:
                        factors.append({
                            'name': factor,
                            'source_nct': example.nct_id,
                            'relevance': example.relevance_score
                        })

        return factors

    def _merge_factors(
        self,
        base_factors: List[str],
        example_factors: List[Dict],
        protocol_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Merge and prioritize stratification factors"""
        result = []
        seen_names = set()

        # First, add protocol-specified factors
        if protocol_data.get('stratification_factors'):
            for factor in protocol_data['stratification_factors']:
                if factor not in seen_names:
                    result.append({
                        'name': factor,
                        'source': 'protocol',
                        'levels': self._estimate_levels(factor)
                    })
                    seen_names.add(factor.lower())

        # Add high-relevance example factors
        for factor in sorted(example_factors, key=lambda x: x['relevance'], reverse=True):
            name_lower = factor['name'].lower()
            if name_lower not in seen_names and len(result) < 6:
                result.append({
                    'name': factor['name'],
                    'source': f"example ({factor['source_nct']})",
                    'levels': self._estimate_levels(factor['name'])
                })
                seen_names.add(name_lower)

        # Fill with base factors if needed
        for factor in base_factors:
            if factor.lower() not in seen_names and len(result) < 4:
                result.append({
                    'name': factor,
                    'source': 'standard',
                    'levels': self._estimate_levels(factor)
                })
                seen_names.add(factor.lower())

        return result[:4]  # Limit to 4 factors typically

    def _estimate_levels(self, factor_name: str) -> List[str]:
        """Estimate levels for a stratification factor"""
        name_lower = factor_name.lower()

        if 'ecog' in name_lower or 'performance status' in name_lower:
            return ['0', '1', '>=2']
        if 'region' in name_lower or 'geographic' in name_lower:
            return ['North America', 'Europe', 'Rest of World']
        if 'prior' in name_lower and ('therapy' in name_lower or 'treatment' in name_lower):
            return ['Yes', 'No']
        if 'stage' in name_lower:
            return ['Early', 'Advanced']
        if 'severity' in name_lower:
            return ['Mild/Moderate', 'Severe']
        if 'age' in name_lower:
            return ['<65', '>=65']

        return ['Level 1', 'Level 2']

    def _recommend_blocking(self, protocol_data: Dict[str, Any]) -> Dict[str, Any]:
        """Recommend blocking strategy"""
        sample_size = protocol_data.get('sample_size', 100)

        if sample_size < 50:
            block_sizes = [2, 4]
        elif sample_size < 200:
            block_sizes = [4, 6]
        else:
            block_sizes = [4, 6, 8]

        return {
            'type': 'Permuted block randomization',
            'block_sizes': block_sizes,
            'rationale': 'Variable block sizes to prevent prediction'
        }


class RAGOrchestrator:
    """
    Orchestrates all RAG agents for complete SAP generation.

    Coordinates:
    - Endpoint extraction
    - Method selection
    - Stratification parsing
    - Context aggregation
    """

    def __init__(
        self,
        vector_store: SAPVectorStore = None,
        retriever: SAPRetriever = None
    ):
        self.vector_store = vector_store or create_vector_store()
        self.retriever = retriever or SAPRetriever(self.vector_store)

        # Initialize agents
        self.endpoint_agent = EndpointExtractionAgent(self.retriever)
        self.method_agent = MethodSelectionAgent(self.retriever)
        self.stratification_agent = StratificationParserAgent(self.retriever)

    def process_protocol(
        self,
        protocol_text: str,
        protocol_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process protocol through all RAG agents.

        Args:
            protocol_text: Raw protocol text
            protocol_data: Parsed protocol metadata

        Returns:
            Complete RAG-enhanced SAP components
        """
        result = {
            'protocol_id': protocol_data.get('nct_id', 'unknown'),
            'therapeutic_area': protocol_data.get('therapeutic_area'),
            'phase': protocol_data.get('phase')
        }

        # Extract endpoints
        endpoint_result = self.endpoint_agent.extract_endpoints(
            protocol_text, protocol_data
        )
        result['endpoints'] = endpoint_result

        # For each primary endpoint, select methods
        methods_results = []
        for i, endpoint in enumerate(endpoint_result.get('primary_endpoints', [])):
            endpoint_info = {
                'endpoint_type': endpoint.get('type', 'continuous'),
                'primary_endpoint': endpoint.get('description'),
                'num_secondary_endpoints': len(endpoint_result.get('secondary_endpoints', []))
            }
            methods = self.method_agent.select_methods(endpoint_info)
            methods['endpoint_index'] = i
            methods_results.append(methods)

        result['statistical_methods'] = methods_results

        # Parse stratification
        stratification = self.stratification_agent.parse_stratification(protocol_data)
        result['stratification'] = stratification

        # Aggregate RAG statistics
        result['rag_statistics'] = self._aggregate_rag_stats(
            endpoint_result,
            methods_results,
            stratification
        )

        return result

    def _aggregate_rag_stats(
        self,
        endpoint_result: Dict,
        methods_results: List[Dict],
        stratification: Dict
    ) -> Dict[str, Any]:
        """Aggregate RAG usage statistics"""
        all_nct_ids = set()
        total_examples = 0

        # From endpoints
        if endpoint_result.get('rag_context'):
            all_nct_ids.update(endpoint_result['rag_context'].get('example_nct_ids', []))
            total_examples += endpoint_result['rag_context'].get('num_examples', 0)

        # From methods
        for methods in methods_results:
            if methods.get('rag_context'):
                all_nct_ids.update(methods['rag_context'].get('example_nct_ids', []))
                total_examples += methods['rag_context'].get('num_examples', 0)

        # From stratification
        if stratification.get('rag_context'):
            all_nct_ids.update(stratification['rag_context'].get('example_nct_ids', []))
            total_examples += stratification['rag_context'].get('num_examples', 0)

        return {
            'unique_examples_used': len(all_nct_ids),
            'total_retrievals': total_examples,
            'example_nct_ids': list(all_nct_ids)
        }

    def get_full_rag_context(
        self,
        protocol_data: Dict[str, Any],
        section_types: List[str] = None
    ) -> Dict[str, str]:
        """
        Get formatted RAG context for LLM prompt injection.

        Returns:
            Dictionary mapping section_type to formatted context string
        """
        if section_types is None:
            section_types = ["endpoints", "methods", "stratification"]

        contexts = self.retriever.retrieve_multi_section(
            protocol_data,
            section_types=section_types
        )

        formatted = {}
        for section_type, rag_context in contexts.items():
            formatted[section_type] = rag_context.to_prompt_context()

        return formatted


def create_rag_orchestrator(
    vector_store: SAPVectorStore = None
) -> RAGOrchestrator:
    """Factory function to create RAG orchestrator"""
    return RAGOrchestrator(vector_store=vector_store)


# CLI interface for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test RAG Agents")
    parser.add_argument("--test", action="store_true", help="Run test")
    args = parser.parse_args()

    if args.test:
        print("Testing RAG Agents...")

        # Create orchestrator
        orchestrator = create_rag_orchestrator()

        # Test with sample protocol data
        sample_protocol = {
            'nct_id': 'NCT_TEST',
            'therapeutic_area': 'oncology',
            'phase': '3',
            'indication': 'non-small cell lung cancer',
            'primary_endpoint': 'progression-free survival',
            'condition': 'NSCLC'
        }

        # Get RAG context
        contexts = orchestrator.get_full_rag_context(sample_protocol)

        print("\n=== Endpoint Context ===")
        print(contexts.get('endpoints', 'No context')[:500])

        print("\n=== Methods Context ===")
        print(contexts.get('methods', 'No context')[:500])

        print("\n=== Stratification Context ===")
        print(contexts.get('stratification', 'No context')[:500])

        print("\n=== Vector Store Stats ===")
        stats = orchestrator.vector_store.get_collection_stats()
        for name, count in stats.items():
            print(f"  {name}: {count} documents")
