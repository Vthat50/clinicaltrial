#!/usr/bin/env python3
"""
Extract SAP structure from Table of Contents
"""
import re
from pathlib import Path
from collections import defaultdict
import json

SAP_DIR = "/mnt/c/Users/vijay/Desktop/sap_data/ground_truth"

def extract_toc_sections(text):
    """Extract sections from Table of Contents"""
    lines = text.split('\n')[:200]  # ToC is in first 200 lines
    sections = []
    
    for line in lines:
        line = line.strip()
        
        # Pattern: "1. INTRODUCTION ........ 12"
        # or: "3.1 Study Design........... 6"
        match = re.match(r'^(\d+(?:\.\d+)?)\s+(.+?)\.{2,}', line)
        if match:
            num = match.group(1)
            title = match.group(2).strip()
            
            # Only top-level sections (1., 2., 3., not 1.1, 1.2)
            if '.' not in num or num.count('.') == 1 and num.endswith('.0'):
                sections.append(title)
    
    return sections

def normalize_section(title):
    """Normalize section title"""
    lower = title.lower()
    
    if 'introduction' in lower or 'background' in lower:
        return 'introduction'
    elif 'objective' in lower:
        return 'objectives'
    elif 'endpoint' in lower or 'outcome' in lower:
        return 'endpoints'
    elif 'study design' in lower or 'study plan' in lower:
        return 'study_design'
    elif 'statistical method' in lower or 'statistical analysis' in lower:
        return 'statistical_methods'
    elif 'sample size' in lower:
        return 'sample_size'
    elif 'analysis set' in lower or 'population' in lower:
        return 'analysis_populations'
    elif 'interim' in lower:
        return 'interim_analysis'
    elif 'safety' in lower:
        return 'safety'
    elif 'efficacy' in lower:
        return 'efficacy'
    elif 'multiplicity' in lower:
        return 'multiplicity'
    elif 'missing' in lower:
        return 'missing_data'
    elif 'randomi' in lower:
        return 'randomization'
    elif 'biomarker' in lower:
        return 'biomarkers'
    elif 'quality of life' in lower or 'qol' in lower:
        return 'qol'
    elif 'appendix' in lower or 'appendices' in lower:
        return 'appendices'
    else:
        return lower[:30].replace(' ', '_')

def detect_phase(text):
    """Detect phase from title page"""
    first_500 = text[:500].lower()
    
    if 'phase iii' in first_500 or 'phase 3' in first_500:
        return 'phase_3'
    elif 'phase ii' in first_500 or 'phase 2' in first_500:
        if 'randomis' in text[:2000].lower() or 'randomiz' in text[:2000].lower():
            return 'phase_2_randomized'
        return 'phase_2_single_arm'
    elif 'phase i' in first_500 or 'phase 1' in first_500:
        return 'phase_1'
    
    return 'unknown'

def main():
    sap_files = sorted(Path(SAP_DIR).glob("*_sap.txt"))
    
    results = defaultdict(lambda: defaultdict(int))
    phase_counts = defaultdict(int)
    
    print(f"Analyzing {len(sap_files)} SAPs...\n")
    
    for sap_file in sap_files:
        with open(sap_file, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        
        phase = detect_phase(text)
        sections = extract_toc_sections(text)
        
        print(f"{sap_file.name:30} → {phase:20} ({len(sections)} sections)")
        
        phase_counts[phase] += 1
        
        for section in sections:
            normalized = normalize_section(section)
            results[phase][normalized] += 1
    
    # Generate report
    print("\n" + "="*70)
    print("PHASE DISTRIBUTION")
    print("="*70)
    for phase, count in sorted(phase_counts.items(), key=lambda x: -x[1]):
        pct = count / len(sap_files) * 100
        print(f"{phase:25} {count:3} ({pct:5.1f}%)")
    
    print("\n" + "="*70)
    print("TOP SECTIONS BY PHASE")
    print("="*70)
    
    for phase in ['phase_1', 'phase_2_single_arm', 'phase_2_randomized', 'phase_3']:
        if phase not in results or phase_counts[phase] < 5:
            continue
        
        print(f"\n{phase.upper().replace('_', ' ')} (n={phase_counts[phase]})")
        print("-" * 50)
        
        sorted_sections = sorted(results[phase].items(), key=lambda x: -x[1])
        
        for section, count in sorted_sections[:12]:
            pct = count / phase_counts[phase] * 100
            marker = "✅" if pct >= 80 else "⚠️" if pct >= 50 else ""
            print(f"  {section:30} {count:3} ({pct:5.1f}%) {marker}")

if __name__ == "__main__":
    main()
