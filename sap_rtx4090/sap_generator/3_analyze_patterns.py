#!/usr/bin/env python3
"""
Step 3: Analyze Patterns and Variance
Determines if fixed template or adaptive approach is needed
"""

import json
import yaml
from collections import Counter, defaultdict
import numpy as np

def load_config():
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

def calculate_variance(structures_by_type):
    """Calculate structural variance within and between study types"""
    
    results = {}
    
    for study_type, structures in structures_by_type.items():
        # Get all section names
        all_sections = []
        for s in structures:
            all_sections.extend(s['section_names'])
        
        # Section frequency
        section_freq = Counter(all_sections)
        total_saps = len(structures)
        
        # Calculate consistency score
        # Score = how often sections appear across SAPs (0-1)
        consistency_scores = {
            section: count / total_saps 
            for section, count in section_freq.items()
        }
        
        # Core sections (appear in >80% of SAPs)
        core_sections = [s for s, score in consistency_scores.items() if score > 0.8]
        
        # Variable sections (20-80%)
        variable_sections = [s for s, score in consistency_scores.items() if 0.2 <= score <= 0.8]
        
        # Rare sections (<20%)
        rare_sections = [s for s, score in consistency_scores.items() if score < 0.2]
        
        results[study_type] = {
            'total_saps': total_saps,
            'unique_sections': len(section_freq),
            'core_sections': core_sections,
            'variable_sections': variable_sections,
            'rare_sections': rare_sections,
            'section_frequency': dict(section_freq),
            'consistency_scores': consistency_scores
        }
    
    return results

def detect_patterns(variance_results):
    """Detect which pattern the data follows"""
    
    # Pattern A: Low Variance (most SAPs similar)
    # Pattern B: Moderate Variance (clusters by study type)
    # Pattern C: High Variance (snowflakes)
    
    patterns = {}
    
    for study_type, data in variance_results.items():
        core_pct = len(data['core_sections']) / data['unique_sections'] if data['unique_sections'] > 0 else 0
        variable_pct = len(data['variable_sections']) / data['unique_sections'] if data['unique_sections'] > 0 else 0
        
        # Determine pattern
        if core_pct > 0.6:
            pattern = 'LOW_VARIANCE'
            recommendation = 'Fixed template with minor conditionals'
        elif core_pct > 0.4:
            pattern = 'MODERATE_VARIANCE'
            recommendation = 'Template library (2-4 templates)'
        else:
            pattern = 'HIGH_VARIANCE'
            recommendation = 'Requirements-based (Homer + Gamble)'
        
        patterns[study_type] = {
            'pattern': pattern,
            'core_percentage': core_pct,
            'variable_percentage': variable_pct,
            'recommendation': recommendation
        }
    
    return patterns

def analyze_patterns():
    """Main analysis function"""
    
    print("=" * 80)
    print("STEP 3: ANALYZING PATTERNS")
    print("=" * 80)
    
    config = load_config()
    output_dir = config['output_dir']
    
    # Load structures
    structures_file = f"{output_dir}/structures.json"
    
    try:
        with open(structures_file, 'r') as f:
            structures_by_type = json.load(f)
    except FileNotFoundError:
        print("❌ structures.json not found! Run 2_extract_structure.py first.")
        return
    
    print("\n📊 Calculating variance...")
    variance_results = calculate_variance(structures_by_type)
    
    print("\n🔍 Detecting patterns...")
    patterns = detect_patterns(variance_results)
    
    # Save analysis
    analysis = {
        'variance': variance_results,
        'patterns': patterns
    }
    
    analysis_file = f"{output_dir}/analysis.json"
    with open(analysis_file, 'w') as f:
        json.dump(analysis, f, indent=2)
    
    print(f"💾 Saved analysis to: {analysis_file}")
    
    # Print summary
    print("\n" + "=" * 80)
    print("📋 PATTERN DETECTION RESULTS")
    print("=" * 80)
    
    for study_type, pattern_data in patterns.items():
        print(f"\n{study_type.upper()}:")
        print(f"  Pattern: {pattern_data['pattern']}")
        print(f"  Core sections: {pattern_data['core_percentage']:.1%}")
        print(f"  Variable sections: {pattern_data['variable_percentage']:.1%}")
        print(f"  📍 Recommendation: {pattern_data['recommendation']}")
    
    # Overall recommendation
    print("\n" + "=" * 80)
    print("🎯 OVERALL RECOMMENDATION")
    print("=" * 80)
    
    pattern_counts = Counter(p['pattern'] for p in patterns.values())
    dominant_pattern = pattern_counts.most_common(1)[0][0]
    
    if dominant_pattern == 'LOW_VARIANCE':
        print("\n✅ Pattern A: LOW VARIANCE")
        print("   Most SAPs are structurally similar")
        print("   👉 RECOMMENDATION: Fixed template with conditionals")
        print("   📝 Implementation: 1 template + study-type conditionals")
        print("   ⏱️  Time: 3 weeks")
        
    elif dominant_pattern == 'MODERATE_VARIANCE':
        print("\n✅ Pattern B: MODERATE VARIANCE")
        print("   SAPs cluster into distinct structural types")
        print("   👉 RECOMMENDATION: Template library (3-4 templates)")
        print("   📝 Implementation: Separate templates per study type")
        print("   ⏱️  Time: 4-5 weeks")
        
    else:
        print("\n⚠️  Pattern C: HIGH VARIANCE")
        print("   Every SAP has unique structure")
        print("   👉 RECOMMENDATION: Requirements-based (Homer + Gamble)")
        print("   📝 Implementation: Full requirements engine")
        print("   ⏱️  Time: 10-12 weeks")
    
    print("\n" + "=" * 80)
    print("✅ PATTERN ANALYSIS COMPLETE")
    print("=" * 80)

if __name__ == '__main__':
    analyze_patterns()
