"""
Fast PersonaBot with caching and optimized retrieval.
Balances quality and speed.
Ported improvements from ppmg: retry logic, reranking, source diversity, project suggestions.
"""

import boto3
import json
import os
import random
import re
import time
from typing import Optional, List, Dict, Set, Tuple

import hashlib
from botocore.config import Config

try:
    from learning_card_generator import LearningCardGenerator
    HAS_CARD_GENERATOR = True
except ImportError:
    HAS_CARD_GENERATOR = False


class FastPersonaBot:
    """
    Optimized PersonaBot with caching and parallel retrieval.
    ~2-3x faster than enhanced version while maintaining quality.
    """

    def __init__(
        self,
        knowledge_base_id: str,
        model_id: str = "us.anthropic.claude-sonnet-4-20250514-v1:0",
        persona_name: str = "Professor Levine",
        enable_learning_cards: bool = True,
    ):
        # Get AWS region from environment with fallback
        aws_region = (
            os.environ.get("AWS_REGION")
            or os.environ.get("AWS_DEFAULT_REGION")
            or "us-east-1"
        )

        session = boto3.Session(region_name=aws_region)
        bedrock_config = Config(
            retries={"max_attempts": 4, "mode": "standard"},
            connect_timeout=3,
            read_timeout=20,
            tcp_keepalive=True,
        )

        self.bedrock_agent = session.client(
            "bedrock-agent-runtime", config=bedrock_config
        )
        self.bedrock_runtime = session.client(
            "bedrock-runtime", config=bedrock_config
        )
        self.knowledge_base_id = knowledge_base_id
        self.persona_name = persona_name
        self.cache_version = "v3-sonnet4"
        self.model_id = model_id

        # Simple domain keyword detection (no LLM call needed)
        self.domain_keywords = {
            "healthcare": [
                "kariko",
                "mrna",
                "pulse",
                "hodgkin",
                "medical",
                "clinical",
                "patient",
                "health",
            ],
            "design": [
                "ux",
                "ui",
                "interface",
                "prototype",
                "wireframe",
                "usability",
                "design",
            ],
            "research": [
                "research",
                "study",
                "methodology",
                "analysis",
                "data",
                "qualitative",
                "quantitative",
            ],
        }
        self.stop_words: Set[str] = {
            "the",
            "and",
            "for",
            "that",
            "with",
            "this",
            "from",
            "your",
            "about",
            "what",
            "when",
            "where",
            "who",
            "would",
            "could",
            "have",
            "been",
            "into",
            "their",
            "there",
            "they",
            "them",
            "just",
            "also",
            "than",
            "then",
            "some",
            "more",
            "most",
            "very",
            "work",
            "project",
            "projects",
            "design",
            "user",
            "users",
        }

        # Cache for query expansions
        self._expansion_cache = {}

        # Learning card generator (optional — gracefully disabled if data files missing)
        self.card_generator = None
        if enable_learning_cards and HAS_CARD_GENERATOR:
            try:
                self.card_generator = LearningCardGenerator(
                    affinity_map_path="data/affinity_map.json",
                    teaching_concepts_path="data/teaching_concepts.json",
                    portfolio_metadata_path="data/portfolio_image_metadata.json",
                    knowledge_base_id=knowledge_base_id,
                    model_id=model_id,
                )
            except Exception as e:
                print(f"⚠ Learning cards disabled: {e}")

        print(f"✓ Fast PersonaBot initialized (model: {self.model_id})")

    @staticmethod
    def _is_retryable_error(error: Exception) -> bool:
        msg = str(error).lower()
        retry_signals = [
            "throttl",
            "timeout",
            "timed out",
            "temporar",
            "too many requests",
            "service unavailable",
            "internal server error",
            "connection reset",
        ]
        return any(signal in msg for signal in retry_signals)

    def _invoke_model_with_retry(self, payload: Dict, max_attempts: int = 3):
        last_error: Optional[Exception] = None
        for attempt in range(1, max_attempts + 1):
            try:
                return self.bedrock_runtime.invoke_model(
                    modelId=self.model_id, body=json.dumps(payload)
                )
            except Exception as e:
                last_error = e
                if attempt == max_attempts or not self._is_retryable_error(e):
                    break
                backoff = (0.25 * (2 ** (attempt - 1))) + random.uniform(0, 0.15)
                time.sleep(backoff)
        raise RuntimeError(
            f"Bedrock model invocation failed after {max_attempts} attempts: {last_error}"
        )

    def _detect_domain_fast(self, query: str) -> Optional[str]:
        """Fast domain detection using keyword matching (no LLM)"""
        query_lower = query.lower()

        for domain, keywords in self.domain_keywords.items():
            if any(kw in query_lower for kw in keywords):
                return domain

        return None

    def _expand_query_simple(self, query: str) -> List[str]:
        """
        Simple query expansion without LLM call.
        Adds domain-specific terms if detected.
        """
        cache_key = hashlib.md5(query.encode()).hexdigest()
        if cache_key in self._expansion_cache:
            return self._expansion_cache[cache_key]

        queries = [query]
        domain = self._detect_domain_fast(query)

        if domain == "healthcare":
            if "kariko" not in query.lower():
                queries.append(f"{query} Kariko")
            if "pulse" not in query.lower() and "hodgkin" not in query.lower():
                queries.append(f"{query} healthcare applications")

        elif domain == "design":
            if "ux" not in query.lower():
                queries.append(f"{query} UX design")

        self._expansion_cache[cache_key] = queries
        return queries

    def _extract_query_terms(self, query: str) -> Set[str]:
        tokens = re.findall(r"[a-z0-9][a-z0-9\-]+", query.lower())
        return {
            token
            for token in tokens
            if len(token) > 2 and token not in self.stop_words
        }

    @staticmethod
    def _source_name_from_result(result: Dict) -> str:
        uri = result.get("location", {}).get("s3Location", {}).get("uri", "")
        return uri.split("/")[-1] if uri else "unknown-source"

    @staticmethod
    def _is_bio_query(query: str) -> bool:
        query_lower = query.lower()
        bio_terms = [
            "bio",
            "background",
            "about you",
            "career",
            "resume",
            "who are you",
            "education",
            "history",
            "experience",
        ]
        return any(term in query_lower for term in bio_terms)

    def _rerank_results_for_specificity(
        self, query: str, results: List[Dict]
    ) -> List[Dict]:
        """
        Prefer chunks that overlap query terms and contain concrete details.
        """
        query_terms = self._extract_query_terms(query)

        def score(result: Dict) -> float:
            text = result.get("content", {}).get("text", "")
            text_lower = text.lower()
            overlap = sum(1 for term in query_terms if term in text_lower)
            numeric_signals = len(re.findall(r"\b\d+(?:\.\d+)?%?\b", text))
            title_signals = len(
                re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b", text)
            )
            bedrock_score = float(result.get("score", 0) or 0)
            source_name = self._source_name_from_result(result).lower()
            # Strongly deprioritize CV/portfolio content — professional experience
            # should only surface as supporting examples, not primary results
            cv_penalty = (
                0.8
                if ("cv" in source_name and not self._is_bio_query(query))
                else 0.0
            )
            portfolio_penalty = (
                0.4
                if ("portfolio" in source_name and not self._is_bio_query(query))
                else 0.0
            )
            return (
                (overlap * 2.0)
                + (numeric_signals * 0.2)
                + (title_signals * 0.05)
                + bedrock_score
                - cv_penalty
                - portfolio_penalty
            )

        return sorted(results, key=score, reverse=True)

    def _select_diverse_results(
        self, query: str, results: List[Dict], max_results: int
    ) -> List[Dict]:
        """
        Ensure the context includes multiple sources when available and
        avoids over-reliance on CV content for non-bio queries.
        """
        if not results:
            return results

        is_bio = self._is_bio_query(query)
        per_source_limit = 2
        cv_limit = 2 if is_bio else 1

        selected: List[Dict] = []
        used_sources: Set[str] = set()
        source_counts: Dict[str, int] = {}

        for result in results:
            source = self._source_name_from_result(result)
            source_lower = source.lower()
            if source in used_sources:
                continue
            if "cv" in source_lower and source_counts.get(source, 0) >= cv_limit:
                continue
            selected.append(result)
            used_sources.add(source)
            source_counts[source] = source_counts.get(source, 0) + 1
            if len(selected) >= max_results:
                return selected[:max_results]

        for result in results:
            if result in selected:
                continue
            source = self._source_name_from_result(result)
            source_lower = source.lower()
            limit = cv_limit if "cv" in source_lower else per_source_limit
            if source_counts.get(source, 0) >= limit:
                continue
            selected.append(result)
            source_counts[source] = source_counts.get(source, 0) + 1
            if len(selected) >= max_results:
                break

        return selected[:max_results]

    def _retrieve_parallel(
        self, queries: List[str], max_results: int = 6
    ) -> Tuple[List[Dict], Optional[str]]:
        """
        Retrieve from multiple queries and deduplicate.
        Returns (results, last_error_message).
        """
        all_results = []
        seen_uris = set()
        last_error: Optional[str] = None

        for query in queries[:2]:
            try:
                response = self.bedrock_agent.retrieve(
                    knowledgeBaseId=self.knowledge_base_id,
                    retrievalQuery={"text": query},
                    retrievalConfiguration={
                        "vectorSearchConfiguration": {
                            "numberOfResults": max_results
                        }
                    },
                )

                for result in response["retrievalResults"]:
                    uri = result["location"]["s3Location"]["uri"]
                    if uri not in seen_uris:
                        seen_uris.add(uri)
                        all_results.append(result)

                if len(all_results) >= max_results:
                    break

            except Exception as e:
                last_error = str(e)
                print(f"Retrieval failed for '{query}': {e}")
                continue

        return all_results[:max_results], last_error

    def _build_persona_prompt(
        self, question: str, context: str, response_language: str = "en"
    ) -> str:
        """Build prompt with lecture-bot persona (teaching/student context)."""

        lang_block = ""
        if response_language == "zh":
            lang_block = """
LANGUAGE (required):
- The student may write in 简体中文 or English.
- Write your entire response in 简体中文 (Simplified Chinese).
- Lecture excerpts below are in English; explain ideas clearly in Chinese. Use standard UX/产品/设计术语 where natural.

"""

        return f"""You are {self.persona_name}, a UX leader and educator responding to a student's question based on your lectures.
{lang_block}
INSTRUCTIONS:
- Respond in first person as Professor Levine, with natural sentence variety.
- Ground your answer in the source content below. Prioritize lecture concepts, frameworks, and methodologies.
- When professional experience appears in the source content, use it as a supporting example to illustrate how a concept is applied in practice — not as the main focus.
- Use details from at least two distinct source sections when available.
- If asked a broad question, include at least 2 concrete references from source content.
- Explain concepts clearly for students — use analogies and practical examples to make ideas stick.
- Be conversational and direct; no roleplay stage directions or meta-phrases like "Speaking as" or "As Professor Levine".
- Keep responses concise: 2-3 short paragraphs by default, longer only if the question warrants depth.
- If source content is insufficient for the question, state that directly and suggest what the student could ask instead.
- Focus on teaching the material — help students understand the "why" behind concepts, not just the "what".
- If a student asks about an assignment, guide them toward the relevant concepts and frameworks rather than giving them the answer directly.
- NEVER write, rewrite, or fix a student's assignment work. Do not produce deliverable content (persona descriptions, journey maps, wireframe labels, rubric responses, etc.) on their behalf. Explain what needs improvement and why, point to the right frameworks, and let them do the work.

Lecture content:
{context}

Student's question: {question}

Remember: be specific, grounded in lecture material, and help the student learn."""

    def _clean_response(self, answer: str) -> str:
        """Remove meta-phrases from response (lecture-bot style)."""
        patterns = [
            r"^\*?Speaking as [^*\n]+\*?\s*",
            r"^\*?As [^*\n]+\*?\s*",
            r"^\*?Responding as [^*\n]+\*?\s*",
            r"^\*?In my role as [^*\n]+\*?\s*",
        ]
        for pattern in patterns:
            answer = re.sub(pattern, "", answer, flags=re.IGNORECASE)
        return answer.strip()

    def query(
        self,
        question: str,
        max_results: int = 3,
        use_persona: bool = True,
        exclude_projects: Optional[List[str]] = None,
        response_language: str = "en",
    ) -> dict:
        """
        Fast query with simple expansion, reranking, and source diversity.
        Optimized for speed with fewer retrieval results.

        response_language: "en" (default) or "zh" (Simplified Chinese output).
        """
        queries = self._expand_query_simple(question)

        results, retrieval_error = self._retrieve_parallel(queries, max_results=max_results)
        results = self._rerank_results_for_specificity(question, results)
        results = self._select_diverse_results(question, results, max_results)

        if not results:
            if response_language == "zh":
                base_msg = "我在课程资料中没有找到这方面的内容。请换个说法或尝试其他主题。"
            else:
                base_msg = "I don't have information about that in my lectures. Could you rephrase or ask about a different topic?"
            if retrieval_error:
                if "ResourceNotFoundException" in retrieval_error or "does not exist" in retrieval_error:
                    if response_language == "zh":
                        base_msg += f"\n\n_(知识库错误：{retrieval_error[:120]}… — 请检查设置中的 Knowledge Base ID)_"
                    else:
                        base_msg += f"\n\n_(KB error: {retrieval_error[:120]}… — check Knowledge Base ID in Settings)_"
                else:
                    if response_language == "zh":
                        base_msg += f"\n\n_(检索错误：{retrieval_error[:120]}…)_"
                    else:
                        base_msg += f"\n\n_(Retrieval error: {retrieval_error[:120]}…)_"
            return {
                "question": question,
                "answer": base_msg,
                "sources": [],
                "context": "",
                "learning_cards": {},
            }

        context_blocks = []
        for r in results:
            source_name = self._source_name_from_result(r)
            text = r["content"]["text"]
            context_blocks.append(f"[Source: {source_name}]\n{text}")
        context = "\n\n---\n\n".join(context_blocks)
        sources = [r["location"]["s3Location"]["uri"] for r in results]

        if use_persona:
            prompt = self._build_persona_prompt(question, context, response_language)
        else:
            if response_language == "zh":
                prompt = f"Context:\n{context}\n\n问题：{question}\n\n请用简体中文回答。"
            else:
                prompt = f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"

        max_out = 1200 if response_language == "zh" else 800

        model_response = self._invoke_model_with_retry(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_out,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.35,
            }
        )

        response_body = json.loads(model_response["body"].read())
        answer = response_body["content"][0]["text"]
        answer = self._clean_response(answer)

        # Generate learning cards if the generator is available
        learning_cards = {}
        if self.card_generator:
            try:
                learning_cards = self.card_generator.generate_cards(
                    question=question,
                    answer=answer,
                    relevant_concepts=None,
                    exclude_projects=exclude_projects,
                )
            except Exception as e:
                print(f"⚠ Learning card generation failed: {e}")

        return {
            "question": question,
            "answer": answer,
            "sources": sources,
            "context": context,
            "learning_cards": learning_cards,
        }

    def health_check(self) -> bool:
        """
        Lightweight dependency check used by /api/health?deep=true.
        """
        try:
            response = self.bedrock_agent.retrieve(
                knowledgeBaseId=self.knowledge_base_id,
                retrievalQuery={"text": "ux design"},
                retrievalConfiguration={
                    "vectorSearchConfiguration": {"numberOfResults": 1}
                },
            )
            return isinstance(response.get("retrievalResults"), list)
        except Exception:
            return False

    def generate_report(self, topic: str) -> str:
        """Generate report"""
        prompt = f"As {self.persona_name}, create a detailed report on '{topic}' based on your lectures."
        return self.query(prompt, max_results=10)["answer"]

    def analyze_assignment(self, assignment_text: str) -> dict:
        """Provide feedback on assignment"""
        prompt = f"""As {self.persona_name}, review this assignment and provide feedback.

Assignment:
{assignment_text}

Provide:
1. What the student did well
2. Areas for improvement
3. Specific suggestions"""

        return self.query(prompt, max_results=8)

    def explain_concept(self, concept: str) -> dict:
        """Explain concept"""
        prompt = f"As {self.persona_name}, explain '{concept}' with examples from your lectures."
        return self.query(prompt, max_results=5)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python persona_bot_fast.py <knowledge_base_id> <question>")
        sys.exit(1)

    kb_id = sys.argv[1]
    question = sys.argv[2]

    bot = FastPersonaBot(kb_id)
    result = bot.query(question)

    print(f"\nQuestion: {result['question']}")
    print(f"\nAnswer:\n{result['answer']}")
    print(f"\nSources: {len(result['sources'])}")
