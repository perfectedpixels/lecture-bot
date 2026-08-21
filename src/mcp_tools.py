"""
Business logic behind the MCP (Model Context Protocol) server's tools —
pure functions, no MCP-protocol imports, no HTTP concerns. Protocol/HTTP
wiring lives in api/mcp_server.py, mirroring the existing split between
src/ (business logic, takes a raw FastPersonaBot) and api/ (FastAPI routes).

These are the "rich information" surface for external agents/tools: raw KB
retrieval, and an ungated methodology-generation tool. Both reuse
FastPersonaBot's existing retrieval/generation primitives — nothing here
reimplements retrieval. Callers MUST pass the raw FastPersonaBot (e.g. via
api/main.py's _raw_bot()), never CachedPersonaBot — see the persona_mode
caution in persona_bot_fast.py::query().
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

DIRECTIVE_RETRIEVE_N = 6


def _retrieve_metadata_filtered(
    bot, query: str, n: int, layer: Optional[str] = None, doc_type: Optional[str] = None
) -> List[Dict]:
    """Filtered retrieve on the `layer` and/or `doc_type` metadata attributes.

    Generalizes feedback_mode._retrieve_directive_channel, which hardcodes
    layer="directive" for its own use. Both filters combine with andAll when
    given together."""
    clauses = []
    if layer:
        clauses.append({"equals": {"key": "layer", "value": layer}})
    if doc_type:
        clauses.append({"equals": {"key": "doc_type", "value": doc_type}})
    if not clauses:
        return []
    filt = clauses[0] if len(clauses) == 1 else {"andAll": clauses}
    try:
        response = bot.bedrock_agent.retrieve(
            knowledgeBaseId=bot.knowledge_base_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {"numberOfResults": n, "filter": filt}
            },
        )
        return list(response.get("retrievalResults", []))
    except Exception as e:
        print(f"⚠ Metadata-filtered retrieve failed (degrading gracefully): {e}")
        return []


def _result_to_dict(bot, r: Dict) -> Dict[str, Any]:
    meta = r.get("metadata") if isinstance(r.get("metadata"), dict) else {}
    return {
        "source": bot._source_name_from_result(r),
        "uri": r.get("location", {}).get("s3Location", {}).get("uri", ""),
        "text": r.get("content", {}).get("text", ""),
        "layer": meta.get("layer"),
        "doc_type": meta.get("doc_type"),
        "score": r.get("score"),
    }


def mcp_retrieve(
    bot,
    query: str,
    layer: Optional[str] = None,
    doc_type: Optional[str] = None,
    max_results: int = 6,
) -> Dict[str, Any]:
    """Raw KB retrieval for MCP clients. With neither filter, uses the normal
    multi-signal retrieve (query expansion is not applied -- MCP callers supply
    their own query text). With `layer` and/or `doc_type`, uses a filtered
    retrieve on those metadata attributes."""
    if layer or doc_type:
        results = _retrieve_metadata_filtered(
            bot, query, max_results, layer=layer, doc_type=doc_type
        )
    else:
        results, _err = bot._retrieve_parallel([query], max_results=max_results)
    return {"results": [_result_to_dict(bot, r) for r in results]}


def mcp_list_rubrics() -> Dict[str, Any]:
    """Assignment rubrics available in the instructor grading handbook."""
    import grading

    return {"rubrics": grading.list_rubrics()}


def mcp_get_rubric(assignment: str) -> Dict[str, Any]:
    """Full handbook rubric for one assignment, by loose name."""
    import grading

    return grading.get_rubric(assignment)


def mcp_grade(bot, submission: str, assignment: str) -> Dict[str, Any]:
    """Instructor-side draft assessment of a student submission."""
    import grading

    return grading.grade_submission(bot, submission, assignment)


def mcp_derive_calibration(bot, submission: str, assignment: str) -> Dict[str, Any]:
    """Draft reusable 4.0 grading criteria from an exemplar submission."""
    import grading

    return grading.derive_calibration(bot, submission, assignment)


def mcp_review_document(
    bot, document: str, focus: str = "", max_results: int = 10
) -> Dict[str, Any]:
    """Check an instructor's own draft against their own course material."""
    import doc_review

    return doc_review.review_document(bot, document, focus=focus, max_results=max_results)


def mcp_check_authorship(
    bot,
    document: str,
    assignment_brief: str = "",
    prior_artifacts: str = "",
    style_trigger: float = 0.40,
) -> Dict[str, Any]:
    """Gather tiered authorship evidence for instructor review."""
    import authorship

    return authorship.check_authorship_signals(
        bot,
        document,
        assignment_brief=assignment_brief,
        prior_artifacts=prior_artifacts,
        style_trigger=style_trigger,
    )


def mcp_calibrate_authorship(documents: List[str]) -> Dict[str, Any]:
    """False-positive rate of the style tells on known-human writing."""
    import authorship

    return authorship.calibrate(documents)


def mcp_methodology(
    bot, request: str, response_language: str = "en", max_results: int = 6
) -> Dict[str, Any]:
    """Ungated methodology generation, subject only to guardrails.BASELINE_RULES
    -- not STUDENT_INTERFACE_ADDENDUM. Thin wrapper around FastPersonaBot's
    existing query() pipeline (retrieval/rerank/diversity/invoke unchanged);
    only the prompt variant differs, via persona_mode="advisor"."""
    result = bot.query(
        request,
        max_results,
        True,
        response_language=response_language,
        persona_mode="advisor",
    )
    return {
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
    }
