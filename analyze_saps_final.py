#!/usr/bin/env python3
"""
Final SAP structure analysis with improved phase detection
"""
import re
from pathlib import Path
from collections import defaultdict
import json

SAP_DIR = "/mnt/c/Users/vijay/Desktop/sap_data/ground_truth"

def extract_toc_sections(text):
    """Extract sections from Table of Contents"""
    lines = text.split('\n')[:300]  # Expand ToC search
    sections = []
    
    for line in lines:
        line = line.strip()
        
        # Multiple patterns for ToC entries
        patterns = [
            r'^(\d+)\.\s+([A-Z][^\.]{5,80})\.{2,}',  # "1. INTRODUCTION....12"
            r'^(\d+)\s+([A-Z][^\.]{5,80})\.{2,}',    # "1 INTRODUCTION....12"
            r'^(\d+)\.\s+([A-Z][A-Z\s]{5,80})\s*\d+$',  # "1. INTRODUCTION  12"
        ]
        
        for pattern in patterns:
            match = re.match(pattern, line)
            if match:
                num = match.group(1)
                title = match.group(2).strip()
                sections.append(title)
                break
    
    return sections

def normalize_section(title):
    """Normalize section title"""
    lower = title.lower().strip()
    
    mappings = {
        'introduction': ['introduction', 'background', 'purpose'],
        'objectives': ['objective', 'study objective', 'study aim'],
        'endpoints': ['endpoint', 'outcome', 'efficacy variable', 'primary endpoint'],
        'study_design': ['study design', 'study plan', 'overall study design'],
        'statistical_methods': ['statistical method', 'statistical analysis', 'analysis method'],
        'sample_size': ['sample size', 'determination of sample', 'sample size justification'],
        'analysis_populations': ['analysis set', 'analysis population', 'study population'],
        'interim_analysis': ['interim analys'],
        'safety': ['safety analys', 'safety assessment', 'safety evaluation', 'safety variable'],
        'efficacy': ['efficacy analys', 'efficacy assessment', 'efficacy evaluation'],
        'multiplicity': ['multiplicity'],
        'missing_data': ['missing data', 'missing value', 'handling of missing'],
        'randomization': ['randomi'],
        'biomarkers': ['biomarker'],
        'qol': ['quality of life', 'qol'],
        'appendices': ['appendix', 'appendices']
    }
    
    for standard, variants in mappings.items():
        for variant in variants:
            if variant in lower:
                return standard
    
    return lower[:30].replace(' ', '_')

def detect_phase_improved(text, filename):
    """Improved phase detection"""
    # Search in first 2000 chars (cover page + intro)
    search_text = text[:2000].lower()
    
    # More specific patterns
    phase_patterns = {
        'phase_3': [
            r'phase\s*iii\s+study',
            r'phase\s*3\s+study', 
            r'phase\s*iii\s+trial',
            r'phase\s*3\s+trial',
            r'phase\s*iii\s*,',
            r'phase\s*3\s*,',
            r'development\s+phase\s*:\s*phase\s*iii',
            r'development\s+phase\s*:\s*phase\s*3',
        ],
        'phase_2': [
            r'phase\s*ii\s+study',
            r'phase\s*2\s+study',
            r'phase\s*ii\s+trial',
            r'phase\s*2\s+trial',
            r'phase\s*ii\s*,',
            r'phase\s*2\s*,',
            r'development\s+phase\s*:\s*phase\s*ii',
            r'development\s+phase\s*:\s*phase\s*2',
        ],
        'phase_1': [
            r'phase\s*i\s+study',
            r'phase\s*1\s+study',
            r'phase\s*i\s+trial',
            r'phase\s*1\s+trial',
            r'phase\s*i\s*,',
            r'phase\s*1\s*,',
            r'development\s+phase\s*:\s*phase\s*i\b',
            r'development\s+phase\s*:\s*phase\s*1\b',
        ]
    }
    
    # Check each phase
    for phase, patterns in phase_patterns.items():
        for pattern in patterns:
            if re.search(pattern, search_text):
                # Distinguish Phase 2 single-arm vs randomized
                if phase == 'phase_2':
                    if 'randomis' in search_text or 'randomiz' in search_text:
                        return 'phase_2_randomized'
                    else:
                        return 'phase_2_single_arm'
                return phase
    
    return 'unknown'

def main():
    sap_files = sorted(Path(SAP_DIR).glob("*_sap.txt"))
    
    results = defaultdict(lambda: defaultdict(int))
    phase_counts = defaultdict(int)
    all_data = []
    
    print(f"Analyzing {len(sap_files)} SAPs...\n")
    print(f"{'Filename':<35} {'Phase':<25} {'Sections'}")
    print("="*80)
    
    for sap_file in sap_files:
        with open(sap_file, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        
        phase = detect_phase_improved(text, sap_file.name)
        sections = extract_toc_sections(text)
        normalized = [normalize_section(s) for s in sections]
        
        print(f"{sap_file.name:<35} {phase:<25} {len(sections)}")
        
        phase_counts[phase] += 1
        
        for norm_section in normalized:
            results[phase][norm_section] += 1
        
        all_data.append({
            'file': sap_file.name,
            'phase': phase,
            'sections': normalized
        })
    
    # Save results
    with open('sap_analysis_final.json', 'w') as f:
        json.dump({
            'phase_counts': dict(phase_counts),
            'section_frequencies': {p: dict(s) for p, s in results.items()},
            'all_saps': all_data
        }, f, indent=2)
    
    # Generate report
    print("\n" + "="*80)
    print("PHASE DISTRIBUTION")
    print("="*80)
    total = len(sap_files)
    for phase, count in sorted(phase_counts.items(), key=lambda x: -x[1]):
        pct = count / total * 100
        bar = "█" * int(pct / 2)
        print(f"{phase:<25} {count:3} ({pct:5.1f}%) {bar}")
    
    print("\n" + "="*80)
    print("SECTION FREQUENCY BY PHASE (TOP 15)")
    print("="*80)
    
    for phase in ['phase_1', 'phase_2_single_arm', 'phase_2_randomized', 'phase_3']:
        if phase not in results or phase_counts[phase] < 3:
            continue
        
        n = phase_counts[phase]
        print(f"\n{phase.upper().replace('_', ' ')} (n={n})")
        print("-" * 70)
        
        sorted_sections = sorted(results[phase].items(), key=lambda x: -x[1])
        
        for section, count in sorted_sections[:15]:
            pct = count / n * 100
            bar = "█" * int(pct / 5)
            marker = "✅" if pct >= 80 else "⚠️" if pct >= 50 else "  "
            print(f"{marker} {section:<30} {count:3}/{n} ({pct:5.1f}%) {bar}")
    
    # Summary recommendation
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    print(f"\nTotal SAPs analyzed: {total}")
    print(f"Successfully phased: {total - phase_counts['unknown']} ({(total-phase_counts['unknown'])/total*100:.1f}%)")
    print(f"\nResults saved to: sap_analysis_final.json")

if __name__ == "__main__":
    main()
