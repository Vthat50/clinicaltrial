#!/usr/bin/env python3
"""
Analyze all 116 ground_truth SAPs - IMPROVED VERSION
"""
import os
import re
import json
from collections import defaultdict
from pathlib import Path

SAP_DIR = "/mnt/c/Users/vijay/Desktop/sap_data/ground_truth"
OUTPUT_FILE = "sap_structure_analysis_v2.json"
REPORT_FILE = "sap_structure_report_v2.md"

def extract_sections(text):
    """Extract sections - IMPROVED regex"""
    sections = []
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # Try multiple patterns
        patterns = [
            r'^(\d+)\.\s+([A-Z][A-Z\s/&\-()]+)$',  # "1. INTRODUCTION"
            r'^(\d+)\.\s+([A-Z][a-z].{5,80})$',     # "1. Introduction to Study"
            r'^(\d+\.\d+)\s+([A-Z].{5,80})$',       # "1.1 Study Objectives"
        ]
        
        for pattern in patterns:
            match = re.match(pattern, line)
            if match:
                section_num = match.group(1)
                section_title = match.group(2).strip()
                
                # Skip if title is too long (likely not a section)
                if len(section_title) > 100:
                    continue
                
                # Skip subsections (only want top-level)
                if '.' in section_num and len(section_num) > 2:
                    continue
                
                sections.append({
                    'number': section_num,
                    'title': section_title,
                    'line': i
                })
                break
    
    return sections

def normalize_section_title(title):
    """Normalize section titles"""
    title_lower = title.lower().strip()
    
    mappings = {
        'introduction': ['introduction', 'background', 'purpose'],
        'objectives': ['objective', 'study objective'],
        'endpoints': ['endpoint', 'end point', 'outcome'],
        'study_design': ['study design', 'design', 'study plan'],
        'statistical_methods': ['statistical method', 'statistical analysis', 'analysis method'],
        'statistical_analysis_strategy': ['statistical analysis strategy', 'analysis strategy'],
        'sample_size': ['sample size', 'determination of sample size', 'sample size justification'],
        'analysis_sets': ['analysis set', 'population', 'analysis population'],
        'interim_analysis': ['interim analys'],
        'safety': ['safety analys', 'safety endpoint'],
        'efficacy': ['efficacy analys'],
        'multiplicity': ['multiplicity'],
        'missing_data': ['missing data', 'handling of missing'],
        'randomisation': ['randomis', 'randomiz'],
        'biomarkers': ['biomarker'],
        'qol': ['quality of life', 'qol'],
        'appendices': ['appendix', 'appendices']
    }
    
    for standard_name, variants in mappings.items():
        for variant in variants:
            if variant in title_lower:
                return standard_name
    
    # Return first 40 chars as fallback
    return title_lower.replace(' ', '_')[:40]

def detect_phase(text):
    """Improved phase detection"""
    text_lower = text[:5000].lower()  # First 5000 chars
    
    # Count indicators
    phase_indicators = {
        'phase_1': ['phase i study', 'phase 1 study', 'phase i trial', 'phase 1 trial',
                    'phase i,', 'phase 1,', 'phase i '],
        'phase_2': ['phase ii study', 'phase 2 study', 'phase ii trial', 'phase 2 trial',
                    'phase ii,', 'phase 2,', 'phase ii '],
        'phase_3': ['phase iii study', 'phase 3 study', 'phase iii trial', 'phase 3 trial',
                    'phase iii,', 'phase 3,', 'phase iii ']
    }
    
    phase_scores = defaultdict(int)
    for phase, indicators in phase_indicators.items():
        for indicator in indicators:
            phase_scores[phase] += text_lower.count(indicator)
    
    # Determine phase
    if phase_scores['phase_1'] > 0:
        detected_phase = 'phase_1'
    elif phase_scores['phase_3'] > 0:
        detected_phase = 'phase_3'
    elif phase_scores['phase_2'] > 0:
        # Check if randomized
        if 'randomis' in text_lower or 'randomiz' in text_lower:
            detected_phase = 'phase_2_randomized'
        else:
            detected_phase = 'phase_2_single_arm'
    else:
        return 'unknown'
    
    return detected_phase

