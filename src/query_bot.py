import json
from typing import Optional

from llm_client import call_claude, DEFAULT_MODEL
from vector_store import VectorStore

class LectureBot:
    """
    Query interface for the lecture bot using local vector store.
    """

    def __init__(self, model_id: str = DEFAULT_MODEL):
        self.vector_store = VectorStore()
        self.model_id = model_id

    def query(self, question: str, max_results: int = 5) -> dict:
        """
        Query the knowledge base with a question.
        Returns relevant context and generated answer.
        """

        # Retrieve relevant documents
        results = self.vector_store.query(question, n_results=max_results)

        # Extract context from retrieved documents
        context = "\n\n".join([r['text'] for r in results])

        # Generate answer using Claude
        prompt = f"""Based on the following lecture content, answer the question.

Context from lectures:
{context}

Question: {question}

Provide a comprehensive answer based on the lecture content above."""

        answer = call_claude(prompt, max_tokens=2000, model=self.model_id)

        return {
            'question': question,
            'answer': answer,
            'sources': [r['source'] for r in results],
            'context': context
        }

    def generate_report(self, topic: str) -> str:
        """Generate a comprehensive report on a topic from lectures."""
        prompt = f"Generate a detailed report summarizing all lecture content related to: {topic}"
        return self.query(prompt)['answer']

    def create_visualization_data(self, concept: str) -> dict:
        """Extract structured data for visualization."""
        prompt = f"""Extract key data points, relationships, and concepts related to '{concept}'
        from the lectures. Format as JSON with nodes and edges for visualization."""

        result = self.query(prompt)
        return {
            'concept': concept,
            'data': result['answer'],
            'sources': result['sources']
        }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python query_bot.py <question>")
        sys.exit(1)

    question = sys.argv[1]

    bot = LectureBot()
    result = bot.query(question)

    print(f"\nQuestion: {result['question']}")
    print(f"\nAnswer:\n{result['answer']}")
    print(f"\nSources: {', '.join(result['sources'])}")
