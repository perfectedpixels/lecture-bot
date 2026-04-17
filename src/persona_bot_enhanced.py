"""
Enhanced PersonaBot with improved retrieval for better content matching.
"""

import boto3
import json
from typing import Optional, List, Dict
from pathlib import Path
from improved_retrieval import ImprovedRetrieval


class EnhancedPersonaBot:
    """
    Persona bot with improved retrieval strategies.
    Better at finding domain-specific content (healthcare, life sciences, etc.)
    """
    
    def __init__(self, 
                 knowledge_base_id: str,
                 model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0",
                 persona_name: str = "Professor Levine"):
        
        self.bedrock_runtime = boto3.client('bedrock-runtime')
        self.knowledge_base_id = knowledge_base_id
        self.model_id = model_id
        self.persona_name = persona_name
        
        # Use improved retrieval
        self.retriever = ImprovedRetrieval(knowledge_base_id, model_id)
        
        print(f"✓ Enhanced PersonaBot initialized with improved retrieval")
    
    def _build_persona_prompt(
        self,
        question: str,
        context: str,
        sources: List[str] = None,
        response_language: str = "en",
    ) -> str:
        """Build prompt with persona instructions."""

        lang_block = ""
        if response_language == "zh":
            lang_block = """
LANGUAGE (required):
- The student may write in 简体中文 or English.
- Write your entire response in 简体中文 (Simplified Chinese).
- Lecture excerpts below may be in English; explain ideas clearly in Chinese.

"""

        source_context = ""
        if sources:
            source_names = [s.split('/')[-1] for s in sources[:3]]
            if response_language == "zh":
                source_context = f"\n参考讲义来源：{', '.join(source_names)}"
            else:
                source_context = f"\nDrawing from lectures: {', '.join(source_names)}"
        
        persona_prompt = f"""You are {self.persona_name}, responding to a student's question based on your lectures.
{lang_block}
IMPORTANT INSTRUCTIONS:
- Respond naturally in first person ("In my lectures, I discussed...")
- Draw ONLY from the lecture content provided below
- Use your teaching style: clear, engaging, with practical examples
- Reference specific examples from the lectures when relevant
- If the question relates to healthcare, life sciences, or specific people/companies mentioned in lectures (like Kariko, Pulse, Hodgkin), make sure to reference those
- If you don't have information in the lectures provided, say so honestly
- Be conversational but authoritative
- Do NOT say "Speaking as" or "Respond as" - just answer naturally

Lecture content:
{context}
{source_context}

Student's question: {question}"""

        return persona_prompt
    
    def query(
        self,
        question: str,
        max_results: int = 8,
        use_persona: bool = True,
        response_language: str = "en",
    ) -> dict:
        """
        Query with improved retrieval and persona.

        response_language: "en" (default) or "zh" (Simplified Chinese output).
        """
        
        print(f"Query: {question}")
        print(f"Detecting domain and expanding query...")
        
        # Use improved retrieval with query expansion
        results = self.retriever.retrieve_with_expansion(question, max_results=max_results)
        
        if not results:
            if response_language == "zh":
                no_info = "我在课程资料中没有找到这方面的内容。请换个说法或尝试其他主题。"
            else:
                no_info = "I don't have information about that in my lectures. Could you rephrase or ask about a different topic?"
            return {
                "question": question,
                "answer": no_info,
                "sources": [],
                "context": "",
            }
        
        print(f"Retrieved {len(results)} relevant passages")
        
        # Rerank for better relevance
        results = self.retriever.rerank_results(question, results)
        
        # Extract context with more detail
        context_parts = []
        for i, result in enumerate(results[:max_results]):
            source = result['location']['s3Location']['uri'].split('/')[-1]
            text = result['content']['text']
            context_parts.append(f"[From {source}]\n{text}")
        
        context = "\n\n---\n\n".join(context_parts)
        sources = [r['location']['s3Location']['uri'] for r in results]
        
        # Build prompt
        if use_persona:
            prompt = self._build_persona_prompt(question, context, sources, response_language)
        else:
            if response_language == "zh":
                prompt = f"Context:\n{context}\n\n问题：{question}\n\n请用简体中文回答。"
            else:
                prompt = f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"

        max_tokens = 2200 if response_language == "zh" else 2500

        # Generate answer with higher max tokens for detailed responses
        model_response = self.bedrock_runtime.invoke_model(
            modelId=self.model_id,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7
            })
        )
        
        response_body = json.loads(model_response['body'].read())
        answer = response_body['content'][0]['text']
        
        # Remove meta-phrases if they appear
        answer = self._clean_response(answer)
        
        return {
            'question': question,
            'answer': answer,
            'sources': sources,
            'context': context
        }
    
    def _clean_response(self, answer: str) -> str:
        """Remove meta-phrases from response"""
        import re
        
        # Remove patterns like "*Speaking as...*" or "Speaking as..." at the start
        patterns = [
            r'^\*?Speaking as [^*\n]+\*?\s*',
            r'^\*?As [^*\n]+\*?\s*',
            r'^\*?Responding as [^*\n]+\*?\s*',
            r'^\*?In my role as [^*\n]+\*?\s*'
        ]
        
        for pattern in patterns:
            answer = re.sub(pattern, '', answer, flags=re.IGNORECASE)
        
        return answer.strip()
    
    def generate_report(self, topic: str) -> str:
        """Generate comprehensive report"""
        prompt = f"As {self.persona_name}, create a detailed report on '{topic}' based on your lectures, including specific examples and case studies you've discussed."
        return self.query(prompt, max_results=15)['answer']
    
    def analyze_assignment(self, assignment_text: str) -> dict:
        """Provide feedback on assignment"""
        prompt = f"""As {self.persona_name}, review this student assignment and provide constructive feedback
based on concepts from your lectures.

Assignment:
{assignment_text}

Provide:
1. What the student did well
2. Areas for improvement  
3. Relevant concepts from lectures they should review
4. Specific suggestions"""

        return self.query(prompt, max_results=10)
    
    def explain_concept(self, concept: str) -> dict:
        """Explain concept in teaching style"""
        prompt = f"As {self.persona_name}, explain '{concept}' the way you would in your lectures, with specific examples and real-world applications you've discussed."
        return self.query(prompt, max_results=6)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python persona_bot_enhanced.py <knowledge_base_id> <question>")
        sys.exit(1)
    
    kb_id = sys.argv[1]
    question = sys.argv[2]
    
    bot = EnhancedPersonaBot(kb_id)
    result = bot.query(question)
    
    print(f"\n{'='*60}")
    print(f"Question: {result['question']}")
    print(f"{'='*60}")
    print(f"\nAnswer:\n{result['answer']}")
    print(f"\n{'='*60}")
    print(f"Sources ({len(result['sources'])}):")
    for source in result['sources']:
        print(f"  - {source.split('/')[-1]}")