def analyze_saps():
    """Analyze all 116 SAPs"""
    print(f"Analyzing SAPs in: {SAP_DIR}\n")
    
    sap_files = list(Path(SAP_DIR).glob("*_sap.txt"))
    print(f"Found {len(sap_files)} SAP files\n")
    
    results = {
        'total_saps': len(sap_files),
        'by_phase': defaultdict(list),
        'section_frequency': defaultdict(lambda: defaultdict(int)),
        'raw_data': []
    }
    
    processed = 0
    for sap_file in sorted(sap_files):
        processed += 1
        print(f"[{processed}/{len(sap_files)}] {sap_file.name}", end='')
        
        try:
            with open(sap_file, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
            
            sections = extract_sections(text)
            phase = detect_phase(text)
            normalized_sections = [normalize_section_title(s['title']) for s in sections]
            
            print(f" → {phase} ({len(sections)} sections)")
            
            sap_data = {
                'filename': sap_file.name,
                'phase': phase,
                'section_count': len(sections),
                'sections': normalized_sections
            }
            
            results['by_phase'][phase].append(sap_data)
            results['raw_data'].append(sap_data)
            
            for section in normalized_sections:
                results['section_frequency'][phase][section] += 1
        
        except Exception as e:
            print(f" ERROR: {e}")
    
    return results

def generate_report(results):
    """Generate report"""
    report = []
    report.append("# SAP Structure Analysis Report (v2)\n")
    report.append(f"**Total SAPs Analyzed:** {results['total_saps']}\n")
    
    # Phase distribution
    report.append("## Phase Distribution\n")
    report.append("| Phase | Count | Percentage |")
    report.append("|-------|-------|------------|")
    for phase, saps in sorted(results['by_phase'].items(), key=lambda x: -len(x[1])):
        pct = (len(saps) / results['total_saps']) * 100
        report.append(f"| {phase} | {len(saps)} | {pct:.1f}% |")
    
    # Section frequency by phase
    report.append("\n## Top Sections by Phase\n")
    
    for phase in ['phase_1', 'phase_2_randomized', 'phase_2_single_arm', 'phase_3']:
        if phase not in results['section_frequency']:
            continue
            
        phase_saps = len(results['by_phase'][phase])
        if phase_saps < 5:  # Skip if too few samples
            continue
        
        report.append(f"\n### {phase.upper().replace('_', ' ')} (n={phase_saps})\n")
        report.append("| Section | Count | % |")
        report.append("|---------|-------|---|")
        
        sections = results['section_frequency'][phase]
        sorted_sections = sorted(sections.items(), key=lambda x: x[1], reverse=True)
        
        for section, count in sorted_sections[:15]:
            pct = (count / phase_saps) * 100
            marker = "✅" if pct > 80 else "⚠️" if pct > 50 else ""
            report.append(f"| {section} | {count} | {pct:.0f}% {marker} |")
    
    # Core sections summary
    report.append("\n## Core Sections (>80% frequency)\n")
    
    for phase in ['phase_1', 'phase_2_randomized', 'phase_3']:
        if phase not in results['section_frequency']:
            continue
        
        phase_saps = len(results['by_phase'][phase])
        if phase_saps < 5:
            continue
        
        sections = results['section_frequency'][phase]
        core_sections = [(s, c) for s, c in sections.items() if c / phase_saps > 0.8]
        
        if core_sections:
            report.append(f"\n**{phase.upper().replace('_', ' ')}:**")
            for section, count in sorted(core_sections, key=lambda x: -x[1]):
                pct = (count / phase_saps) * 100
                report.append(f"- {section}: {pct:.0f}%")
        else:
            report.append(f"\n**{phase.upper().replace('_', ' ')}:** None")
    
    return '\n'.join(report)

def main():
    print("=" * 70)
    print("SAP STRUCTURE ANALYSIS v2 - IMPROVED EXTRACTION")
    print("=" * 70)
    print()
    
    results = analyze_saps()
    
    print(f"\n{'=' * 70}")
    print("Saving results...")
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"✓ JSON: {OUTPUT_FILE}")
    
    report = generate_report(results)
    with open(REPORT_FILE, 'w') as f:
        f.write(report)
    print(f"✓ Report: {REPORT_FILE}")
    
    print(f"{'=' * 70}\n")

if __name__ == "__main__":
    main()

