"""
SAP Evaluation Framework (v3) - REAL Section-by-Section Comparison
===================================================================

This eval ACTUALLY compares generated SAP vs reference SAP field-by-field.

Key fields extracted and compared:
1. Primary endpoint + statistical method
2. Sample size + power + alpha
3. Analysis populations (ITT, PP, Safety definitions)
4. Randomization ratio + stratification factors
5. Interim analysis (timing, alpha spending)
6. Missing data handling method
7. Multiplicity adjustment
8. Secondary endpoints + methods

How it works:
- Extract structured fields from BOTH SAPs
- Compare each field: exact match, partial match, or mismatch
- Return detailed comparison report
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import difflib


# =============================================================================
# SECTION 1: Field Extractor - Extracts structured fields from SAP text
# =============================================================================

class SAPFieldExtractor:
    """
    Extract key fields from SAP text for comparison.

    Returns structured data that can be compared field-by-field.
    """

    def extract(self, sap_text: str) -> Dict[str, Any]:
        """Extract all key fields from SAP."""
        text_lower = sap_text.lower()

        return {
            'primary_endpoint': self._extract_primary_endpoint(sap_text),
            'primary_method': self._extract_primary_method(sap_text),
            'sample_size': self._extract_sample_size(sap_text),
            'alpha': self._extract_alpha(sap_text),
            'power': self._extract_power(sap_text),
            'populations': self._extract_populations(sap_text),
            'randomization': self._extract_randomization(sap_text),
            'stratification': self._extract_stratification(sap_text),
            'interim': self._extract_interim(sap_text),
            'missing_data': self._extract_missing_data(sap_text),
            'multiplicity': self._extract_multiplicity(sap_text),
            'secondary_endpoints': self._extract_secondary_endpoints(sap_text),
        }

    def _extract_primary_endpoint(self, text: str) -> Dict[str, Any]:
        """Extract primary endpoint definition."""
        result = {
            'name': None,
            'definition': None,
            'timeframe': None,
        }

        # Common primary endpoints in oncology
        endpoint_patterns = [
            (r'overall\s+survival\s*\(?os\)?', 'OS'),
            (r'progression[- ]free\s+survival\s*\(?pfs\)?', 'PFS'),
            (r'objective\s+response\s+rate\s*\(?orr\)?', 'ORR'),
            (r'disease[- ]free\s+survival\s*\(?dfs\)?', 'DFS'),
            (r'event[- ]free\s+survival\s*\(?efs\)?', 'EFS'),
            (r'duration\s+of\s+response\s*\(?d[o]?r\)?', 'DoR'),
            (r'complete\s+response\s+rate\s*\(?cr[r]?\)?', 'CRR'),
            (r'pathological\s+complete\s+response\s*\(?pcr\)?', 'pCR'),
        ]

        text_lower = text.lower()

        # Look for primary endpoint section
        primary_section = re.search(
            r'(?:primary|co-?primary)\s+endpoint[s]?\s*[:\-]?\s*(.*?)(?:secondary|$)',
            text_lower, re.DOTALL | re.IGNORECASE
        )

        if primary_section:
            section_text = primary_section.group(1)[:500]

            # Find which endpoint
            for pattern, name in endpoint_patterns:
                if re.search(pattern, section_text):
                    result['name'] = name
                    break

            # Extract definition
            def_match = re.search(
                r'(?:defined\s+as|is\s+defined|definition)[:\s]*(.*?)(?:\.|$)',
                section_text
            )
            if def_match:
                result['definition'] = def_match.group(1).strip()[:200]

            # Extract timeframe
            time_match = re.search(
                r'(?:time\s+frame|assessed|measured)[:\s]*(.*?)(?:\.|$)',
                section_text
            )
            if time_match:
                result['timeframe'] = time_match.group(1).strip()[:100]

        return result

    def _extract_primary_method(self, text: str) -> Dict[str, Any]:
        """Extract primary statistical method."""
        result = {
            'test': None,
            'model': None,
            'stratified': False,
        }

        text_lower = text.lower()

        # Statistical tests
        test_patterns = [
            (r'log[- ]?rank\s+test', 'log-rank'),
            (r'cox\s+(?:proportional\s+)?hazard', 'cox'),
            (r'kaplan[- ]?meier', 'kaplan-meier'),
            (r'chi[- ]?square', 'chi-square'),
            (r'fisher\'?s?\s+exact', 'fisher-exact'),
            (r'cochran[- ]?mantel[- ]?haenszel', 'cmh'),
            (r't[- ]?test', 't-test'),
            (r'wilcoxon', 'wilcoxon'),
            (r'anova', 'anova'),
            (r'ancova', 'ancova'),
            (r'mmrm', 'mmrm'),
            (r'mixed\s+model', 'mixed-model'),
            (r'logistic\s+regression', 'logistic'),
        ]

        for pattern, name in test_patterns:
            if re.search(pattern, text_lower):
                result['test'] = name
                break

        # Check if stratified
        if re.search(r'stratified\s+(?:log[- ]?rank|analysis|test)', text_lower):
            result['stratified'] = True

        # Cox model specifics
        if 'cox' in text_lower:
            result['model'] = 'cox'
            if re.search(r'hazard\s+ratio', text_lower):
                result['estimate'] = 'hazard_ratio'

        return result

    def _extract_sample_size(self, text: str) -> Dict[str, Any]:
        """Extract sample size information."""
        result = {
            'total': None,
            'per_arm': {},
            'events': None,
        }

        # Total sample size
        patterns = [
            r'(?:approximately|total\s+of|enroll[a-z]*)\s*(\d+)\s*(?:patients?|subjects?|participants?)',
            r'sample\s+size[:\s]*(\d+)',
            r'n\s*=\s*(\d+)',
            r'(\d+)\s*(?:patients?|subjects?)\s*(?:will\s+be|are)\s*(?:enrolled|randomized)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result['total'] = int(match.group(1))
                break

        # Events for time-to-event
        event_match = re.search(
            r'(\d+)\s*(?:events?|deaths?|progressions?)',
            text, re.IGNORECASE
        )
        if event_match:
            result['events'] = int(event_match.group(1))

        return result

    def _extract_alpha(self, text: str) -> Dict[str, Any]:
        """Extract significance level."""
        result = {
            'value': None,
            'sided': None,
        }

        # Alpha value
        alpha_patterns = [
            r'alpha\s*[=:]\s*(0?\.\d+)',
            r'significance\s+level\s*(?:of)?\s*(0?\.\d+)',
            r'(?:type\s+i|type\s+1)\s+error\s*(?:rate)?\s*(?:of)?\s*(0?\.\d+)',
            r'(0?\.\d+)\s*(?:two[- ]sided|one[- ]sided)\s*(?:significance|alpha)',
            r'p\s*[<≤]\s*(0?\.\d+)',
        ]

        for pattern in alpha_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result['value'] = float(match.group(1))
                break

        # One or two-sided
        if re.search(r'two[- ]sided', text, re.IGNORECASE):
            result['sided'] = 'two-sided'
        elif re.search(r'one[- ]sided', text, re.IGNORECASE):
            result['sided'] = 'one-sided'

        return result

    def _extract_power(self, text: str) -> Dict[str, Any]:
        """Extract power information."""
        result = {
            'value': None,
            'hr': None,  # hazard ratio assumption
        }

        # Power value
        power_patterns = [
            r'power\s*(?:of)?\s*(?:at\s+least)?\s*(\d+)\s*%',
            r'(\d+)\s*%\s*power',
            r'power\s*[=:]\s*(\d+)',
        ]

        for pattern in power_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result['value'] = int(match.group(1))
                break

        # Hazard ratio assumption
        hr_match = re.search(
            r'(?:hazard\s+ratio|hr)\s*(?:of)?\s*(0?\.\d+)',
            text, re.IGNORECASE
        )
        if hr_match:
            result['hr'] = float(hr_match.group(1))

        return result

    def _extract_populations(self, text: str) -> Dict[str, Any]:
        """Extract analysis population definitions."""
        result = {
            'itt': None,
            'pp': None,
            'safety': None,
        }

        text_lower = text.lower()

        # ITT definition
        itt_match = re.search(
            r'(?:intent[- ]to[- ]treat|itt|full\s+analysis\s+set|fas)[^.]*(?:defined\s+as|includes?|consists?\s+of)[:\s]*([^.]+)',
            text_lower
        )
        if itt_match:
            result['itt'] = itt_match.group(1).strip()[:200]
        elif re.search(r'all\s+random[iz]+ed\s+(?:patients?|subjects?)', text_lower):
            result['itt'] = 'all randomized patients'

        # Per-protocol definition
        pp_match = re.search(
            r'(?:per[- ]?protocol|pp)[^.]*(?:defined\s+as|includes?|consists?\s+of)[:\s]*([^.]+)',
            text_lower
        )
        if pp_match:
            result['pp'] = pp_match.group(1).strip()[:200]

        # Safety population
        safety_match = re.search(
            r'(?:safety\s+(?:population|set|analysis))[^.]*(?:defined\s+as|includes?|consists?\s+of)[:\s]*([^.]+)',
            text_lower
        )
        if safety_match:
            result['safety'] = safety_match.group(1).strip()[:200]
        elif re.search(r'(?:received|at\s+least\s+one\s+dose)', text_lower):
            result['safety'] = 'received at least one dose'

        return result

    def _extract_randomization(self, text: str) -> Dict[str, Any]:
        """Extract randomization details."""
        result = {
            'ratio': None,
            'method': None,
        }

        # Ratio
        ratio_match = re.search(
            r'(\d+)\s*:\s*(\d+)\s*(?:ratio|allocation|random)',
            text, re.IGNORECASE
        )
        if ratio_match:
            result['ratio'] = f"{ratio_match.group(1)}:{ratio_match.group(2)}"

        # Method
        if re.search(r'block\s*random', text, re.IGNORECASE):
            result['method'] = 'block'
        elif re.search(r'stratified\s*random', text, re.IGNORECASE):
            result['method'] = 'stratified'
        elif re.search(r'simple\s*random', text, re.IGNORECASE):
            result['method'] = 'simple'

        return result

    def _extract_stratification(self, text: str) -> List[str]:
        """Extract stratification factors."""
        factors = []

        text_lower = text.lower()

        # Common stratification factors
        factor_patterns = [
            (r'(?:stratif|random)[^.]*(?:by|factor)[^.]*age', 'age'),
            (r'(?:stratif|random)[^.]*(?:by|factor)[^.]*sex', 'sex'),
            (r'(?:stratif|random)[^.]*(?:by|factor)[^.]*gender', 'gender'),
            (r'(?:stratif|random)[^.]*(?:by|factor)[^.]*(?:ecog|performance)', 'ecog'),
            (r'(?:stratif|random)[^.]*(?:by|factor)[^.]*(?:stage|staging)', 'stage'),
            (r'(?:stratif|random)[^.]*(?:by|factor)[^.]*(?:region|geographic)', 'region'),
            (r'(?:stratif|random)[^.]*(?:by|factor)[^.]*(?:histology|histological)', 'histology'),
            (r'(?:stratif|random)[^.]*(?:by|factor)[^.]*(?:smoking|smoker)', 'smoking'),
            (r'(?:stratif|random)[^.]*(?:by|factor)[^.]*(?:pd-?l1|biomarker)', 'biomarker'),
            (r'(?:stratif|random)[^.]*(?:by|factor)[^.]*(?:prior\s+therapy|previous)', 'prior_therapy'),
        ]

        for pattern, name in factor_patterns:
            if re.search(pattern, text_lower):
                factors.append(name)

        return factors

    def _extract_interim(self, text: str) -> Dict[str, Any]:
        """Extract interim analysis details."""
        result = {
            'planned': False,
            'count': None,
            'timing': [],
            'alpha_spending': None,
            'stopping_rules': None,
        }

        text_lower = text.lower()

        # Check if interim planned
        if re.search(r'interim\s+analys[ie]s', text_lower):
            result['planned'] = True

        # Number of interims
        count_match = re.search(r'(\d+)\s*interim\s+analys[ie]s', text_lower)
        if count_match:
            result['count'] = int(count_match.group(1))

        # Alpha spending function
        if re.search(r"o'brien[- ]?fleming", text_lower):
            result['alpha_spending'] = 'obrien-fleming'
        elif re.search(r'pocock', text_lower):
            result['alpha_spending'] = 'pocock'
        elif re.search(r'lan[- ]?demets', text_lower):
            result['alpha_spending'] = 'lan-demets'

        # Timing (events or information fraction)
        timing_matches = re.findall(
            r'(?:interim|analysis)\s*(?:at|when|after)\s*(\d+)\s*(?:events?|deaths?|%)',
            text_lower
        )
        if timing_matches:
            result['timing'] = [int(t) for t in timing_matches]

        return result

    def _extract_missing_data(self, text: str) -> Dict[str, Any]:
        """Extract missing data handling approach."""
        result = {
            'method': None,
            'sensitivity': [],
        }

        text_lower = text.lower()

        # Primary method
        methods = [
            (r'multiple\s+imputation', 'multiple_imputation'),
            (r'last\s+observation\s+carried|locf', 'locf'),
            (r'baseline\s+observation\s+carried|bocf', 'bocf'),
            (r'mixed\s+(?:effect\s+)?model.*repeated', 'mmrm'),
            (r'complete\s+case', 'complete_case'),
            (r'pattern\s+mixture', 'pattern_mixture'),
            (r'tipping\s+point', 'tipping_point'),
            (r'jump\s+to\s+reference', 'jump_to_reference'),
        ]

        for pattern, name in methods:
            if re.search(pattern, text_lower):
                result['method'] = name
                break

        # Sensitivity analyses
        sensitivity_patterns = [
            (r'tipping\s+point', 'tipping_point'),
            (r'pattern\s+mixture', 'pattern_mixture'),
            (r'multiple\s+imputation', 'multiple_imputation'),
            (r'worst[- ]?case', 'worst_case'),
        ]

        for pattern, name in sensitivity_patterns:
            if re.search(pattern, text_lower):
                if name not in result['sensitivity']:
                    result['sensitivity'].append(name)

        return result

    def _extract_multiplicity(self, text: str) -> Dict[str, Any]:
        """Extract multiplicity adjustment method."""
        result = {
            'method': None,
            'hierarchy': [],
        }

        text_lower = text.lower()

        # Method
        methods = [
            (r'bonferroni', 'bonferroni'),
            (r'hochberg', 'hochberg'),
            (r'holm', 'holm'),
            (r'gatekeeping', 'gatekeeping'),
            (r'hierarchical\s+(?:testing|procedure)', 'hierarchical'),
            (r'fixed[- ]?sequence', 'fixed_sequence'),
            (r'fallback', 'fallback'),
            (r'alpha\s+(?:splitting|allocation)', 'alpha_split'),
            (r'no\s+(?:adjustment|multiplicity)', 'none'),
        ]

        for pattern, name in methods:
            if re.search(pattern, text_lower):
                result['method'] = name
                break

        return result

    def _extract_secondary_endpoints(self, text: str) -> List[str]:
        """Extract secondary endpoints."""
        endpoints = []

        text_lower = text.lower()

        endpoint_patterns = [
            (r'overall\s+survival', 'OS'),
            (r'progression[- ]free\s+survival', 'PFS'),
            (r'objective\s+response\s+rate', 'ORR'),
            (r'duration\s+of\s+response', 'DoR'),
            (r'disease\s+control\s+rate', 'DCR'),
            (r'time\s+to\s+(?:progression|response)', 'TTP'),
            (r'quality\s+of\s+life', 'QoL'),
            (r'patient[- ]reported\s+outcome', 'PRO'),
        ]

        # Look in secondary section
        secondary_section = re.search(
            r'secondary\s+endpoint[s]?\s*[:\-]?\s*(.*?)(?:exploratory|safety|$)',
            text_lower, re.DOTALL
        )

        if secondary_section:
            section_text = secondary_section.group(1)[:1000]
            for pattern, name in endpoint_patterns:
                if re.search(pattern, section_text):
                    endpoints.append(name)

        return endpoints


# =============================================================================
# SECTION 2: Field Comparator - Compares extracted fields
# =============================================================================

class SAPFieldComparator:
    """
    Compare extracted fields from generated vs reference SAP.

    Returns detailed match scores for each field.
    """

    def compare(
        self,
        generated_fields: Dict[str, Any],
        reference_fields: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare all fields between generated and reference SAP."""

        comparisons = {}

        # 1. Primary endpoint
        comparisons['primary_endpoint'] = self._compare_primary_endpoint(
            generated_fields['primary_endpoint'],
            reference_fields['primary_endpoint']
        )

        # 2. Primary method
        comparisons['primary_method'] = self._compare_primary_method(
            generated_fields['primary_method'],
            reference_fields['primary_method']
        )

        # 3. Sample size
        comparisons['sample_size'] = self._compare_sample_size(
            generated_fields['sample_size'],
            reference_fields['sample_size']
        )

        # 4. Alpha
        comparisons['alpha'] = self._compare_alpha(
            generated_fields['alpha'],
            reference_fields['alpha']
        )

        # 5. Power
        comparisons['power'] = self._compare_power(
            generated_fields['power'],
            reference_fields['power']
        )

        # 6. Populations
        comparisons['populations'] = self._compare_populations(
            generated_fields['populations'],
            reference_fields['populations']
        )

        # 7. Randomization
        comparisons['randomization'] = self._compare_randomization(
            generated_fields['randomization'],
            reference_fields['randomization']
        )

        # 8. Stratification
        comparisons['stratification'] = self._compare_stratification(
            generated_fields['stratification'],
            reference_fields['stratification']
        )

        # 9. Interim
        comparisons['interim'] = self._compare_interim(
            generated_fields['interim'],
            reference_fields['interim']
        )

        # 10. Missing data
        comparisons['missing_data'] = self._compare_missing_data(
            generated_fields['missing_data'],
            reference_fields['missing_data']
        )

        # 11. Multiplicity
        comparisons['multiplicity'] = self._compare_multiplicity(
            generated_fields['multiplicity'],
            reference_fields['multiplicity']
        )

        # 12. Secondary endpoints
        comparisons['secondary_endpoints'] = self._compare_secondary_endpoints(
            generated_fields['secondary_endpoints'],
            reference_fields['secondary_endpoints']
        )

        # Calculate overall score
        scores = [c['score'] for c in comparisons.values() if 'score' in c]
        comparisons['overall_score'] = sum(scores) / len(scores) if scores else 0.0

        return comparisons

    def _compare_primary_endpoint(self, gen: Dict, ref: Dict) -> Dict:
        """Compare primary endpoint."""
        result = {
            'generated': gen,
            'reference': ref,
            'match': 'none',
            'score': 0.0,
        }

        if gen['name'] and ref['name']:
            if gen['name'] == ref['name']:
                result['match'] = 'exact'
                result['score'] = 1.0
            else:
                result['match'] = 'mismatch'
                result['score'] = 0.0
        elif gen['name'] or ref['name']:
            result['match'] = 'partial'
            result['score'] = 0.3
        else:
            result['match'] = 'both_missing'
            result['score'] = 0.0

        return result

    def _compare_primary_method(self, gen: Dict, ref: Dict) -> Dict:
        """Compare primary statistical method."""
        result = {
            'generated': gen,
            'reference': ref,
            'match': 'none',
            'score': 0.0,
        }

        score = 0.0

        # Test match
        if gen['test'] and ref['test']:
            if gen['test'] == ref['test']:
                score += 0.6
            elif gen['test'] in ['log-rank', 'cox'] and ref['test'] in ['log-rank', 'cox']:
                score += 0.4  # Both time-to-event methods

        # Stratified match
        if gen['stratified'] == ref['stratified']:
            score += 0.4
        elif gen['stratified'] or ref['stratified']:
            score += 0.2

        result['score'] = score
        result['match'] = 'exact' if score >= 0.9 else ('partial' if score > 0.3 else 'mismatch')

        return result

    def _compare_sample_size(self, gen: Dict, ref: Dict) -> Dict:
        """Compare sample size."""
        result = {
            'generated': gen,
            'reference': ref,
            'match': 'none',
            'score': 0.0,
        }

        if gen['total'] and ref['total']:
            # Allow 5% tolerance
            diff = abs(gen['total'] - ref['total']) / ref['total']
            if diff <= 0.05:
                result['match'] = 'exact'
                result['score'] = 1.0
            elif diff <= 0.15:
                result['match'] = 'close'
                result['score'] = 0.7
            else:
                result['match'] = 'mismatch'
                result['score'] = 0.3
        elif gen['total'] or ref['total']:
            result['match'] = 'partial'
            result['score'] = 0.2

        return result

    def _compare_alpha(self, gen: Dict, ref: Dict) -> Dict:
        """Compare significance level."""
        result = {
            'generated': gen,
            'reference': ref,
            'match': 'none',
            'score': 0.0,
        }

        score = 0.0

        # Value match
        if gen['value'] and ref['value']:
            if abs(gen['value'] - ref['value']) < 0.001:
                score += 0.7
            elif abs(gen['value'] - ref['value']) < 0.01:
                score += 0.4

        # Sidedness match
        if gen['sided'] and ref['sided']:
            if gen['sided'] == ref['sided']:
                score += 0.3
        elif gen['sided'] or ref['sided']:
            score += 0.1

        result['score'] = score
        result['match'] = 'exact' if score >= 0.9 else ('partial' if score > 0.3 else 'mismatch')

        return result

    def _compare_power(self, gen: Dict, ref: Dict) -> Dict:
        """Compare power."""
        result = {
            'generated': gen,
            'reference': ref,
            'match': 'none',
            'score': 0.0,
        }

        score = 0.0

        if gen['value'] and ref['value']:
            if gen['value'] == ref['value']:
                score += 0.6
            elif abs(gen['value'] - ref['value']) <= 5:
                score += 0.4

        if gen['hr'] and ref['hr']:
            if abs(gen['hr'] - ref['hr']) < 0.01:
                score += 0.4
            elif abs(gen['hr'] - ref['hr']) < 0.05:
                score += 0.2

        result['score'] = score
        result['match'] = 'exact' if score >= 0.9 else ('partial' if score > 0.3 else 'mismatch')

        return result

    def _compare_populations(self, gen: Dict, ref: Dict) -> Dict:
        """Compare analysis populations."""
        result = {
            'generated': gen,
            'reference': ref,
            'match': 'none',
            'score': 0.0,
        }

        score = 0.0
        count = 0

        for pop in ['itt', 'pp', 'safety']:
            if gen[pop] and ref[pop]:
                count += 1
                # Simple text similarity
                gen_words = set(gen[pop].lower().split())
                ref_words = set(ref[pop].lower().split())
                overlap = len(gen_words & ref_words) / max(len(ref_words), 1)
                score += overlap
            elif gen[pop] or ref[pop]:
                count += 1
                score += 0.2

        result['score'] = score / count if count > 0 else 0.0
        result['match'] = 'exact' if result['score'] >= 0.8 else ('partial' if result['score'] > 0.3 else 'mismatch')

        return result

    def _compare_randomization(self, gen: Dict, ref: Dict) -> Dict:
        """Compare randomization details."""
        result = {
            'generated': gen,
            'reference': ref,
            'match': 'none',
            'score': 0.0,
        }

        score = 0.0

        if gen['ratio'] and ref['ratio']:
            if gen['ratio'] == ref['ratio']:
                score += 0.7

        if gen['method'] and ref['method']:
            if gen['method'] == ref['method']:
                score += 0.3

        result['score'] = score
        result['match'] = 'exact' if score >= 0.9 else ('partial' if score > 0.3 else 'mismatch')

        return result

    def _compare_stratification(self, gen: List, ref: List) -> Dict:
        """Compare stratification factors."""
        result = {
            'generated': gen,
            'reference': ref,
            'match': 'none',
            'score': 0.0,
        }

        if gen and ref:
            gen_set = set(gen)
            ref_set = set(ref)

            if gen_set == ref_set:
                result['match'] = 'exact'
                result['score'] = 1.0
            else:
                overlap = len(gen_set & ref_set)
                total = len(gen_set | ref_set)
                result['score'] = overlap / total if total > 0 else 0.0
                result['match'] = 'partial' if result['score'] > 0.3 else 'mismatch'
        elif gen or ref:
            result['match'] = 'partial'
            result['score'] = 0.2

        return result

    def _compare_interim(self, gen: Dict, ref: Dict) -> Dict:
        """Compare interim analysis plans."""
        result = {
            'generated': gen,
            'reference': ref,
            'match': 'none',
            'score': 0.0,
        }

        score = 0.0

        # Planned match
        if gen['planned'] == ref['planned']:
            score += 0.3

        # Count match
        if gen['count'] and ref['count']:
            if gen['count'] == ref['count']:
                score += 0.3

        # Alpha spending match
        if gen['alpha_spending'] and ref['alpha_spending']:
            if gen['alpha_spending'] == ref['alpha_spending']:
                score += 0.4
        elif not gen['alpha_spending'] and not ref['alpha_spending']:
            score += 0.2

        result['score'] = score
        result['match'] = 'exact' if score >= 0.9 else ('partial' if score > 0.3 else 'mismatch')

        return result

    def _compare_missing_data(self, gen: Dict, ref: Dict) -> Dict:
        """Compare missing data handling."""
        result = {
            'generated': gen,
            'reference': ref,
            'match': 'none',
            'score': 0.0,
        }

        score = 0.0

        # Primary method match
        if gen['method'] and ref['method']:
            if gen['method'] == ref['method']:
                score += 0.7

        # Sensitivity analyses overlap
        if gen['sensitivity'] and ref['sensitivity']:
            gen_set = set(gen['sensitivity'])
            ref_set = set(ref['sensitivity'])
            overlap = len(gen_set & ref_set)
            total = len(ref_set)
            score += 0.3 * (overlap / total if total > 0 else 0)

        result['score'] = score
        result['match'] = 'exact' if score >= 0.8 else ('partial' if score > 0.3 else 'mismatch')

        return result

    def _compare_multiplicity(self, gen: Dict, ref: Dict) -> Dict:
        """Compare multiplicity adjustment."""
        result = {
            'generated': gen,
            'reference': ref,
            'match': 'none',
            'score': 0.0,
        }

        if gen['method'] and ref['method']:
            if gen['method'] == ref['method']:
                result['match'] = 'exact'
                result['score'] = 1.0
            else:
                result['match'] = 'mismatch'
                result['score'] = 0.3
        elif gen['method'] or ref['method']:
            result['match'] = 'partial'
            result['score'] = 0.2

        return result

    def _compare_secondary_endpoints(self, gen: List, ref: List) -> Dict:
        """Compare secondary endpoints."""
        result = {
            'generated': gen,
            'reference': ref,
            'match': 'none',
            'score': 0.0,
        }

        if gen and ref:
            gen_set = set(gen)
            ref_set = set(ref)

            if gen_set == ref_set:
                result['match'] = 'exact'
                result['score'] = 1.0
            else:
                overlap = len(gen_set & ref_set)
                total = len(ref_set)
                result['score'] = overlap / total if total > 0 else 0.0
                result['match'] = 'partial' if result['score'] > 0.3 else 'mismatch'
        elif gen or ref:
            result['match'] = 'partial'
            result['score'] = 0.2

        return result


