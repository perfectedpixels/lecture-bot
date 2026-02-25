import boto3
import json
from typing import Optional, List, Dict
from pathlib import Path

class PersonaLectureBot:
    """
    Enhanced lecture bot with persona and affinity-based context selection.
    Responds as if it's the instructor, using teaching style and knowledge from lectures.
    """
    
    def __init__(self, 
                 knowledge_base_id: str,
                 affinity_map_path: str = None,
                 model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0",
                 persona_name: str = "Professor Levine"):
        
        self.bedrock_agent = boto3.client('bedrock-agent-runtime')
        self.bedrock_runtime = boto3.client('bedrock-runtime')
        self.knowledge_base_id = knowledge_base_id
        self.model_id = model_id
        self.persona_name = persona_name
        
        # Load affinity map if provided
        self.affinity_map = None
        self.clusters = {}
        if affinity_map_path and Path(affinity_map_path).exists():
            self._load_affinity_map(affinity_map_path)
    
    def _load_affinity_map(self, path: str):
        """Load the affinity map for intelligent context selection"""
        with open(path, 'r') as f:
            self.affinity_map = json.load(f)
        
        # Index clusters by ID for quick lookup
        for cluster in self.affinity_map.get('clusters', []):
            self.clusters[cluster['cluster_id']] = cluster
        
        print(f"Loaded affinity map with {len(self.clusters)} concept clusters")
    
    def _get_relevant_concepts(self, query: str) -> List[str]:
        """
        Determine which concepts are relevant to the query.
        Uses Claude to analyze query against concept clusters.
        """
        if not self.affinity_map:
            return []
        
        cluster_summary = {
            cid: {
                'central_concept': c['central_concept'],
                'concepts': c['concepts'][:5]
            }
            for cid, c in self.clusters.items()
        }
        
        prompt = f"""Analyze this query and identify relevant concept clusters.

Query: {query}

Available clusters:
{json.dumps(cluster_summary, indent=2)}

Return ONLY a JSON array of relevant cluster IDs:
["cluster_id1", "cluster_id2"]"""

        try:
            response = self.bedrock_runtime.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                })
            )
            
            content = json.loads(response['body'].read())['content'][0]['text']
            cluster_ids = json.loads(content[content.find('['):content.rfind(']')+1])
            
            # Get all concepts from relevant clusters
            concepts = []
            for cid in cluster_ids:
                if cid in self.clusters:
                    concepts.extend(self.clusters[cid]['concepts'])
            
            return concepts
            
        except Exception as e:
            print(f"Error determining relevant concepts: {e}")
            return []
    
    def _build_persona_prompt(self, question: str, context: str, concepts: List[str] = None) -> str:
        """
        Build a prompt that includes persona instructions and context.
        """
        
        concept_context = ""
        if concepts:
            concept_context = f"\nRelevant concepts to consider: {', '.join(concepts[:10])}"
        
        persona_prompt = f"""You are {self.persona_name}, responding to a student's question based on your lectures.

IMPORTANT INSTRUCTIONS:
- Respond as if you are the instructor, using first person ("In my lectures, I discussed...")
- Draw from the lecture content provided below
- Use your teaching style: clear, engaging, with practical examples
- If the question relates to concepts you've taught, reference those lectures
- If you don't have information in the lectures, say so honestly
- Be conversational but authoritative

Lecture content:
{context}
{concept_context}

Student's question: {question}

Respond as {self.persona_name}:"""

        return persona_prompt
    
    def query(self, question: str, max_results: int = 5, use_persona: bool = True) -> dict:
        """
        Query with persona and affinity-based context selection.
        """
        
        # Get relevant concepts from affinity map
        relevant_concepts = self._get_relevant_concepts(question)
        
        # Build metadata filter if we have relevant concepts
        filter_config = {}
        if relevant_concepts:
            # Filter by concepts in metadata
            concepts_str = ", ".join(relevant_concepts[:5])
            filter_config = {
                'andAll': [
                    {
                        'stringContains': {
                            'key': 'concepts',
                            'value': relevant_concepts[0]  # At least one relevant concept
                        }
                    }
                ]
            }
        
        # Retrieve relevant documents from Knowledge Base
        retrieve_params = {
            'knowledgeBaseId': self.knowledge_base_id,
            'retrievalQuery': {'text': question},
            'retrievalConfiguration': {
                'vectorSearchConfiguration': {
                    'numberOfResults': max_results
                }
            }
        }
        
        # Add filter if we have one
        if filter_config:
            retrieve_params['retrievalConfiguration']['vectorSearchConfiguration']['filter'] = filter_config
        
        try:
            response = self.bedrock_agent.retrieve(**retrieve_params)
        except Exception as e:
            print(f"Retrieval error: {e}")
            # Fallback without filter
            retrieve_params['retrievalConfiguration']['vectorSearchConfiguration'].pop('filter', None)
            response = self.bedrock_agent.retrieve(**retrieve_params)
        
        # Extract context
        context = "\n\n".join([
            result['content']['text'] 
            for result in response['retrievalResults']
        ])
        
        # Build prompt with or without persona
        if use_persona:
            prompt = self._build_persona_prompt(question, context, relevant_concepts)
        else:
            prompt = f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"
        
        # Generate answer
        model_response = self.bedrock_runtime.invoke_model(
            modelId=self.model_id,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            })
        )
        
        response_body = json.loads(model_response['body'].read())
        answer = response_body['content'][0]['text']
        
        return {
            'question': question,
            'answer': answer,
            'sources': [r['location']['s3Location']['uri'] for r in response['retrievalResults']],
            'relevant_concepts': relevant_concepts,
            'context': context
        }
    
    def generate_report(self, topic: str) -> str:
        """Generate a comprehensive report as the instructor."""
        prompt = f"As {self.persona_name}, create a detailed report on '{topic}' based on your lectures."
        return self.query(prompt, max_results=10)['answer']
    
    def analyze_assignment(self, assignment_text: str) -> dict:
        """Provide feedback on an assignment as the instructor."""
        prompt = f"""As {self.persona_name}, review this student assignment and provide constructive feedback
based on concepts from your lectures.

Assignment:
{assignment_text}

Provide:
1. What the student did well
2. Areas for improvement
3. Relevant concepts from lectures they should review
4. Specific suggestions"""

        return self.query(prompt, max_results=8)
    
    def explain_concept(self, concept: str) -> dict:
        """Explain a concept in the instructor's teaching style."""
        prompt = f"As {self.persona_name}, explain '{concept}' the way you would in your lectures, with examples."
        return self.query(prompt, max_results=5)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python persona_bot.py <knowledge_base_id> <question> [affinity_map_path]")
        sys.exit(1)
    
    kb_id = sys.argv[1]
    question = sys.argv[2]
    affinity_path = sys.argv[3] if len(sys.argv) > 3 else None
    
    bot = PersonaLectureBot(kb_id, affinity_path)
    result = bot.query(question)
    
    print(f"\nQuestion: {result['question']}")
    print(f"\nAnswer:\n{result['answer']}")
    
    if result['relevant_concepts']:
        print(f"\nRelevant concepts: {', '.join(result['relevant_concepts'][:5])}")
    
    print(f"\nSources: {', '.join(result['sources'])}")
