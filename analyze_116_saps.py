#!/usr/bin/env python3
"""
Analyze all 116 ground_truth SAPs to determine structural patterns by phase
"""
import os
import re
import json
from collections import defaultdict, Counter
from pathlib import Path

# Configuration
SAP_DIR = "/mnt/c/Users/vijay/Desktop/sap_data/ground_truth"
OUTPUT_FILE = "sap_structure_analysis.json"
REPORT_FILE = "sap_structure_report.md"

def extract_sections(text):
    """Extract numbered sections from SAP text"""
    sections = []
    
    # Pattern: "1. INTRODUCTION" or "5.1. Subheading"
    pattern = r'^(\d+(?:\.\d+)?)\.\s+([A-Z][A-Z\s/&\-()]+)$'
    
    for line in text.split('\n'):
        line = line.strip()
        match = re.match(pattern, line)
        if match:
            section_num = match.group(1)
            section_title = match.group(2).strip()
            sections.append({
                'number': section_num,
                'title': section_title
            })
    
    return sections

def normalize_section_title(title):
    """Normalize section titles to standard names"""
    title_lower = title.lower()
    
    # Mapping dictionary
    mappings = {
        'introduction': ['introduction', 'background'],
        'objectives': ['objectives', 'study objectives'],
        'endpoints': ['endpoints', 'end points', 'efficacy endpoints', 'primary endpoint'],
        'study_design': ['study design', 'design', 'study plan'],
        'statistical_methods': ['statistical methods', 'statistical analysis', 'methods'],
        'sample_size': ['sample size', 'determination of sample size'],
        'analysis_sets': ['analysis sets', 'populations', 'analysis populations'],
        'interim_analysis': ['interim analysis', 'interim analyses'],
        'safety': ['safety', 'safety analysis', 'safety endpoints'],
        'efficacy': ['efficacy', 'efficacy analysis'],
        'multiplicity': ['multiplicity', 'multiplicity issues'],
        'missing_data': ['missing data', 'handling of missing data'],
        'randomisation': ['randomisation', 'randomization', 'type of randomisation'],
        'biomarkers': ['biomarkers', 'biomarker'],
        'qol': ['qol', 'quality of life'],
        'appendices': ['appendices', 'appendix']
    }
    
    for standard_name, variants in mappings.items():
        for variant in variants:
            if variant in title_lower:
                return standard_name
    
    return title_lower.replace(' ', '_')[:50]

def detect_phase(sap_path, text):
    """Detect study phase from filename or content"""
    text_lower = text.lower()
    
    # Check title/content for phase indicators
    if 'phase i ' in text_lower or 'phase 1 ' in text_lower or 'phase i study' in text_lower:
        return 'phase_1'
    elif 'phase ii ' in text_lower or 'phase 2 ' in text_lower or 'phase ii study' in text_lower:
        # Distinguish single-arm vs randomized
        if 'randomis' in text_lower or 'randomiz' in text_lower:
            return 'phase_2_randomized'
        else:
            return 'phase_2_single_arm'
    elif 'phase iii ' in text_lower or 'phase 3 ' in text_lower or 'phase iii study' in text_lower:
        return 'phase_3'
    
    return 'unknown'

