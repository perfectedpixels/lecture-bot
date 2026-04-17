"""
Improved retrieval strategies for better lecture content matching.
Handles domain-specific queries (healthcare, life sciences, etc.)
"""

import boto3
import json
from typing import List, Dict, Optional


class ImprovedRetrieval:
    """Enhanced retrieval with query expansion and reranking"""
    
    def __init__(self, knowledge_base_id: str, model_id: str = "us.anthropic.claude-sonnet-4-20250514-v1:0"):
        self.bedrock_agent = boto3.client('bedrock-agent-runtime')
        self.bedrock_runtime = boto3.client('bedrock-runtime')
        self.knowledge_base_id = knowledge_base_id
        self.model_id = model_id
        
        # Domain-specific term mappings
        self.domain_terms = {
            'healthcare': ['Kariko', 'Katalin Kariko', 'mRNA', 'Pulse', 'Hodgkin', 'medical', 'clinical', 'patient', 'diagnosis', 'treatment'],
            'life_sciences': ['biology', 'biotech', 'pharmaceutical', 'research', 'clinical trials'],
            'design': ['UX', 'user experience', 'interface', 'prototype', 'wireframe', 'usability'],
            'research': ['methodology', 'qualitative', 'quantitative', 'analysis', 'data']
        }
    
    def expand_query(self, query: str) -> List[str]:
        """
        Expand query with related terms and variations.
        Returns multiple query variations to try.
        """
        
        prompt = f"""Given this query, generate 3 alternative phrasings that would help find relevant lecture content.
Include variations with:
- More specific terms
- Related concepts
- Different word choices

Original query: {query}

Return ONLY a JSON array of 3 alternative queries:
["query1", "query2", "query3"]"""

        try:
            response = self.bedrock_runtime.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7
                })
            )
            
            content = json.loads(response['body'].read())['content'][0]['text']
            queries = json.loads(content[content.find('['):content.rfind(']')+1])
            return [query] + queries  # Include original
            
        except Exception as e:
            print(f"Query expansion failed: {e}")
            return [query]
    
    def detect_domain(self, query: str) -> Optional[str]:
        """Detect if query is about a specific domain"""
        query_lower = query.lower()
        
        for domain, terms in self.domain_terms.items():
            if any(term.lower() in query_lower for term in terms):
                return domain
        
        return None
    
    def retrieve_with_expansion(self, query: str, max_results: int = 10) -> List[Dict]:
        """
        Retrieve using multiple query variations and combine results.
        """
        
        # Detect domain and add domain terms
        domain = self.detect_domain(query)
        expanded_queries = [query]
        
        if domain:
            # Add domain-specific variations
            domain_terms = self.domain_terms[domain][:3]
            for term in domain_terms:
                if term.lower() not in query.lower():
                    expanded_queries.append(f"{query} {term}")
        
        # Get query expansions
        expanded_queries.extend(self.expand_query(query)[:2])
        
        all_results = []
        seen_uris = set()
        
        # Try each query variation
        for q in expanded_queries[:4]:  # Limit to 4 variations
            try:
                response = self.bedrock_agent.retrieve(
                    knowledgeBaseId=self.knowledge_base_id,
                    retrievalQuery={'text': q},
                    retrievalConfiguration={
                        'vectorSearchConfiguration': {
                            'numberOfResults': max_results
                        }
                    }
                )
                
                # Deduplicate by URI
                for result in response['retrievalResults']:
                    uri = result['location']['s3Location']['uri']
                    if uri not in seen_uris:
                        seen_uris.add(uri)
                        result['query_used'] = q
                        all_results.append(result)
                
            except Exception as e:
                print(f"Retrieval failed for query '{q}': {e}")
                continue
        
        # Sort by score if available
        all_results.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        return all_results[:max_results]
    
    def rerank_results(self, query: str, results: List[Dict]) -> List[Dict]:
        """
        Rerank results based on relevance to original query.
        """
        
        if len(results) <= 3:
            return results
        
        # Build context from top results
        contexts = []
        for i, result in enumerate(results[:10]):
            contexts.append(f"[{i}] {result['content']['text'][:500]}")
        
        prompt = f"""Given this query and these lecture excerpts, rank them by relevance.

Query: {query}

Excerpts:
{chr(10).join(contexts)}

Return ONLY a JSON array of indices in order of relevance (most relevant first):
[0, 3, 1, 5, ...]"""

        try:
            response = self.bedrock_runtime.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 200,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                })
            )
            
            content = json.loads(response['body'].read())['content'][0]['text']
            ranking = json.loads(content[content.find('['):content.rfind(']')+1])
            
            # Reorder results
            reranked = []
            for idx in ranking:
                if 0 <= idx < len(results):
                    reranked.append(results[idx])
            
            # Add any missing results at the end
            for result in results:
                if result not in reranked:
                    reranked.append(result)
            
            return reranked
            
        except Exception as e:
            print(f"Reranking failed: {e}")
            return results


def test_retrieval():
    """Test the improved retrieval"""
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python improved_retrieval.py <kb_id> <query>")
        sys.exit(1)
    
    kb_id = sys.argv[1]
    query = sys.argv[2]
    
    retriever = ImprovedRetrieval(kb_id)
    
    print(f"Original query: {query}")
    print(f"\nDetected domain: {retriever.detect_domain(query)}")
    
    print("\nExpanded queries:")
    for q in retriever.expand_query(query):
        print(f"  - {q}")
    
    print("\nRetrieving...")
    results = retriever.retrieve_with_expansion(query, max_results=5)
    
    print(f"\nFound {len(results)} results:")
    for i, result in enumerate(results):
        print(f"\n[{i+1}] Score: {result.get('score', 'N/A')}")
        print(f"Query used: {result.get('query_used', 'original')}")
        print(f"Source: {result['location']['s3Location']['uri']}")
        print(f"Content preview: {result['content']['text'][:200]}...")


if __name__ == "__main__":
    test_retrieval()