# =============================================================================
# SECTION 3: Main Evaluator
# =============================================================================

@dataclass
class EvalResultV3:
    """Evaluation result with field-by-field comparison."""
    nct_id: str

    # Field comparisons
    comparisons: Dict[str, Any] = field(default_factory=dict)

    # Summary scores
    overall_score: float = 0.0
    field_scores: Dict[str, float] = field(default_factory=dict)

    # Metadata
    generated_length: int = 0
    reference_length: int = 0
    eval_time: float = 0.0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'nct_id': self.nct_id,
            'overall_score': self.overall_score,
            'field_scores': self.field_scores,
            'comparisons': self.comparisons,
            'generated_length': self.generated_length,
            'reference_length': self.reference_length,
            'eval_time': self.eval_time,
            'errors': self.errors,
        }

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"NCT ID: {self.nct_id}",
            f"Overall Score: {self.overall_score:.2f}",
            "",
            "Field Scores:",
        ]

        for field_name, score in self.field_scores.items():
            match = self.comparisons.get(field_name, {}).get('match', 'unknown')
            lines.append(f"  {field_name}: {score:.2f} ({match})")

        return "\n".join(lines)


class SAPEvaluatorV3:
    """
    SAP Evaluator V3 - Real field-by-field comparison.

    Compares generated SAP to reference SAP by extracting
    structured fields and comparing them.
    """

    def __init__(self):
        self.extractor = SAPFieldExtractor()
        self.comparator = SAPFieldComparator()

    def evaluate(
        self,
        generated_sap: str,
        reference_sap: str,
        nct_id: str = "unknown",
    ) -> EvalResultV3:
        """
        Evaluate generated SAP against reference SAP.

        Args:
            generated_sap: The SAP generated by your system
            reference_sap: The reference SAP from eval set
            nct_id: Trial identifier

        Returns:
            EvalResultV3 with detailed field comparisons
        """
        import time
        start_time = time.time()

        result = EvalResultV3(nct_id=nct_id)
        result.generated_length = len(generated_sap)
        result.reference_length = len(reference_sap)

        try:
            # Extract fields from both SAPs
            gen_fields = self.extractor.extract(generated_sap)
            ref_fields = self.extractor.extract(reference_sap)

            # Compare fields
            comparisons = self.comparator.compare(gen_fields, ref_fields)

            result.comparisons = comparisons
            result.overall_score = comparisons.get('overall_score', 0.0)

            # Extract individual field scores
            for field_name in [
                'primary_endpoint', 'primary_method', 'sample_size', 'alpha',
                'power', 'populations', 'randomization', 'stratification',
                'interim', 'missing_data', 'multiplicity', 'secondary_endpoints'
            ]:
                if field_name in comparisons:
                    result.field_scores[field_name] = comparisons[field_name].get('score', 0.0)

        except Exception as e:
            result.errors.append(str(e))

        result.eval_time = time.time() - start_time
        return result


