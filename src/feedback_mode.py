"""
Feedback mode: Socratic, rubric-grounded feedback on a student's own pasted
work, distinct from lecture-bot's normal concept-question answering.

Ports two mechanisms from the sibling ux-team-kb project, adapted to
lecture-bot's own retrieval pipeline and KB:

  1. A "directive channel" — a second, layer-filtered retrieve alongside
     normal semantic search, so grading-handbook/rubric content (tagged
     layer=directive at ingest — see scripts/kb_metadata.py) reliably
     surfaces instead of competing on equal footing with lecture transcripts.
  2. Automatic intent classification (concept question vs. feedback request)
     so the same chat input handles both without a separate UI mode.

Reuses FastPersonaBot's existing retrieval primitives — no retrieval logic
reimplemented here, matching src/explore_topic.py's shape.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

import guardrails

DIRECTIVE_RETRIEVE_N = 4
MAX_DIRECTIVE_INJECT = 2
FEEDBACK_MAX_RESULTS = 6
# A pasted block longer than this is an overwhelming signal it's a feedback
# request on its own — skip the classifier call entirely and save the round
# trip. Only messages at or under this length go through the Haiku classifier.
FEEDBACK_CLASSIFY_LENGTH_THRESHOLD = 400
CLASSIFIER_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


def _retrieve_directive_channel(bot, query: str, n: int = DIRECTIVE_RETRIEVE_N) -> List[Dict]:
    """Filtered retrieve for layer=directive chunks only. Not routed through
    bot._retrieve_parallel, which has no filter support."""
    try:
        response = bot.bedrock_agent.retrieve(
            knowledgeBaseId=bot.knowledge_base_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {
                    "numberOfResults": n,
                    "filter": {"equals": {"key": "layer", "value": "directive"}},
                }
            },
        )
        return list(response.get("retrievalResults", []))
    except Exception as e:
        # A filtered retrieve fails if `layer` isn't indexed as filterable yet,
        # or the directive channel is simply empty for this KB state. The
        # directive channel is a bonus, never a hard dependency — degrade to
        # reference-only context rather than failing the whole request.
        print(f"⚠ Directive channel retrieve failed (degrading gracefully): {e}")
        return []


def _merge_directive_channel(
    reference_results: List[Dict], directive_results: List[Dict], max_inject: int = MAX_DIRECTIVE_INJECT
) -> List[Dict]:
    """Combine reference + directive results into one context list, directive
    entries first. Directive results come from a separate, guaranteed
    channel — rather than blending two differently-scaled scoring systems
    (Bedrock's raw retrieve score vs. FastPersonaBot's specificity-rerank
    score, which isn't preserved on the result dict), directive entries are
    unconditionally placed first. This achieves the same "always surfaces,
    never crowded out" behavior as ux-team-kb's score-boost approach without
    needing to compare two incompatible scores."""
    seen = {_result_uri(r) for r in reference_results}
    injected: List[Dict] = []
    for d in directive_results[:max_inject]:
        uri = _result_uri(d)
        if uri and uri not in seen:
            d = dict(d)
            d["_directive_channel"] = True
            injected.append(d)
            seen.add(uri)
    return injected + reference_results


def _result_uri(result: Dict) -> str:
    return result.get("location", {}).get("s3Location", {}).get("uri", "")


def _is_directive(result: Dict) -> bool:
    if result.get("_directive_channel"):
        return True
    meta = result.get("metadata")
    return isinstance(meta, dict) and meta.get("layer") == "directive"


def _format_context(results: List[Dict], bot) -> str:
    blocks = []
    for i, r in enumerate(results, start=1):
        source_name = bot._source_name_from_result(r)
        text = r.get("content", {}).get("text", "")
        tag = "[DIRECTIVE — grading criteria]" if _is_directive(r) else "[reference]"
        blocks.append(f"[{i}] {tag} Source: {source_name}\n{text}")
    return "\n\n---\n\n".join(blocks)


def _build_feedback_prompt(
    submitted_work: str,
    student_question: str,
    context: str,
    has_directive: bool,
    persona_name: str,
    response_language: str,
) -> str:
    directive_note = (
        ""
        if has_directive
        else "\nNo specific grading rubric was found for this topic — base your feedback on the lecture concepts and general best practices below instead.\n"
    )

    lang_block = ""
    if response_language == "zh":
        lang_block = "\nWrite your entire response in 简体中文 (Simplified Chinese).\n"

    question_block = (
        f'\nThe student also asked: "{student_question}"\n' if student_question.strip() else ""
    )

    return f"""You are {persona_name}, reviewing a student's own work and giving feedback — not answering a general question.
{lang_block}{directive_note}
SOURCE MATERIAL (grading criteria marked [DIRECTIVE] take priority over general [reference] lecture content when they conflict):
{context or "(no sources retrieved)"}

STUDENT'S SUBMITTED WORK:
{submitted_work}
{question_block}
INSTRUCTIONS:
{guardrails.BASELINE_RULES}
{guardrails.STUDENT_INTERFACE_ADDENDUM}
- Ground feedback in the SOURCE MATERIAL above — cite specific rubric dimensions or lecture concepts, don't invent criteria.
- Structure your response as exactly these three bulleted sections, in this order:

**What's working**
- 1-3 bullets on genuine strengths, specific to their actual submission (not generic praise).

**What's missing**
- 1-4 bullets, each tied to a specific rubric dimension or lecture concept when the source material supports one. Explain WHAT is missing and WHY it matters — never what the fix should say.

**A question to push their thinking**
- One Socratic question that makes them reconsider a specific weak spot themselves, rather than being told the answer.

- Keep each bullet to 1-2 sentences. Be encouraging but honest about what the material actually shows."""


def _prepare_feedback(
    bot,
    submitted_work: str,
    student_question: str,
    response_language: str,
    max_results: int,
):
    """Shared retrieval + prompt setup for both run_feedback and
    run_feedback_stream. Returns (prompt, sources, directive_sources, context)."""
    query_text = submitted_work if not student_question else f"{submitted_work}\n\n{student_question}"

    queries = bot._expand_query_simple(query_text[:2000])
    reference_results, _err = bot._retrieve_parallel(queries, max_results=max_results)
    reference_results = bot._rerank_results_for_specificity(query_text, reference_results)
    reference_results = bot._select_diverse_results(query_text, reference_results, max_results)

    directive_results = _retrieve_directive_channel(bot, query_text[:1000])
    merged = _merge_directive_channel(reference_results, directive_results)

    has_directive = any(_is_directive(r) for r in merged)
    context = _format_context(merged, bot)

    prompt = _build_feedback_prompt(
        submitted_work, student_question, context, has_directive, bot.persona_name, response_language
    )

    sources = [_result_uri(r) for r in merged if not _is_directive(r)]
    directive_sources = [_result_uri(r) for r in merged if _is_directive(r)]

    return prompt, sources, directive_sources, context


def run_feedback(
    bot,
    submitted_work: str,
    student_question: str = "",
    response_language: str = "en",
    max_results: int = FEEDBACK_MAX_RESULTS,
) -> Dict[str, Any]:
    """Blocking feedback generation: dual retrieve (reference + directive),
    merge, prompt, single Bedrock call. Returns
    {"answer", "sources", "directive_sources", "context"}."""
    prompt, sources, directive_sources, context = _prepare_feedback(
        bot, submitted_work, student_question, response_language, max_results
    )

    model_response = bot._invoke_model_with_retry(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1536,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
        }
    )
    response_body = json.loads(model_response["body"].read())
    answer = response_body["content"][0]["text"]

    return {
        "answer": answer,
        "sources": sources,
        "directive_sources": directive_sources,
        "context": context,
    }


def run_feedback_stream(
    bot,
    submitted_work: str,
    student_question: str = "",
    response_language: str = "en",
    max_results: int = FEEDBACK_MAX_RESULTS,
):
    """Streaming counterpart to run_feedback. Same retrieval/prompt setup;
    yields {"type": "delta", "text": ...} per token as it arrives, then a
    final {"type": "done", "sources": [...], "directive_sources": [...]}."""
    prompt, sources, directive_sources, _context = _prepare_feedback(
        bot, submitted_work, student_question, response_language, max_results
    )

    for event in bot._invoke_model_stream(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1536,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
        }
    ):
        yield event

    yield {"type": "done", "sources": sources, "directive_sources": directive_sources}


def classify_intent(bot, message: str) -> str:
    """Returns "feedback" or "concept". Long messages skip the classifier
    entirely (an overwhelming signal on their own); short/medium messages get
    a cheap Haiku classification call. Any failure defaults to "concept" —
    today's behavior, the safe default."""
    if len(message) > FEEDBACK_CLASSIFY_LENGTH_THRESHOLD:
        return "feedback"

    system = (
        "Classify the student's message as exactly one word: FEEDBACK or CONCEPT.\n"
        "FEEDBACK = the student is asking for feedback, review, or critique of their "
        "own work (even a short piece pasted inline, or asked about without pasting "
        'it, e.g. "can you review my approach to X?").\n'
        "CONCEPT = the student is asking a question to understand a concept, "
        "framework, or lecture topic.\n"
        "Respond with ONLY the single word FEEDBACK or CONCEPT, nothing else."
    )
    try:
        model_response = bot._invoke_model_with_retry(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 5,
                "system": system,
                "messages": [{"role": "user", "content": message}],
                "temperature": 0,
            },
            max_attempts=2,
            model_id_override=CLASSIFIER_MODEL_ID,
        )
        response_body = json.loads(model_response["body"].read())
        text = response_body["content"][0]["text"].strip().upper()
        return "feedback" if "FEEDBACK" in text else "concept"
    except Exception as e:
        print(f"⚠ Intent classification failed (defaulting to concept): {e}")
        return "concept"
