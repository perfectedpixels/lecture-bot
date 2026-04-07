"""
LLM client wrapper around the Anthropic Python SDK.
Replaces all boto3 bedrock-runtime invoke_model() calls.
"""

import os
import anthropic

DEFAULT_MODEL = "claude-sonnet-4-20250514"


def _get_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    try:
        import streamlit as st
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        pass
    raise ValueError(
        "ANTHROPIC_API_KEY not found. Set it as an environment variable "
        "or in .streamlit/secrets.toml"
    )


_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=_get_api_key())
    return _client


def call_claude(
    prompt: str,
    max_tokens: int = 1000,
    temperature: float = 0.3,
    model: str = DEFAULT_MODEL,
) -> str:
    """Call Claude and return the text response."""
    client = _get_client()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
