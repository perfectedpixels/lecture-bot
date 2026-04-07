import json
from typing import Optional, List, Dict
from pathlib import Path

from llm_client import call_claude, DEFAULT_MODEL
from vector_store import VectorStore

class PersonaLectureBot:
    """
    Enhanced lecture bot with persona and affinity-based context selection.
    Responds as if it's the instructor, using teaching style and knowledge from lectures.
    """

    def __init__(self,
                 affinity_map_path: str = None,
                 model_id: str = DEFAULT_MODEL,
                 persona_name: str = "Professor Levine"):

        self.vector_store = VectorStore()
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
            content = call_claude(prompt, max_tokens=300, temperature=0.3, model=self.model_id)
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
        """Build a prompt that includes persona instructions and context."""

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
        """Query with persona and affinity-based context selection."""

        # Get relevant concepts from affinity map
        relevant_concepts = self._get_relevant_concepts(question)

        # Retrieve relevant documents from vector store
        try:
            results = self.vector_store.query(question, n_results=max_results)
        except Exception as e:
            print(f"Retrieval error: {e}")
            results = []

        # Extract context
        context = "\n\n".join([r['text'] for r in results])

        # Build prompt with or without persona
        if use_persona:
            prompt = self._build_persona_prompt(question, context, relevant_concepts)
        else:
            prompt = f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"

        # Generate answer
        answer = call_claude(prompt, max_tokens=2000, model=self.model_id)

        return {
            'question': question,
            'answer': answer,
            'sources': [r['source'] for r in results],
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

    if len(sys.argv) < 2:
        print("Usage: python persona_bot.py <question> [affinity_map_path]")
        sys.exit(1)

    question = sys.argv[1]
    affinity_path = sys.argv[2] if len(sys.argv) > 1 else None

    bot = PersonaLectureBot(affinity_path)
    result = bot.query(question)

    print(f"\nQuestion: {result['question']}")
    print(f"\nAnswer:\n{result['answer']}")

    if result['relevant_concepts']:
        print(f"\nRelevant concepts: {', '.join(result['relevant_concepts'][:5])}")

    print(f"\nSources: {', '.join(result['sources'])}")
