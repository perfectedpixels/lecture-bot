import boto3
import json
from typing import Optional

class LectureBot:
    """
    Query interface for the lecture bot using Bedrock Knowledge Base.
    """
    
    def __init__(self, knowledge_base_id: str, model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"):
        self.bedrock_agent = boto3.client('bedrock-agent-runtime')
        self.bedrock_runtime = boto3.client('bedrock-runtime')
        self.knowledge_base_id = knowledge_base_id
        self.model_id = model_id
    
    def query(self, question: str, max_results: int = 5) -> dict:
        """
        Query the knowledge base with a question.
        Returns relevant context and generated answer.
        """
        
        # Retrieve relevant documents
        response = self.bedrock_agent.retrieve(
            knowledgeBaseId=self.knowledge_base_id,
            retrievalQuery={'text': question},
            retrievalConfiguration={
                'vectorSearchConfiguration': {
                    'numberOfResults': max_results
                }
            }
        )
        
        # Extract context from retrieved documents
        context = "\n\n".join([
            result['content']['text'] 
            for result in response['retrievalResults']
        ])
        
        # Generate answer using Bedrock model
        prompt = f"""Based on the following lecture content, answer the question.

Context from lectures:
{context}

Question: {question}

Provide a comprehensive answer based on the lecture content above."""

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
            'context': context
        }
    
    def generate_report(self, topic: str) -> str:
        """
        Generate a comprehensive report on a topic from lectures.
        """
        prompt = f"Generate a detailed report summarizing all lecture content related to: {topic}"
        return self.query(prompt)['answer']
    
    def create_visualization_data(self, concept: str) -> dict:
        """
        Extract structured data for visualization.
        """
        prompt = f"""Extract key data points, relationships, and concepts related to '{concept}' 
        from the lectures. Format as JSON with nodes and edges for visualization."""
        
        result = self.query(prompt)
        return {
            'concept': concept,
            'data': result['answer'],
            'sources': result['sources']
        }


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python query_bot.py <knowledge_base_id> <question>")
        sys.exit(1)
    
    kb_id = sys.argv[1]
    question = sys.argv[2]
    
    bot = LectureBot(kb_id)
    result = bot.query(question)
    
    print(f"\nQuestion: {result['question']}")
    print(f"\nAnswer:\n{result['answer']}")
    print(f"\nSources: {', '.join(result['sources'])}")