# =============================================================================
# SECTION 4: Benchmark Runner
# =============================================================================

class SAPBenchmarkRunner:
    """
    Run benchmark on eval set.

    For each protocol in eval set:
    1. Generate SAP using your system (via API or function)
    2. Compare to reference SAP
    3. Collect scores
    """

    def __init__(
        self,
        eval_set_path: str = None,
        api_url: str = "http://localhost:8000",
    ):
        self.eval_set_path = Path(eval_set_path) if eval_set_path else self._default_path()
        self.api_url = api_url
        self.evaluator = SAPEvaluatorV3()

    def _default_path(self) -> Path:
        return Path(__file__).parent.parent.parent / 'data' / 'eval_set'

    def get_eval_pairs(self) -> List[Tuple[str, str, str]]:
        """Get (nct_id, protocol_path, reference_sap_path) tuples."""
        pairs = []
        for sap_path in self.eval_set_path.glob('*_sap.txt'):
            nct_id = sap_path.stem.replace('_sap', '')
            protocol_path = self.eval_set_path / f'{nct_id}_protocol.txt'
            if protocol_path.exists():
                pairs.append((nct_id, str(protocol_path), str(sap_path)))
        return sorted(pairs)

    def evaluate_single(
        self,
        generated_sap: str,
        reference_sap: str,
        nct_id: str = "unknown",
    ) -> EvalResultV3:
        """Evaluate a single generated SAP."""
        return self.evaluator.evaluate(generated_sap, reference_sap, nct_id)

    def run_with_generator(
        self,
        generator_fn,
        limit: int = None,
        verbose: bool = True,
    ) -> List[EvalResultV3]:
        """
        Run benchmark using a generator function.

        Args:
            generator_fn: Function that takes protocol_text and returns generated_sap
            limit: Max number of pairs to evaluate
            verbose: Print progress

        Returns:
            List of EvalResultV3
        """
        pairs = self.get_eval_pairs()
        if limit:
            pairs = pairs[:limit]

        results = []

        for i, (nct_id, protocol_path, sap_path) in enumerate(pairs, 1):
            try:
                # Load protocol and reference SAP
                with open(protocol_path, encoding='utf-8') as f:
                    protocol = f.read()
                with open(sap_path, encoding='utf-8') as f:
                    reference_sap = f.read()

                # Generate SAP
                generated_sap = generator_fn(protocol)

                # Evaluate
                result = self.evaluator.evaluate(generated_sap, reference_sap, nct_id)
                results.append(result)

                if verbose:
                    print(f"[{i}/{len(pairs)}] {nct_id}: {result.overall_score:.2f}")

            except Exception as e:
                if verbose:
                    print(f"[{i}/{len(pairs)}] {nct_id}: ERROR - {e}")

        return results

    def print_summary(self, results: List[EvalResultV3]):
        """Print benchmark summary."""
        if not results:
            print("No results to summarize.")
            return

        print("\n" + "=" * 70)
        print("BENCHMARK SUMMARY")
        print("=" * 70)
        print(f"Evaluated: {len(results)} SAPs")
        print(f"Average Overall Score: {sum(r.overall_score for r in results) / len(results):.3f}")
        print()

        # Per-field averages
        field_names = [
            'primary_endpoint', 'primary_method', 'sample_size', 'alpha',
            'power', 'populations', 'randomization', 'stratification',
            'interim', 'missing_data', 'multiplicity', 'secondary_endpoints'
        ]

        print("Field Scores (average):")
        for field_name in field_names:
            scores = [r.field_scores.get(field_name, 0) for r in results]
            avg = sum(scores) / len(scores) if scores else 0
            print(f"  {field_name:25s}: {avg:.3f}")


# =============================================================================
# SECTION 5: CLI
# =============================================================================

def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="SAP Evaluation V3 - Field-by-Field Comparison")
    parser.add_argument('--generated', type=str, help='Path to generated SAP')
    parser.add_argument('--reference', type=str, help='Path to reference SAP')
    parser.add_argument('--nct-id', type=str, default='unknown', help='NCT ID')
    parser.add_argument('--eval-set', type=str, help='Path to eval set directory')

    args = parser.parse_args()

    if args.generated and args.reference:
        # Single evaluation
        with open(args.generated, encoding='utf-8') as f:
            generated = f.read()
        with open(args.reference, encoding='utf-8') as f:
            reference = f.read()

        evaluator = SAPEvaluatorV3()
        result = evaluator.evaluate(generated, reference, args.nct_id)

        print(result.summary())
        print("\nDetailed comparisons:")
        print(json.dumps(result.to_dict(), indent=2, default=str))
    else:
        print("Usage: python sap_eval_v3.py --generated <path> --reference <path>")


if __name__ == "__main__":
    main()