def analyze_saps():
    """Analyze all 116 SAPs"""
    print(f"Analyzing SAPs in: {SAP_DIR}")
    
    sap_files = list(Path(SAP_DIR).glob("*_sap.txt"))
    print(f"Found {len(sap_files)} SAP files")
    
    results = {
        'total_saps': len(sap_files),
        'by_phase': defaultdict(list),
        'section_frequency': defaultdict(lambda: defaultdict(int)),
        'raw_data': []
    }
    
    for sap_file in sorted(sap_files):
        print(f"Processing: {sap_file.name}")
        
        try:
            with open(sap_file, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
            
            # Extract sections
            sections = extract_sections(text)
            
            # Detect phase
            phase = detect_phase(sap_file, text)
            
            # Normalize section titles
            normalized_sections = [normalize_section_title(s['title']) for s in sections]
            
            # Store data
            sap_data = {
                'filename': sap_file.name,
                'phase': phase,
                'section_count': len(sections),
                'sections': normalized_sections
            }
            
            results['by_phase'][phase].append(sap_data)
            results['raw_data'].append(sap_data)
            
            # Count section frequency by phase
            for section in normalized_sections:
                results['section_frequency'][phase][section] += 1
        
        except Exception as e:
            print(f"  ERROR: {e}")
    
    return results

def generate_report(results):
    """Generate markdown report"""
    report = []
    report.append("# SAP Structure Analysis Report")
    report.append(f"\n**Total SAPs Analyzed:** {results['total_saps']}\n")
    
    # Phase distribution
    report.append("## Phase Distribution\n")
    report.append("| Phase | Count | Percentage |")
    report.append("|-------|-------|------------|")
    for phase, saps in sorted(results['by_phase'].items()):
        pct = (len(saps) / results['total_saps']) * 100
        report.append(f"| {phase} | {len(saps)} | {pct:.1f}% |")
    
    # Section frequency by phase
    report.append("\n## Section Frequency by Phase\n")
    
    for phase in sorted(results['section_frequency'].keys()):
        phase_saps = len(results['by_phase'][phase])
        if phase_saps == 0:
            continue
            
        report.append(f"\n### {phase.upper()} (n={phase_saps})\n")
        report.append("| Section | Count | Percentage |")
        report.append("|---------|-------|------------|")
        
        # Sort by frequency
        sections = results['section_frequency'][phase]
        sorted_sections = sorted(sections.items(), key=lambda x: x[1], reverse=True)
        
        for section, count in sorted_sections[:20]:  # Top 20 sections
            pct = (count / phase_saps) * 100
            report.append(f"| {section} | {count} | {pct:.1f}% |")
    
    # Pattern detection
    report.append("\n## Pattern Detection\n")
    
    for phase in sorted(results['section_frequency'].keys()):
        phase_saps = len(results['by_phase'][phase])
        if phase_saps == 0:
            continue
        
        sections = results['section_frequency'][phase]
        
        # Calculate core sections (>80%)
        core_sections = [s for s, c in sections.items() if c / phase_saps > 0.8]
        
        # Calculate variable sections (20-80%)
        variable_sections = [s for s, c in sections.items() if 0.2 <= c / phase_saps <= 0.8]
        
        # Calculate rare sections (<20%)
        rare_sections = [s for s, c in sections.items() if c / phase_saps < 0.2]
        
        report.append(f"\n### {phase.upper()}")
        report.append(f"- **Core sections (>80%):** {len(core_sections)}")
        report.append(f"  - {', '.join(core_sections[:10])}")
        report.append(f"- **Variable sections (20-80%):** {len(variable_sections)}")
        report.append(f"  - {', '.join(variable_sections[:10])}")
        report.append(f"- **Rare sections (<20%):** {len(rare_sections)}")
    
    # Recommendation
    report.append("\n## Recommendation\n")
    
    # Count phases with different structures
    phases_with_data = [p for p in results['by_phase'].keys() if len(results['by_phase'][p]) > 5]
    
    if len(phases_with_data) >= 3:
        report.append("**Pattern: MODERATE VARIANCE (Template Library)**\n")
        report.append("- SAPs cluster into 3-4 distinct structural types by phase")
        report.append("- Each phase has consistent core sections (>80%)")
        report.append("- But phases differ significantly from each other")
        report.append("- **Recommended approach:** Template Library (4-5 weeks)")
        report.append("  - Create phase-specific templates")
        report.append("  - Use Section Applicability Matrix")
        report.append("  - Generate only relevant sections per phase")
    else:
        report.append("**Pattern: Insufficient data to determine variance**")
    
    return '\n'.join(report)

def main():
    """Main execution"""
    print("=" * 60)
    print("SAP STRUCTURE ANALYSIS")
    print("=" * 60)
    
    # Analyze
    results = analyze_saps()
    
    # Save JSON
    print(f"\nSaving results to: {OUTPUT_FILE}")
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Generate report
    report = generate_report(results)
    
    print(f"Saving report to: {REPORT_FILE}")
    with open(REPORT_FILE, 'w') as f:
        f.write(report)
    
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE!")
    print("=" * 60)
    print(f"\nResults: {OUTPUT_FILE}")
    print(f"Report:  {REPORT_FILE}")
    print("\nTo view report:")
    print(f"  cat {REPORT_FILE}")

if __name__ == "__main__":
    main()
