#!/usr/bin/env python3
"""
Generate Affinity Map from Lecture Transcripts
Creates concept clusters for the Related Concepts card
"""

import json
import boto3
from pathlib import Path
from typing import List, Dict
from collections import defaultdict

class AffinityMapGenerator:
    """Generate affinity map from lecture content"""
    
    def __init__(self, model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"):
        self.bedrock = boto3.client('bedrock-runtime')
        self.model_id = model_id
    
    def extract_concepts_from_lectures(self, lecture_dir: str = "data/canvas_extracted_512") -> List[str]:
        """Extract all concepts mentioned in lectures"""
        
        lecture_path = Path(lecture_dir)
        all_text = []
        
        print(f"Reading lectures from {lecture_dir}...")
        for file in lecture_path.glob("*.txt"):
            with open(file, 'r') as f:
                all_text.append(f.read())
        
        combined_text = "\n\n".join(all_text)
        print(f"Loaded {len(all_text)} lecture files")
        
        # Use Claude to extract concepts
        prompt = f"""Analyze these lecture transcripts and extract all UX/design concepts mentioned.

Lecture content (first 5000 chars):
{combined_text[:5000]}

Extract a comprehensive list of concepts, methods, and topics covered. Include:
- Design methods (e.g., "user interviews", "wireframing")
- Concepts (e.g., "information architecture", "usability")
- Tools and deliverables (e.g., "personas", "journey maps")
- Principles (e.g., "user-centered design", "accessibility")

Return ONLY a JSON array of concept strings:
["concept1", "concept2", ...]

Aim for 50-100 concepts.
"""
        
        try:
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                })
            )
            
            content = json.loads(response['body'].read())['content'][0]['text']
            json_start = content.find('[')
            json_end = content.rfind(']') + 1
            concepts = json.loads(content[json_start:json_end])
            
            print(f"Extracted {len(concepts)} concepts")
            return concepts
            
        except Exception as e:
            print(f"Error extracting concepts: {e}")
            return []
    
    def cluster_concepts(self, concepts: List[str]) -> List[Dict]:
        """Group concepts into clusters using Claude"""
        
        print("\nClustering concepts...")
        
        prompt = f"""Group these UX/design concepts into 8-12 thematic clusters.

Concepts:
{json.dumps(concepts, indent=2)}

For each cluster:
1. Choose a central concept that represents the theme
2. Group 5-10 related concepts
3. Identify 1-2 related clusters (by name)

Return ONLY valid JSON:
[
  {{
    "cluster_id": "research_methods",
    "central_concept": "User Research",
    "concepts": ["user interviews", "surveys", "usability testing", ...],
    "related_clusters": ["personas", "data_analysis"]
  }}
]

Create 8-12 clusters total.
"""
        
        try:
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 3000,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                })
            )
            
            content = json.loads(response['body'].read())['content'][0]['text']
            json_start = content.find('[')
            json_end = content.rfind(']') + 1
            clusters = json.loads(content[json_start:json_end])
            
            print(f"Created {len(clusters)} clusters")
            return clusters
            
        except Exception as e:
            print(f"Error clustering concepts: {e}")
            return []
    
    def generate_affinity_map(self, output_path: str = "data/affinity_map.json"):
        """Generate complete affinity map"""
        
        print("="*60)
        print("GENERATING AFFINITY MAP")
        print("="*60)
        
        # Step 1: Extract concepts
        concepts = self.extract_concepts_from_lectures()
        
        if not concepts:
            print("❌ Failed to extract concepts")
            return
        
        # Step 2: Cluster concepts
        clusters = self.cluster_concepts(concepts)
        
        if not clusters:
            print("❌ Failed to cluster concepts")
            return
        
        # Step 3: Create affinity map structure
        affinity_map = {
            "version": "1.0",
            "generated_from": "lecture transcripts",
            "total_concepts": len(concepts),
            "total_clusters": len(clusters),
            "clusters": clusters
        }
        
        # Step 4: Save to file
        with open(output_path, 'w') as f:
            json.dump(affinity_map, f, indent=2)
        
        print(f"\n✓ Affinity map saved to {output_path}")
        
        # Step 5: Print summary
        print("\n" + "="*60)
        print("AFFINITY MAP SUMMARY")
        print("="*60)
        print(f"Total concepts: {len(concepts)}")
        print(f"Total clusters: {len(clusters)}")
        print("\nClusters:")
        for cluster in clusters:
            print(f"  • {cluster['central_concept']} ({len(cluster['concepts'])} concepts)")
        
        return affinity_map


def main():
    print("Starting affinity map generation...\n")
    
    generator = AffinityMapGenerator()
    affinity_map = generator.generate_affinity_map()
    
    if affinity_map:
        print("\n✓ Affinity map generation complete!")
        print("\nNext steps:")
        print("  1. Review data/affinity_map.json")
        print("  2. Re-deploy to EC2 (it will be included automatically)")
        print("  3. Related Concepts card will now show suggestions")
    else:
        print("\n❌ Affinity map generation failed")


if __name__ == "__main__":
    main()
