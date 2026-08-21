"""
Review the instructor's own documents against their own course material.

Scope is deliberately narrow. The knowledge base is lecture transcripts,
assignment briefs and rubrics -- a record of *what was taught*, not a corpus
about writing craft. So this tool answers questions the material can actually
answer:

  - Does this draft match what the lectures actually say?
  - Does it contradict a rubric or an assignment brief?
  - Does it claim something the course material doesn't support?
  - Is there relevant material the draft omits?

It explicitly does NOT give structure/clarity/style feedback. Grounding
generic writing advice in a lecture corpus would dress up an opinion as though
it came from the instructor's own material, which is worse than not answering.

This is an instructor-facing tool for the instructor's *own* documents, so it
carries guardrails.BASELINE_RULES but not STUDENT_INTERFACE_ADDENDUM -- see
src/guardrails.py. Reviewing a *student's* draft is a different job with a
different rule set; that is what feedback_mode.py is for.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import guardrails

MIN_REVIEWABLE_CHARS = 200
# A review of a real draft routinely runs several findings, each quoting both
# the draft and the source material. 2000 truncated mid-JSON on the first
# realistic test document, so the parse failed even though the findings were
# correct -- headroom here is cheaper than a lost review.
DOC_REVIEW_MAX_TOKENS = 4096
DOC_REVIEW_TEMPERATURE = 0.3
# Documents are long; retrieve more widely than a chat turn would, so a
# multi-section draft has a chance of matching material for each section
# rather than only its opening.
DOC_REVIEW_MAX_RESULTS = 10
# Cap what we embed as the retrieval query. Retrieval quality degrades on very
# long query text, and a full document would blow past practical query limits.
QUERY_CHARS = 2000


def _extract_json_object(text: str) -> Dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("```")[1]
        if stripped.startswith("json"):
            stripped = stripped[4:]
    start, end = stripped.find("{"), stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        stripped = stripped[start : end + 1]
    return json.loads(stripped)


def _format_sources(bot, results: List[Dict]) -> str:
    blocks = []
    for i, r in enumerate(results, start=1):
        name = bot._source_name_from_result(r)
        text = r.get("content", {}).get("text", "")
        blocks.append(f"[{i}] {name}\n{text}")
    return "\n\n---\n\n".join(blocks)


def _build_review_prompt(document: str, focus: str, sources: str) -> str:
    focus_block = f"\nThe author specifically wants you to check: {focus}\n" if focus.strip() else ""
    return f"""You are helping an instructor check their own draft against their own course material. This is the instructor's document, not a student's submission.

{guardrails.BASELINE_RULES}
{focus_block}
COURSE MATERIAL (retrieved from the instructor's lectures, assignment briefs and rubrics):
{sources or "(nothing relevant retrieved)"}

THE INSTRUCTOR'S DRAFT:
{document}

INSTRUCTIONS:
- Judge the draft ONLY against the course material above. You are checking consistency and coverage, not writing quality.
- Do NOT comment on structure, style, tone, grammar, flow, or persuasiveness. Those are real concerns but this material cannot ground them, and unsupported style advice presented as if it came from the course material would be misleading.
- Every point you make must cite a specific retrieved source by its [n] marker. If you cannot ground a point in the sources, leave it out.
- A contradiction means the draft asserts something the material actually says otherwise. Do not report mere differences in wording or emphasis as contradictions.
- If the retrieved material is too thin or off-topic to judge the draft, say so plainly rather than manufacturing findings.

Return ONLY a JSON object (no markdown fences):
{{
  "grounded": true,
  "coverage_note": "one sentence on whether the retrieved material was actually sufficient to review this draft",
  "contradictions": [
    {{"claim": "what the draft asserts", "material_says": "what the course material says", "source": "[n]"}}
  ],
  "unsupported_claims": [
    {{"claim": "assertion the material neither supports nor contradicts", "note": "why it matters"}}
  ],
  "omissions": [
    {{"missing": "relevant material the draft doesn't mention", "source": "[n]", "note": "why it may belong"}}
  ],
  "consistent_with": ["points where the draft correctly reflects the material, each with a [n] marker"]
}}

Any of the arrays may be empty. An empty result is a legitimate answer -- do not invent findings to fill them."""


def review_document(
    bot,
    document: str,
    focus: str = "",
    max_results: int = DOC_REVIEW_MAX_RESULTS,
) -> Dict[str, Any]:
    """Check a draft for consistency with the instructor's own course material.

    Returns {"ok": bool, ...} with contradictions, unsupported claims,
    omissions and confirmations -- each tied to a retrieved source. Refuses
    rather than guessing when the document is too short or when nothing
    relevant is retrieved.
    """
    document = (document or "").strip()
    if len(document) < MIN_REVIEWABLE_CHARS:
        return {
            "ok": False,
            "error": f"document too short to review ({len(document)} chars; "
                     f"needs at least {MIN_REVIEWABLE_CHARS})",
        }

    # Focus text, when given, is what the author actually wants checked --
    # bias retrieval toward it rather than toward the document's opening.
    query = f"{focus}\n\n{document}"[:QUERY_CHARS] if focus.strip() else document[:QUERY_CHARS]
    results, retrieval_error = bot._retrieve_parallel([query], max_results=max_results)

    if not results:
        return {
            "ok": False,
            "error": "no relevant course material retrieved; cannot ground a review",
            "retrieval_error": retrieval_error,
        }

    results = bot._rerank_results_for_specificity(query, results)
    results = bot._select_diverse_results(query, results, max_results)

    prompt = _build_review_prompt(document, focus, _format_sources(bot, results))
    response = bot._invoke_model_with_retry(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": DOC_REVIEW_MAX_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": DOC_REVIEW_TEMPERATURE,
        }
    )
    body = json.loads(response["body"].read())
    text = body["content"][0]["text"]

    try:
        review = _extract_json_object(text)
    except (json.JSONDecodeError, ValueError):
        # Distinguish "ran out of room" from "emitted malformed JSON" -- the
        # first is actionable (shorten the document or raise the cap) and the
        # findings up to the cut are usually real; the second is not.
        if body.get("stop_reason") == "max_tokens":
            return {
                "ok": False,
                "error": "review was cut off before it finished (hit the output limit)",
                "hint": "Review a section at a time, or narrow `focus` to what matters most.",
                "partial": text,
            }
        return {"ok": False, "error": "could not parse review output", "raw": text}

    review["ok"] = True
    review["sources_consulted"] = [bot._source_name_from_result(r) for r in results]
    review["scope_note"] = (
        "Checked for consistency with your course material only. Structure, clarity "
        "and style were deliberately not assessed -- the knowledge base is lecture "
        "and rubric content and cannot ground that kind of feedback."
    )
    return review
