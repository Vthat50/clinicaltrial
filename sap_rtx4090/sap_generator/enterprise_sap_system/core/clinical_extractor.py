#!/usr/bin/env python3
"""
Clinical Trial Domain-Specific Extractor
=========================================
Production-grade extraction for clinical trial-specific details that LLMs miss.

Extracts:
- Diary data calculation rules
- PK sampling windows and methods
- Modified scoring criteria
- Worsening/withdrawal criteria
- Biomarker subgroup specifications
- Sensitivity analysis requirements
- Visit schedule details
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class DiaryDataRules:
    """Rules for calculating patient-reported outcomes from diary data."""
    days_required: int = 3
    days_to_average: str = "3-5"
    exclusion_rules: List[str] = field(default_factory=list)
    minimum_days: int = 3
    handling_if_insufficient: str = "treated as missing"


@dataclass
class PKSamplingWindow:
    """PK sampling timepoint with acceptable window."""
    timepoint: str
    target_time: str
    window_minus: str
    window_plus: str
    notes: str = ""


@dataclass
class PKAnalysisSpec:
    """PK analysis specifications."""
    parameters: List[str] = field(default_factory=list)
    method: str = "Non-compartmental analysis"
    software: str = "WinNonlin"
    population: str = "PK Analysis Set"
    sampling_windows: List[PKSamplingWindow] = field(default_factory=list)


@dataclass
class ScoringModification:
    """Modified scoring criteria vs standard."""
    score_name: str
    modification: str
    original_criteria: str
    modified_criteria: str
    source_section: str


@dataclass
class WithdrawalCriteria:
    """Criteria for patient withdrawal/worsening."""
    criterion: str
    threshold: str
    confirmation_required: str
    handling_in_analysis: str


@dataclass
class SubgroupSpec:
    """Biomarker subgroup analysis specification."""
    biomarker: str
    cutoff_method: str
    cutoff_value: Optional[str] = None
    subgroups: List[str] = field(default_factory=list)
    analysis_approach: str = ""


@dataclass
class SensitivityAnalysis:
    """Sensitivity analysis specification."""
    name: str
    description: str
    differs_from_primary: str
    population: str = ""
    method: str = ""


class ClinicalTrialExtractor:
    """
    Extracts clinical trial-specific details from protocol.
    These are domain-specific elements that generic extractors miss.
    """

    # Diary data patterns
    DIARY_PATTERNS = [
        r'(\d+)[-–](\d+)\s+days?\s+(?:of\s+)?diary',
        r'average\s+(?:of\s+)?(?:the\s+)?(\d+)[-–](\d+)\s+days?',
        r'calculated\s+from\s+(\d+)[-–](\d+)\s+days?',
        r'minimum\s+(?:of\s+)?(\d+)\s+days?\s+required',
    ]

    DIARY_EXCLUSION_PATTERNS = [
        r'days?\s+with\s+bowel\s+prep\s+should\s+be\s+excluded',
        r'exclude\s+(?:the\s+)?day\s+of\s+(?:endoscopy|colonoscopy)',
        r'day\s+after\s+(?:endoscopy|colonoscopy)\s+should\s+be\s+excluded',
        r'days?\s+(?:of|with)\s+(?:bowel\s+)?prep(?:aration)?\s+excluded',
    ]

    # PK patterns
    PK_PARAMETER_PATTERNS = [
        r'AUC(?:inf|t|0-\w+)?',
        r'C(?:max|min|trough)',
        r't(?:max|1/2|½)',
        r'(?:CL|Vz|Vd|Vss)',
        r'λz|MRT',
        r'%ExtrapAUC',
    ]

    PK_WINDOW_PATTERNS = [
        r'(\d+(?:\.\d+)?)\s*h(?:our)?s?\s*(?:post[- ]?dose)?[:\s]+(?:within\s+)?(\d+)\s*(?:h|min)',
        r'pre[- ]?dose[:\s]+within\s+(\d+)\s*h',
        r'(\d+)[-–](\d+)\s*h\s+post[:\s]+[±]?\s*(\d+)\s*min',
    ]

    # Modified scoring patterns
    MODIFIED_SCORING_PATTERNS = [
        r'(?:criteria|scoring)\s+(?:in\s+this\s+study\s+)?(?:is|are)\s+(?:DIFFERENT|different|modified)',
        r'(?:subscore|score)\s+is\s+modified\s+so\s+that\s+(.+)',
        r'does\s+NOT\s+include\s+(\w+)',
        r'unlike\s+(?:the\s+)?(?:original|standard)',
    ]

    # Worsening/withdrawal patterns
    WORSENING_PATTERNS = [
        r'(?:worsening|deterioration)\s+(?:is\s+)?defined\s+as\s+(.+?)(?:\.|$)',
        r'increase\s+in\s+(\w+\s+subscore)\s+[≥>]\s*(\d+)',
        r'over\s+(\d+)\s+consecutive\s+days?',
        r'confirmed\s+by\s+(\w+)',
        r'withdraw(?:n|al)\s+(?:for|due\s+to)\s+worsening',
    ]

    # Biomarker subgroup patterns
    BIOMARKER_PATTERNS = [
        r'split\s+into\s+subgroups?\s+based\s+on\s+(?:baseline\s+)?(?:level\s+of\s+)?(\w+(?:/\w+)?)',
        r'subgroup\s+analysis\s+(?:by|based\s+on)\s+(\w+(?:/\w+)?)',
        r'(?:high|low)\s+(\w+)\s+(?:group|subgroup)',
        r'median\s+(?:split|cut[- ]?off)',
    ]

    # Sensitivity analysis patterns
    SENSITIVITY_PATTERNS = [
        r'sensitivity\s+analysis\s+(?:will\s+)?(?:be\s+)?(?:performed|conducted)\s+(?:using|with|on)\s+(.+?)(?:\.|$)',
        r'(?:as\s+)?sensitivity[,:\s]+(.+?)(?:will\s+be|population)',
        r'(?:LOCF|BOCF|MMRM|MI|multiple\s+imputation)',
        r'per[- ]?protocol\s+(?:population\s+)?(?:as\s+)?sensitivity',
    ]

    # Alpha level assignment patterns
    ALPHA_ASSIGNMENT_PATTERNS = [
        r'(\w+\s+endpoint)\s+(?:will\s+be\s+)?(?:tested|analyzed)\s+at\s+(?:the\s+)?(\d+)\s*%',
        r'one[- ]?sided\s+(\d+)\s*%\s+(?:for|level)',
        r'primary[:\s]+.+?(\d+)\s*%',
        r'secondary[:\s]+.+?(\d+)\s*%',
        r'exploratory\s+(?:nature|endpoint)',
    ]

    def extract_diary_data_rules(self, protocol_text: str) -> DiaryDataRules:
        """Extract diary data calculation rules."""
        rules = DiaryDataRules()

        # Find days to average
        for pattern in self.DIARY_PATTERNS:
            match = re.search(pattern, protocol_text, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    rules.days_to_average = f"{groups[0]}-{groups[1]}"
                    rules.minimum_days = int(groups[0])
                elif len(groups) == 1:
                    rules.minimum_days = int(groups[0])
                break

        # Find exclusion rules
        for pattern in self.DIARY_EXCLUSION_PATTERNS:
            match = re.search(pattern, protocol_text, re.IGNORECASE)
            if match:
                rules.exclusion_rules.append(match.group(0))

        # Check for handling of insufficient data
        insufficient_match = re.search(
            r'(?:if\s+)?(?:fewer|less)\s+than\s+(\d+)\s+days?[^.]*?(?:treated\s+as|considered)\s+(\w+)',
            protocol_text,
            re.IGNORECASE
        )
        if insufficient_match:
            rules.handling_if_insufficient = f"treated as {insufficient_match.group(2)}"

        return rules

    def extract_pk_analysis_spec(self, protocol_text: str) -> PKAnalysisSpec:
        """Extract PK analysis specifications."""
        spec = PKAnalysisSpec()

        # Find PK parameters
        for pattern in self.PK_PARAMETER_PATTERNS:
            matches = re.findall(pattern, protocol_text, re.IGNORECASE)
            for match in matches:
                param = match if isinstance(match, str) else match[0]
                if param and param not in spec.parameters:
                    spec.parameters.append(param)

        # Also look for listed parameters
        param_list_match = re.search(
            r'(?:PK\s+)?parameters?[:\s]+(.+?)(?:\.|will\s+be)',
            protocol_text,
            re.IGNORECASE
        )
        if param_list_match:
            params = re.split(r'[,;]\s*', param_list_match.group(1))
            for p in params:
                p = p.strip()
                if p and len(p) < 20 and p not in spec.parameters:
                    spec.parameters.append(p)

        # Find software
        software_match = re.search(
            r'(WinNonlin|Phoenix|NONMEM|Monolix|R|SAS)[^\w]*(?:V|version)?[^\w]*(\d+\.?\d*)?',
            protocol_text,
            re.IGNORECASE
        )
        if software_match:
            version = software_match.group(2) or ""
            spec.software = f"{software_match.group(1)} {version}".strip()

        # Find method
        if re.search(r'non[- ]?compartmental|NCA', protocol_text, re.IGNORECASE):
            spec.method = "Non-compartmental analysis (NCA)"
        elif re.search(r'population\s+PK|popPK', protocol_text, re.IGNORECASE):
            spec.method = "Population PK modeling"

        # Extract sampling windows
        spec.sampling_windows = self._extract_pk_windows(protocol_text)

        return spec

    def _extract_pk_windows(self, protocol_text: str) -> List[PKSamplingWindow]:
        """Extract PK sampling timepoint windows."""
        windows = []

        # Pattern: "0h: within 1h pre-dose" or "2h post: ±10 min"
        window_matches = re.findall(
            r'(\d+(?:\.\d+)?)\s*h(?:our)?s?\s*(?:post)?[:\s]+(?:within\s+)?([±]?\s*\d+)\s*(h|min)',
            protocol_text,
            re.IGNORECASE
        )

        for timepoint, window, unit in window_matches:
            windows.append(PKSamplingWindow(
                timepoint=f"{timepoint}h",
                target_time=f"{timepoint}h post-dose",
                window_minus=f"{window.replace('±', '').strip()} {unit}",
                window_plus=f"{window.replace('±', '').strip()} {unit}"
            ))

        # Pre-dose window
        predose_match = re.search(
            r'pre[- ]?dose[:\s]+(?:within\s+)?(\d+)\s*(h|min)',
            protocol_text,
            re.IGNORECASE
        )
        if predose_match:
            windows.insert(0, PKSamplingWindow(
                timepoint="0h",
                target_time="Pre-dose",
                window_minus=f"{predose_match.group(1)} {predose_match.group(2)}",
                window_plus="0",
                notes="Before dosing"
            ))

        return windows

    def extract_scoring_modifications(self, protocol_text: str) -> List[ScoringModification]:
        """Extract any modified scoring criteria."""
        modifications = []

        # Look for explicit modification statements
        mod_match = re.search(
            r'(?:the\s+)?(\w+\s+(?:sub)?score)[^.]*(?:is\s+)?modified\s+so\s+that\s+(?:a\s+)?(?:value\s+of\s+)?(\d+)\s+does\s+NOT\s+include\s+(\w+)',
            protocol_text,
            re.IGNORECASE
        )
        if mod_match:
            modifications.append(ScoringModification(
                score_name=mod_match.group(1),
                modification=f"Value of {mod_match.group(2)} does NOT include {mod_match.group(3)}",
                original_criteria=f"Standard: {mod_match.group(2)} includes {mod_match.group(3)}",
                modified_criteria=f"Modified: {mod_match.group(2)} excludes {mod_match.group(3)}",
                source_section="Protocol scoring criteria"
            ))

        # Look for "DIFFERENT from original" statements
        different_match = re.search(
            r'criteria[^.]*(?:are|is)\s+DIFFERENT\s+from\s+(?:the\s+)?original[^.]*\.([^.]+\.)',
            protocol_text,
            re.IGNORECASE
        )
        if different_match:
            modifications.append(ScoringModification(
                score_name="Endoscopic scoring",
                modification=different_match.group(1).strip(),
                original_criteria="Original Mayo endoscopic criteria",
                modified_criteria=different_match.group(1).strip(),
                source_section="Protocol Table footnote"
            ))

        return modifications

    def extract_withdrawal_criteria(self, protocol_text: str) -> List[WithdrawalCriteria]:
        """Extract patient withdrawal/worsening criteria."""
        criteria = []

        # Look for worsening definition
        worsening_match = re.search(
            r'(?:worsening|deterioration)[^.]*increase\s+in\s+(\w+\s+subscore)\s*[≥>]\s*(\d+)[^.]*(?:from\s+)?(?:last\s+)?visit',
            protocol_text,
            re.IGNORECASE
        )
        if worsening_match:
            criteria.append(WithdrawalCriteria(
                criterion=f"Increase in {worsening_match.group(1)}",
                threshold=f"≥{worsening_match.group(2)} from last visit",
                confirmation_required="",
                handling_in_analysis="Included in ITT, excluded from PP if major deviation"
            ))

        # Look for consecutive days requirement
        consecutive_match = re.search(
            r'over\s+(\d+)\s+consecutive\s+days?',
            protocol_text,
            re.IGNORECASE
        )
        if consecutive_match and criteria:
            criteria[-1].threshold += f" over {consecutive_match.group(1)} consecutive days"

        # Look for confirmation requirement
        confirm_match = re.search(
            r'confirmed\s+by\s+(\w+)',
            protocol_text,
            re.IGNORECASE
        )
        if confirm_match and criteria:
            criteria[-1].confirmation_required = f"Confirmed by {confirm_match.group(1)}"

        return criteria

    def extract_subgroup_specs(self, protocol_text: str) -> List[SubgroupSpec]:
        """Extract biomarker subgroup analysis specifications."""
        specs = []

        # Look for subgroup split by biomarker
        subgroup_match = re.search(
            r'(?:split|divided)\s+into\s+subgroups?\s+based\s+on\s+(?:baseline\s+)?(?:level\s+of\s+)?([A-Za-z0-9/\-]+)',
            protocol_text,
            re.IGNORECASE
        )
        if subgroup_match:
            biomarker = subgroup_match.group(1)

            # Determine cutoff method
            cutoff_method = "median"  # default
            if re.search(r'median\s+(?:split|cut)', protocol_text, re.IGNORECASE):
                cutoff_method = "median split"
            elif re.search(r'tertile', protocol_text, re.IGNORECASE):
                cutoff_method = "tertiles"
            elif re.search(r'quartile', protocol_text, re.IGNORECASE):
                cutoff_method = "quartiles"

            specs.append(SubgroupSpec(
                biomarker=biomarker,
                cutoff_method=cutoff_method,
                subgroups=["High", "Low"] if cutoff_method == "median split" else [],
                analysis_approach="Same as primary analysis within each subgroup"
            ))

        return specs

    def extract_sensitivity_analyses(self, protocol_text: str) -> List[SensitivityAnalysis]:
        """Extract sensitivity analysis specifications."""
        analyses = []

        # Common sensitivity analysis patterns
        sensitivity_keywords = {
            'per-protocol': ('Per-Protocol Analysis', 'Analysis on PP population'),
            'LOCF': ('LOCF Imputation', 'Last observation carried forward'),
            'BOCF': ('BOCF Imputation', 'Baseline observation carried forward'),
            'multiple imputation': ('Multiple Imputation', 'MI for missing data'),
            'MMRM': ('MMRM', 'Mixed model repeated measures'),
            'tipping point': ('Tipping Point Analysis', 'Assess impact of missing data assumptions'),
            'as observed': ('As Observed', 'Complete cases only'),
        }

        for keyword, (name, description) in sensitivity_keywords.items():
            if re.search(keyword, protocol_text, re.IGNORECASE):
                # Check if it's mentioned as sensitivity
                context = re.search(
                    rf'(?:sensitivity|supportive)[^.]*{keyword}|{keyword}[^.]*(?:sensitivity|supportive)',
                    protocol_text,
                    re.IGNORECASE
                )
                if context:
                    analyses.append(SensitivityAnalysis(
                        name=name,
                        description=description,
                        differs_from_primary=f"Uses {keyword} instead of primary approach"
                    ))

        return analyses

    def extract_alpha_assignments(self, protocol_text: str) -> Dict[str, Dict]:
        """Extract which endpoints use which alpha levels."""
        assignments = {
            'primary_alpha': 0.05,
            'secondary_alpha': 0.05,
            'exploratory_alpha': 0.20,
            'sidedness': 'one-sided',
            'rationale': '',
        }

        # Check if exploratory/proof-of-concept
        if re.search(r'exploratory\s+(?:nature|study|trial)|proof[- ]?of[- ]?concept',
                     protocol_text, re.IGNORECASE):
            assignments['rationale'] = "Exploratory/proof-of-concept study"

        # Find specific alpha mentions
        alpha_20_match = re.search(r'one[- ]?sided\s+20\s*%', protocol_text, re.IGNORECASE)
        alpha_5_match = re.search(r'one[- ]?sided\s+5\s*%', protocol_text, re.IGNORECASE)

        if alpha_20_match and alpha_5_match:
            assignments['exploratory_alpha'] = 0.20
            assignments['primary_alpha'] = 0.05
            # Check which is used for what
            both_match = re.search(
                r'(?:tested|performed)\s+(?:both\s+)?at\s+(?:the\s+)?one[- ]?sided\s+20\s*%\s+and\s+(?:the\s+)?one[- ]?sided\s+5\s*%',
                protocol_text,
                re.IGNORECASE
            )
            if both_match:
                assignments['rationale'] += "; Testing at both 20% and 5% levels"

        return assignments

    def extract_visit_schedule(self, protocol_text: str) -> Dict[str, Dict]:
        """Extract complete visit schedule with windows."""
        schedule = {}

        # Pattern for "Week X / Day Y" or "Week X (Day Y)"
        visit_matches = re.findall(
            r'(?:Week|Visit)\s*(\d+)[^\n]*?Day\s*(\d+)\s*(?:[±]\s*(\d+)|[\(]Days?\s*(\d+)[-–](\d+)[\)])?',
            protocol_text,
            re.IGNORECASE
        )

        for match in visit_matches:
            week = match[0]
            target_day = int(match[1])

            if match[2]:  # ± format
                window = int(match[2])
                min_day = target_day - window
                max_day = target_day + window
            elif match[3] and match[4]:  # (Days X-Y) format
                min_day = int(match[3])
                max_day = int(match[4])
                window = (max_day - min_day) // 2
            else:
                window = 0
                min_day = target_day
                max_day = target_day

            schedule[f"Week {week}"] = {
                'target_day': target_day,
                'window': f"±{window}" if window else "exact",
                'min_day': min_day,
                'max_day': max_day,
                'acceptable_range': f"Days {min_day}-{max_day}"
            }

        return schedule

    def extract_all_clinical_details(self, protocol_text: str) -> Dict[str, Any]:
        """
        Master extraction method for all clinical trial-specific details.
        """
        return {
            'diary_data_rules': self.extract_diary_data_rules(protocol_text),
            'pk_analysis_spec': self.extract_pk_analysis_spec(protocol_text),
            'scoring_modifications': self.extract_scoring_modifications(protocol_text),
            'withdrawal_criteria': self.extract_withdrawal_criteria(protocol_text),
            'subgroup_specs': self.extract_subgroup_specs(protocol_text),
            'sensitivity_analyses': self.extract_sensitivity_analyses(protocol_text),
            'alpha_assignments': self.extract_alpha_assignments(protocol_text),
            'visit_schedule': self.extract_visit_schedule(protocol_text),
        }
