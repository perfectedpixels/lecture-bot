#!/usr/bin/env python3
"""
View Portfolio Image Tags Summary
Quick overview of all tagged images
"""

import json
from collections import Counter

def main():
    with open('data/portfolio_image_metadata.json', 'r') as f:
        metadata = json.load(f)
    
    print("\n" + "="*70)
    print("PORTFOLIO IMAGE TAGGING SUMMARY")
    print("="*70)
    
    # Overall stats
    total_images = sum(len(p['images']) for p in metadata.values())
    all_concepts = []
    all_phases = []
    
    for project in metadata.values():
        for img in project['images']:
            all_concepts.extend(img.get('concept_tags', []))
            all_phases.append(img.get('phase', 'unknown'))
    
    print(f"\n📊 Overall Statistics:")
    print(f"   Projects: {len(metadata)}")
    print(f"   Images: {total_images}")
    print(f"   Unique concepts: {len(set(all_concepts))}")
    
    # Top concepts
    concept_counts = Counter(all_concepts)
    print(f"\n🏆 Top 10 Concept Tags:")
    for concept, count in concept_counts.most_common(10):
        print(f"   {count:3d}x  {concept}")
    
    # Phase distribution
    phase_counts = Counter(all_phases)
    print(f"\n📈 Phase Distribution:")
    for phase, count in sorted(phase_counts.items(), key=lambda x: -x[1]):
        print(f"   {count:3d}x  {phase}")
    
    # Project details
    print(f"\n" + "="*70)
    print("PROJECT DETAILS")
    print("="*70)
    
    for project_key, project_data in metadata.items():
        print(f"\n📁 {project_data['title'].upper()}")
        print(f"   Images: {len(project_data['images'])}")
        
        summary = project_data.get('summary', {})
        if summary.get('primary_concepts'):
            print(f"   Primary Concepts: {', '.join(summary['primary_concepts'])}")
        if summary.get('methodologies_used'):
            print(f"   Methodologies: {', '.join(summary['methodologies_used'])}")
        if summary.get('key_outcomes'):
            print(f"   Outcomes: {summary['key_outcomes'][:80]}...")
        
        # Show first image as example
        if project_data['images']:
            img = project_data['images'][0]
            print(f"   Example: {img['filename']}")
            print(f"     - {img.get('description', 'No description')[:60]}...")
            print(f"     - Tags: {', '.join(img.get('concept_tags', [])[:3])}")
    
    print(f"\n" + "="*70)
    print("✅ Tagging complete! Data saved in data/portfolio_image_metadata.json")
    print("="*70)

if __name__ == "__main__":
    main()
