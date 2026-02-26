"""
Learning Card Generator
Generates contextual learning cards for bot responses
"""

import json
import boto3
from typing import List, Dict, Optional
from pathlib import Path


class LearningCardGenerator:
    """
    Generates three types of contextual learning cards:
    1. Related Concepts (from affinity map)
    2. Core Teaching Concepts (high-level concepts)
    3. See It in Practice (portfolio examples)
    """
    
    def __init__(self,
                 affinity_map_path: str = None,
                 teaching_concepts_path: str = "data/teaching_concepts.json",
                 portfolio_metadata_path: str = "data/portfolio_image_metadata.json",
                 knowledge_base_id: str = None,
                 model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"):
        
        self.bedrock_runtime = boto3.client('bedrock-runtime')
        self.bedrock_agent = boto3.client('bedrock-agent-runtime') if knowledge_base_id else None
        self.knowledge_base_id = knowledge_base_id
        self.model_id = model_id
        
        # Load data files
        self.affinity_map = None
        self.clusters = {}
        if affinity_map_path and Path(affinity_map_path).exists():
            self._load_affinity_map(affinity_map_path)
        
        self.teaching_concepts = {}
        if Path(teaching_concepts_path).exists():
            self._load_teaching_concepts(teaching_concepts_path)
        
        self.portfolio_metadata = {}
        if Path(portfolio_metadata_path).exists():
            self._load_portfolio_metadata(portfolio_metadata_path)
        
        # Cache for inline content
        self._content_cache = {}
    
    def _load_affinity_map(self, path: str):
        """Load affinity map for related concepts"""
        with open(path, 'r') as f:
            self.affinity_map = json.load(f)
        
        for cluster in self.affinity_map.get('clusters', []):
            self.clusters[cluster['cluster_id']] = cluster
        
        print(f"✓ Loaded {len(self.clusters)} concept clusters")
    
    def _load_teaching_concepts(self, path: str):
        """Load teaching concepts taxonomy"""
        with open(path, 'r') as f:
            self.teaching_concepts = json.load(f)
        
        print(f"✓ Loaded {len(self.teaching_concepts)} teaching concepts")
    
    def _load_portfolio_metadata(self, path: str):
        """Load portfolio image metadata"""
        with open(path, 'r') as f:
            self.portfolio_metadata = json.load(f)
        
        total_images = sum(len(p.get('images', [])) for p in self.portfolio_metadata.values())
        print(f"✓ Loaded {len(self.portfolio_metadata)} projects with {total_images} images")
    
    def generate_cards(self, 
                      question: str, 
                      answer: str, 
                      relevant_concepts: List[str] = None,
                      exclude_projects: List[str] = None) -> Dict:
        """
        Generate all three types of learning cards for a Q&A pair.
        
        Args:
            exclude_projects: List of project_keys to exclude from portfolio examples
        
        Returns:
        {
            'related_concepts': [...],
            'teaching_concepts': [...],
            'portfolio_examples': [...]
        }
        """
        try:
            cards = {
                'related_concepts': self.analyze_related_concepts(question, answer, relevant_concepts),
                'teaching_concepts': self.identify_teaching_concepts(question, answer),
                'portfolio_examples': self.find_portfolio_examples(question, answer, relevant_concepts, exclude_projects)
            }
            return cards
        
        except Exception as e:
            print(f"Error generating cards: {e}")
            return {
                'related_concepts': [],
                'teaching_concepts': [],
                'portfolio_examples': []
            }
    
    def analyze_related_concepts(self, 
                                 question: str, 
                                 answer: str, 
                                 relevant_concepts: List[str] = None) -> List[Dict]:
        """
        Find related concepts from affinity map.
        Returns 3-5 concepts that are related but not already discussed.
        """
        if not self.affinity_map or not relevant_concepts:
            return []
        
        # Find which clusters the current concepts belong to
        current_clusters = set()
        for concept in relevant_concepts[:5]:  # Limit to top 5
            for cluster_id, cluster in self.clusters.items():
                if concept.lower() in [c.lower() for c in cluster.get('concepts', [])]:
                    current_clusters.add(cluster_id)
        
        if not current_clusters:
            return []
        
        # Get related concepts from same and related clusters
        related_concepts = []
        for cluster_id in current_clusters:
            cluster = self.clusters[cluster_id]
            
            # Add concepts from same cluster
            for concept in cluster.get('concepts', [])[:10]:
                if concept.lower() not in [c.lower() for c in relevant_concepts]:
                    related_concepts.append({
                        'concept': concept,
                        'cluster': cluster.get('central_concept', ''),
                        'relevance': 'same_cluster'
                    })
            
            # Add concepts from related clusters
            for related_id in cluster.get('related_clusters', [])[:2]:
                if related_id in self.clusters:
                    related_cluster = self.clusters[related_id]
                    for concept in related_cluster.get('concepts', [])[:5]:
                        if concept.lower() not in [c.lower() for c in relevant_concepts]:
                            related_concepts.append({
                                'concept': concept,
                                'cluster': related_cluster.get('central_concept', ''),
                                'relevance': 'related_cluster'
                            })
        
        # Remove duplicates and limit to top 5
        seen = set()
        unique_concepts = []
        for item in related_concepts:
            if item['concept'].lower() not in seen:
                seen.add(item['concept'].lower())
                unique_concepts.append(item)
                if len(unique_concepts) >= 5:
                    break
        
        return unique_concepts
    
    def identify_teaching_concepts(self, question: str, answer: str) -> List[Dict]:
        """
        Identify relevant high-level teaching concepts.
        Uses Claude to analyze Q&A and map to taxonomy.
        Returns top 3-5 teaching concepts.
        """
        if not self.teaching_concepts:
            return []
        
        # Build concept summary for Claude
        concept_summary = {
            name: {
                'definition': data.get('definition', ''),
                'keywords': data.get('keywords', [])
            }
            for name, data in self.teaching_concepts.items()
        }
        
        prompt = f"""Analyze this Q&A exchange and identify relevant high-level teaching concepts based primarily on what was discussed in the ANSWER.

Question: {question}
Answer: {answer[:800]}

Available Teaching Concepts:
{json.dumps(concept_summary, indent=2)}

Identify the 3-5 most relevant teaching concepts that relate to the topics actually discussed in the answer.
Focus on concepts that were explained or demonstrated in the response, not just mentioned in the question.
For each, explain WHY it's relevant based on the answer content in one sentence.

Return ONLY valid JSON:
[
  {{
    "concept": "concept name",
    "relevance": "why it's relevant based on the answer",
    "confidence": 0.0-1.0
  }}
]
"""
        
        try:
            response = self.bedrock_runtime.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 800,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                })
            )
            
            content = json.loads(response['body'].read())['content'][0]['text']
            json_start = content.find('[')
            json_end = content.rfind(']') + 1
            concepts = json.loads(content[json_start:json_end])
            
            # Enrich with full concept data
            enriched = []
            for item in concepts:
                concept_name = item['concept']
                if concept_name in self.teaching_concepts:
                    enriched.append({
                        **item,
                        'definition': self.teaching_concepts[concept_name].get('definition', ''),
                        'key_principles': self.teaching_concepts[concept_name].get('key_principles', [])[:3]
                    })
            
            return enriched[:5]
            
        except Exception as e:
            print(f"Error identifying teaching concepts: {e}")
            return []
    
    def find_portfolio_examples(self, 
                               question: str, 
                               answer: str, 
                               relevant_concepts: List[str] = None,
                               exclude_projects: List[str] = None) -> List[Dict]:
        """
        Find relevant portfolio examples based on semantic similarity with the answer.
        
        Args:
            exclude_projects: List of project_keys to exclude (prevents doom loops)
        
        Scoring prioritizes:
        1. Semantic overlap between answer and project descriptions (HIGH weight)
        2. Concept tag matches from answer content (MEDIUM weight)
        3. Teaching concept matches (MEDIUM weight)
        4. Lecture mentions as tiebreaker (LOW weight)
        
        Returns top 1-3 projects with images and confidence scores.
        """
        if not self.portfolio_metadata:
            return []
        
        if exclude_projects is None:
            exclude_projects = []
        
        # Extract key terms from answer for semantic matching
        answer_lower = answer.lower()
        answer_words = set(answer_lower.split())
        
        # Score each project
        project_scores = []
        
        for project_key, project_data in self.portfolio_metadata.items():
            # Skip if this project was recently shown
            if project_key in exclude_projects:
                continue
            
            score = 0
            reasons = []
            
            # 1. SEMANTIC SIMILARITY - Check if answer discusses this project/company
            project_title = project_data.get('title', '').lower()
            project_name = project_key.lower()
            
            # Direct mention of project/company in answer (HIGHEST weight)
            if project_name in answer_lower or project_title in answer_lower:
                score += 10
                reasons.append(f"Directly relevant to your question")
            
            # 2. ANSWER-BASED CONCEPT MATCHING - Check project descriptions against answer
            project_description = project_data.get('summary', {}).get('description', '').lower()
            primary_concepts = [pc.lower() for pc in project_data.get('summary', {}).get('primary_concepts', [])]
            
            # Check if project concepts appear in the answer
            concept_matches = []
            for concept in primary_concepts:
                concept_words = set(concept.split())
                # Check for word overlap between concept and answer
                overlap = concept_words.intersection(answer_words)
                if len(overlap) >= 2 or concept in answer_lower:  # At least 2 words match or full phrase
                    score += 5
                    concept_matches.append(concept)
            
            if concept_matches:
                reasons.append(f"Demonstrates {', '.join(concept_matches[:2])}")
            
            # 3. IMAGE CONCEPT TAG MATCHING - Check image tags against answer
            for img in project_data.get('images', []):
                img_concepts = [c.lower() for c in img.get('concept_tags', [])]
                for img_concept in img_concepts:
                    # Check if this concept appears in the answer
                    if img_concept in answer_lower or any(word in answer_words for word in img_concept.split()):
                        score += 3
                        if f"Shows {img_concept}" not in reasons:
                            reasons.append(f"Shows {img_concept}")
                        break  # Only count once per image
            
            # 4. RELEVANT_CONCEPTS MATCHING (from question context) - REDUCED weight
            if relevant_concepts:
                for concept in relevant_concepts:
                    concept_lower = concept.lower()
                    # Only count if concept also appears in answer (ensures relevance)
                    if concept_lower in answer_lower:
                        if any(concept_lower in pc for pc in primary_concepts):
                            score += 2
                            if f"Example of {concept}" not in reasons:
                                reasons.append(f"Example of {concept}")
            
            # 5. LECTURE MENTIONS - TIEBREAKER ONLY (minimal weight)
            lecture_mentions = project_data.get('lecture_mentions', [])
            if lecture_mentions and score > 0:  # Only add if already relevant
                score += min(len(lecture_mentions) * 0.5, 2)  # Cap at +2 points
            
            if score > 0:
                # Calculate confidence (normalize score to 0-1 range)
                # Max realistic score is now ~25, so normalize accordingly
                confidence = min(score / 20.0, 1.0)
                
                project_scores.append({
                    'project_key': project_key,
                    'project_data': project_data,
                    'score': score,
                    'confidence': confidence,
                    'reasons': reasons[:2]  # Top 2 reasons
                })
        
        # Sort by score and return top 3
        project_scores.sort(key=lambda x: x['score'], reverse=True)
        
        results = []
        for item in project_scores[:3]:
            project_data = item['project_data']
            
            # Get top 3 most relevant images
            images = []
            for img in project_data.get('images', [])[:3]:
                images.append({
                    'filename': img.get('filename', ''),
                    's3_url': img.get('s3_url', ''),
                    'description': img.get('description', ''),
                    'phase': img.get('phase', 'unknown')
                })
            
            results.append({
                'project_key': item['project_key'],
                'title': project_data.get('title', item['project_key']),
                'reasons': item['reasons'],
                'images': images,
                'lecture_mentions': len(project_data.get('lecture_mentions', [])),
                'confidence': item['confidence']
            })
        
        return results
    
    def get_smart_follow_ups(self, cards: Dict, min_confidence: float = 0.80, max_items: int = 3) -> List[Dict]:
        """
        Get top follow-up topics with 80%+ confidence, mixing both types.
        
        Returns list of:
        {
            'type': 'concept' or 'example',
            'title': 'Display title',
            'summary': 'Short summary (max 10 words)',
            'prompt': 'Auto-submit prompt text',
            'confidence': 0.0-1.0
        }
        """
        all_topics = []
        
        # Add teaching concepts
        for concept in cards.get('teaching_concepts', []):
            if concept.get('confidence', 0) >= min_confidence:
                # Create 10-word summary from relevance
                summary_words = concept.get('relevance', '').split()[:10]
                summary = ' '.join(summary_words)
                
                all_topics.append({
                    'type': 'concept',
                    'title': concept['concept'],
                    'summary': summary,
                    'prompt': f"Can you explain {concept['concept']} in more detail?",
                    'confidence': concept.get('confidence', 0.85)
                })
        
        # Add portfolio examples
        for project in cards.get('portfolio_examples', []):
            if project.get('confidence', 0) >= min_confidence:
                project_name = project['title'].replace('-', ' ').title()
                
                # Create 10-word summary from reasons
                reasons = project.get('reasons', [])
                summary_words = ' '.join(reasons).split()[:10] if reasons else "Real-world application example".split()
                summary = ' '.join(summary_words)
                
                all_topics.append({
                    'type': 'example',
                    'title': f"{project_name} work example",
                    'summary': summary,
                    'prompt': f"Tell me more about the {project_name} example and how it demonstrates these concepts",
                    'confidence': project.get('confidence', 0.80)
                })
        
        # Sort by confidence and return top N
        all_topics.sort(key=lambda x: x['confidence'], reverse=True)
        return all_topics[:max_items]
    
    def get_inline_content(self, concept: str, max_length: int = 500) -> Optional[str]:
        """
        Fetch inline content for a concept from Knowledge Base.
        Returns a brief explanation suitable for inline expansion.
        """
        if not self.bedrock_agent or not self.knowledge_base_id:
            return None
        
        # Check cache
        cache_key = f"{concept}_{max_length}"
        if cache_key in self._content_cache:
            return self._content_cache[cache_key]
        
        try:
            # Query Knowledge Base
            response = self.bedrock_agent.retrieve(
                knowledgeBaseId=self.knowledge_base_id,
                retrievalQuery={'text': f"Explain {concept} briefly"},
                retrievalConfiguration={
                    'vectorSearchConfiguration': {
                        'numberOfResults': 2
                    }
                }
            )
            
            # Extract and format content
            content = "\n".join([
                result['content']['text'][:max_length]
                for result in response['retrievalResults']
            ])
            
            # Cache it
            self._content_cache[cache_key] = content
            
            return content
            
        except Exception as e:
            print(f"Error fetching inline content for {concept}: {e}")
            return None


if __name__ == "__main__":
    # Test the card generator
    generator = LearningCardGenerator(
        affinity_map_path="data/affinity_map.json",
        teaching_concepts_path="data/teaching_concepts.json",
        portfolio_metadata_path="data/portfolio_image_metadata.json"
    )
    
    # Test with sample Q&A
    question = "What is user research?"
    answer = "User research is the systematic study of target users..."
    relevant_concepts = ["user research", "interviews", "surveys"]
    
    cards = generator.generate_cards(question, answer, relevant_concepts)
    
    print("\n=== LEARNING CARDS ===\n")
    print(f"Related Concepts: {len(cards['related_concepts'])}")
    print(f"Teaching Concepts: {len(cards['teaching_concepts'])}")
    print(f"Portfolio Examples: {len(cards['portfolio_examples'])}")
    
    print(json.dumps(cards, indent=2))
