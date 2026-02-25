import boto3
import json
from typing import List, Dict, Set, Tuple
from collections import defaultdict
import numpy as np
from dataclasses import dataclass

@dataclass
class ConceptCluster:
    """Represents a cluster of related concepts"""
    cluster_id: str
    concepts: List[str]
    central_concept: str
    related_categories: Set[str]
    segment_count: int
    affinity_score: float

class AffinityMapper:
    """
    Creates affinity maps by clustering related concepts across all lectures.
    Uses Claude to understand semantic relationships between concepts.
    """
    
    def __init__(self, model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"):
        self.bedrock = boto3.client('bedrock-runtime')
        self.model_id = model_id
        self.concept_cooccurrence = defaultdict(lambda: defaultdict(int))
        self.concept_contexts = defaultdict(list)
    
    def build_cooccurrence_matrix(self, tagged_segments: List) -> Dict[str, Dict[str, int]]:
        """
        Build a matrix showing how often concepts appear together.
        """
        for segment in tagged_segments:
            concepts = [c.name for c in segment.concepts]
            
            # Record co-occurrence
            for i, concept1 in enumerate(concepts):
                for concept2 in concepts[i+1:]:
                    self.concept_cooccurrence[concept1][concept2] += 1
                    self.concept_cooccurrence[concept2][concept1] += 1
                
                # Store context for each concept
                self.concept_contexts[concept1].append({
                    'text': segment.text[:200],  # First 200 chars
                    'category': segment.primary_category
                })
        
        return dict(self.concept_cooccurrence)
    
    def find_related_concepts(self, concept: str, top_n: int = 5) -> List[Tuple[str, int]]:
        """
        Find concepts most frequently appearing with the given concept.
        """
        if concept not in self.concept_cooccurrence:
            return []
        
        related = self.concept_cooccurrence[concept]
        sorted_related = sorted(related.items(), key=lambda x: x[1], reverse=True)
        return sorted_related[:top_n]
    
    def create_semantic_clusters(self, all_concepts: List[str], num_clusters: int = 10) -> List[ConceptCluster]:
        """
        Use Claude to create semantic clusters of related concepts.
        This goes beyond co-occurrence to understand conceptual relationships.
        """
        
        # Get co-occurrence data for context
        cooccurrence_summary = {}
        for concept in all_concepts:
            related = self.find_related_concepts(concept, top_n=3)
            if related:
                cooccurrence_summary[concept] = [r[0] for r in related]
        
        prompt = f"""You are analyzing concepts from a series of lectures. Create {num_clusters} thematic clusters
that group related concepts together based on their semantic meaning and relationships.

Concepts to cluster:
{json.dumps(all_concepts, indent=2)}

Co-occurrence data (concepts that appear together):
{json.dumps(cooccurrence_summary, indent=2)}

For each cluster, provide:
1. A cluster_id (short, descriptive name like "ml_fundamentals")
2. List of concepts belonging to this cluster
3. The central_concept (most representative concept)
4. A brief description of what unifies this cluster

Return ONLY a JSON array in this format:
[
  {{
    "cluster_id": "cluster_name",
    "concepts": ["concept1", "concept2", ...],
    "central_concept": "main concept",
    "description": "what unifies these concepts"
  }}
]

Make clusters meaningful and balanced. Each concept should appear in only one cluster."""

        try:
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 3000,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.5
                })
            )
            
            response_body = json.loads(response['body'].read())
            content = response_body['content'][0]['text']
            
            # Extract JSON
            json_match = content[content.find('['):content.rfind(']')+1]
            clusters_data = json.loads(json_match)
            
            # Convert to ConceptCluster objects
            clusters = []
            for cluster_data in clusters_data:
                # Calculate affinity score based on co-occurrence
                affinity_score = self._calculate_cluster_affinity(cluster_data['concepts'])
                
                cluster = ConceptCluster(
                    cluster_id=cluster_data['cluster_id'],
                    concepts=cluster_data['concepts'],
                    central_concept=cluster_data['central_concept'],
                    related_categories=set(),  # Will be populated later
                    segment_count=0,  # Will be populated later
                    affinity_score=affinity_score
                )
                clusters.append(cluster)
            
            return clusters
            
        except Exception as e:
            print(f"Error creating clusters: {e}")
            return []
    
    def _calculate_cluster_affinity(self, concepts: List[str]) -> float:
        """
        Calculate how strongly concepts in a cluster are related.
        Based on co-occurrence frequency.
        """
        if len(concepts) < 2:
            return 0.0
        
        total_affinity = 0
        pair_count = 0
        
        for i, concept1 in enumerate(concepts):
            for concept2 in concepts[i+1:]:
                affinity = self.concept_cooccurrence.get(concept1, {}).get(concept2, 0)
                total_affinity += affinity
                pair_count += 1
        
        return total_affinity / pair_count if pair_count > 0 else 0.0
    
    def enrich_clusters_with_metadata(self, clusters: List[ConceptCluster], tagged_segments: List) -> List[ConceptCluster]:
        """
        Add category and segment count information to clusters.
        """
        for cluster in clusters:
            categories = set()
            segment_count = 0
            
            for segment in tagged_segments:
                segment_concepts = {c.name for c in segment.concepts}
                
                # Check if any cluster concept appears in this segment
                if any(concept in segment_concepts for concept in cluster.concepts):
                    segment_count += 1
                    categories.add(segment.primary_category)
            
            cluster.related_categories = categories
            cluster.segment_count = segment_count
        
        return clusters
    
    def get_cluster_for_query(self, query: str, clusters: List[ConceptCluster]) -> List[str]:
        """
        Given a user query, determine which concept clusters are most relevant.
        Returns cluster IDs ranked by relevance.
        """
        
        prompt = f"""Given this user query, identify which concept clusters are most relevant.

Query: {query}

Available clusters:
{json.dumps([{
    'cluster_id': c.cluster_id,
    'central_concept': c.central_concept,
    'concepts': c.concepts[:5]  # Show first 5 concepts
} for c in clusters], indent=2)}

Return ONLY a JSON array of cluster_ids ranked by relevance (most relevant first):
["cluster_id1", "cluster_id2", ...]

Include only clusters that are actually relevant to the query."""

        try:
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 500,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3
                })
            )
            
            response_body = json.loads(response['body'].read())
            content = response_body['content'][0]['text']
            
            # Extract JSON array
            json_match = content[content.find('['):content.rfind(']')+1]
            relevant_clusters = json.loads(json_match)
            
            return relevant_clusters
            
        except Exception as e:
            print(f"Error determining relevant clusters: {e}")
            return []
    
    def export_affinity_map(self, clusters: List[ConceptCluster], output_file: str):
        """
        Export affinity map to JSON for visualization or storage.
        """
        export_data = {
            'clusters': [
                {
                    'cluster_id': c.cluster_id,
                    'concepts': c.concepts,
                    'central_concept': c.central_concept,
                    'categories': list(c.related_categories),
                    'segment_count': c.segment_count,
                    'affinity_score': c.affinity_score
                }
                for c in clusters
            ],
            'concept_relationships': {
                concept: dict(related)
                for concept, related in self.concept_cooccurrence.items()
            }
        }
        
        with open(output_file, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"Affinity map exported to {output_file}")


if __name__ == "__main__":
    # Test affinity mapper
    print("AffinityMapper test - requires tagged segments from ConceptExtractor")
