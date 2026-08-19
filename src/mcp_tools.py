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


def _retrieve_layer_filtered(bot, query: str, layer: str, n: int) -> List[Dict]:
    """Filtered retrieve for a specific `layer` metadata value (e.g.
    "directive" or "reference"). Generalizes
    feedback_mode._retrieve_directive_channel, which hardcodes "directive"
    for its own single use case; this one is parameterized for MCP callers
    who may want either channel explicitly."""
    try:
        response = bot.bedrock_agent.retrieve(
            knowledgeBaseId=bot.knowledge_base_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {
                    "numberOfResults": n,
                    "filter": {"equals": {"key": "layer", "value": layer}},
                }
            },
        )
        return list(response.get("retrievalResults", []))
    except Exception as e:
        print(f"⚠ Layer-filtered retrieve failed (degrading gracefully): {e}")
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
    bot, query: str, layer: Optional[str] = None, max_results: int = 6
) -> Dict[str, Any]:
    """Raw KB retrieval for MCP clients. layer=None uses the normal
    multi-signal retrieve (query expansion not applied here -- MCP callers
    supply their own query text directly); layer="directive"|"reference"
    uses a filtered retrieve on that metadata channel."""
    if layer:
        results = _retrieve_layer_filtered(bot, query, layer, max_results)
    else:
        results, _err = bot._retrieve_parallel([query], max_results=max_results)
    return {"results": [_result_to_dict(bot, r) for r in results]}


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
