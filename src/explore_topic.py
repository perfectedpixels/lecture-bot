"""
Explore Canvas: branch a topic into up to 4 grounded facet cards.

Powers the node-based topic explorer. Given a topic (and an optional parent
breadcrumb path from prior branches), it:

  1. Retrieves from the lecture KB using FastPersonaBot's existing retrieval
     pipeline (query expansion, reranking, source diversity) — no separate
     retrieval logic.
  2. If grounding is weak/ambiguous, returns clarifying **directions** first so
     the student can narrow the topic before any general-knowledge fallback.
  3. Otherwise generates up to 4 distinct sub-topic cards, each grounded in
     retrieved lecture snippets with citations. A card that has to lean on
     general knowledge is flagged ``grounded: false`` and labeled — never
     silently presented as lecture content.

Card prompts are deliberately neutral/structural (not persona-voiced) to keep
cards short and scannable, unlike the first-person lecturer voice used
elsewhere in this codebase.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Optional

# Below this top retrieval score we treat the KB as thin for the topic and
# prefer a clarifying step before generating cards (or before leaning on
# general knowledge). Tuned against this KB's actual score distribution
# (sampled 2026-08-17): nonsense/uncovered topics floor around 0.57-0.59,
# genuinely well-covered lecture topics score 0.77+, with real-but-thin
# coverage around 0.65-0.68. The ux-team-kb reference's 0.40 never fires
# here — its KB's score distribution is different.
CLARIFY_SCORE_THRESHOLD = 0.65
MIN_RESULTS_FOR_GROUNDED = 2
MAX_CARDS = 4

# Shared with frontend/src/explore/conceptVisual.js — keep both in sync if this changes.
CONCEPT_TAXONOMY = [
    "lecture_concept",
    "framework",
    "case_study",
    "methodology",
    "terminology",
    "historical_example",
    "best_practice",
    "ethics",
]


def _extract_json_object(text: str) -> Dict[str, Any]:
    """Parse a JSON object out of a Claude response, tolerating ```json fences
    or leading/trailing prose."""
    stripped = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, re.DOTALL)
    if fence:
        stripped = fence.group(1)
    else:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            stripped = stripped[start : end + 1]
    return json.loads(stripped)


def _compose_topic(topic: str, parent_path: Optional[List[str]]) -> str:
    parent_path = parent_path or []
    if parent_path:
        trail = " > ".join(parent_path[-4:])
        return f"{trail} > {topic}"
    return topic


def _format_indexed_context(results: List[Dict], bot) -> str:
    blocks = []
    for i, r in enumerate(results, start=1):
        source_name = bot._source_name_from_result(r)
        text = r.get("content", {}).get("text", "")
        blocks.append(f"[{i}] Source: {source_name}\n{text}")
    return "\n\n---\n\n".join(blocks)


def _invoke_json(bot, system: str, user: str, max_tokens: int = 1024) -> Dict[str, Any]:
    response = bot._invoke_model_with_retry(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "temperature": 0.4,
        }
    )
    body = json.loads(response["body"].read())
    text = body["content"][0]["text"]
    return _extract_json_object(text)


def _clarifying_options(bot, topic: str, context: str) -> Dict[str, Any]:
    """Lecture material is thin/ambiguous for this topic -> a short summary of
    WHY, plus 2-4 SHORT thematic DIRECTIONS the student can pick to focus the
    next branch. Not open-ended questions."""
    system = (
        "You help focus an exploration of a set of lecture transcripts. The "
        "retrieved material is thin or ambiguous for the topic. Return JSON "
        'only: {"summary": "one sentence on why this needs narrowing", '
        '"options": ["short thematic direction (3-6 words)", "..."]}. Give '
        "2-4 distinct options the student could pick to focus (e.g. a "
        "specific framework, case study, timeframe, or angle covered in the "
        "lectures). Options are short labels, NOT questions. Do not answer "
        "the topic."
    )
    user = f"Topic: {topic}\n\nClosest lecture snippets (may be weak):\n{context or '(none)'}"
    try:
        obj = _invoke_json(bot, system, user, max_tokens=512)
        options = [str(o).strip() for o in obj.get("options", []) if str(o).strip()][:4]
        summary = str(obj.get("summary", "")).strip()
        return {"options": options, "summary": summary}
    except (json.JSONDecodeError, ValueError, KeyError):
        return {"options": [], "summary": ""}


def _generate_cards(
    bot, topic: str, context: str, allow_general: bool, grounded_corpus: bool
) -> List[Dict[str, Any]]:
    fallback_clause = (
        "If the snippets do not cover a facet, you MAY use general knowledge "
        'for that card but set "grounded": false and leave "citations": []. '
        "Never fabricate citations."
        if allow_general
        else 'Only produce cards supported by the snippets; set "grounded": true and cite.'
    )
    taxonomy = ", ".join(CONCEPT_TAXONOMY)
    system = f"""You expand a topic into up to {MAX_CARDS} distinct, non-overlapping sub-topics worth exploring deeper, for a UX/design student's lecture-exploration canvas.
Ground each card in the retrieved lecture snippets when possible. {fallback_clause}
Write in neutral third person — short, scannable, structural. Do NOT write in first person as the professor and do NOT use a teaching/lecturer voice; this is card metadata, not a lecture answer.
Each paragraph is 2-4 sentences, specific and substantive (no fluff/niceties).
Tag each card's "concepts" using ONLY this taxonomy: {taxonomy}.
Return a single JSON object (no markdown fences):
{{
  "cards": [
    {{
      "title": "<=6 word title",
      "paragraph": "2-4 sentences",
      "concepts": ["one or more tags from the taxonomy above"],
      "grounded": true,
      "citations": [{{"label": "short", "excerpt": "tied to a snippet", "snippet_index": 1}}]
    }}
  ]
}}"""
    user = f"Topic to expand:\n{topic}\n\nRetrieved lecture snippets (indexed [1]..[n]):\n{context or '(no lecture snippets)'}"
    try:
        obj = _invoke_json(bot, system, user, max_tokens=1536)
        cards = obj.get("cards", [])
    except (json.JSONDecodeError, ValueError, KeyError):
        cards = []

    out: List[Dict[str, Any]] = []
    for c in cards[:MAX_CARDS]:
        grounded = bool(c.get("grounded", grounded_corpus)) and bool(c.get("citations"))
        concepts = [str(x) for x in (c.get("concepts") or []) if str(x) in CONCEPT_TAXONOMY][:6]
        out.append(
            {
                "id": str(uuid.uuid4()),
                "title": str(c.get("title", "")).strip()[:120] or "Untitled",
                "paragraph": str(c.get("paragraph", "")).strip(),
                "concepts": concepts,
                "grounded": grounded,
                "citations": c.get("citations") or [],
                "source_note": (
                    "From lecture materials"
                    if grounded
                    else "General knowledge — not from lecture materials"
                ),
            }
        )
    return out


def run_explore(
    bot,
    topic: str,
    parent_path: Optional[List[str]] = None,
    allow_general_fallback: bool = True,
    skip_clarify: bool = False,
    max_results: int = 6,
) -> Dict[str, Any]:
    """Branch ``topic`` into clarifying directions or up to 4 grounded facet
    cards. ``bot`` must be a FastPersonaBot instance (its raw retrieval
    methods are used directly, bypassing any response-cache wrapper)."""
    composed = _compose_topic(topic, parent_path)

    queries = bot._expand_query_simple(composed)
    results, _retrieval_error = bot._retrieve_parallel(queries, max_results=max_results)
    ranked = bot._rerank_results_for_specificity(composed, results)
    ranked = bot._select_diverse_results(composed, ranked, max_results)

    top_score = float(ranked[0].get("score", 0) or 0) if ranked else 0.0
    context = _format_indexed_context(ranked, bot)

    grounded_corpus = len(ranked) >= MIN_RESULTS_FOR_GROUNDED and top_score >= CLARIFY_SCORE_THRESHOLD

    if not grounded_corpus and not skip_clarify:
        clar = _clarifying_options(bot, topic, context)
        if clar["options"]:
            return {
                "mode": "clarify",
                "topic": topic,
                "parent_path": parent_path or [],
                "summary": clar["summary"],
                "options": clar["options"],
                "retrieval": {"result_count": len(ranked), "top_score": top_score},
            }

    cards = _generate_cards(
        bot, composed, context, allow_general=allow_general_fallback, grounded_corpus=grounded_corpus
    )
    return {
        "mode": "cards",
        "topic": topic,
        "parent_path": parent_path or [],
        "cards": cards,
        "grounded": grounded_corpus,
        "retrieval": {"result_count": len(ranked), "top_score": top_score},
    }
