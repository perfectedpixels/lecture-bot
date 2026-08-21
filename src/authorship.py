"""
Authorship signals: evidence for a conversation, not a verdict.

What this is for
----------------
Deciding whether a submission is worth a closer look, and giving the
instructor something concrete to point at when they have that conversation.
It never asserts that a document was AI-generated, never emits a probability,
and never produces an accusation.

Why it is shaped this way
-------------------------
Weak signals do combine -- that part of the intuition is sound. But the
common stylistic tells are not independent of each other. "Elevated
vocabulary", "verbose", "antithesis", and "em-dashes" all load onto a single
underlying trait: formal academic register. A student who writes formally
trips all four at once, which is one characteristic counted four times, not
four confirmations.

That matters because the population most likely to write in a formal register
is students who learned English academically -- the same population that
published GPT-detector evaluations found being misclassified at a much higher
rate than native speakers. So an unweighted "N of the tells fired" rule fails
hardest on exactly the students who can least afford a false accusation.

The base rate makes it worse. At a realistic prevalence, a classifier with
90% sensitivity and 90% specificity produces flag sets that are close to half
false positives, and those false positives are not randomly distributed --
they concentrate on the same students every term. Specificity dominates
sensitivity here: missing some generated work is cheap, accusing an innocent
student is not.

Hence two structural rules:

  1. STYLE ALONE NEVER FLAGS. Stylistic tells can only corroborate a hit from
     a tier that rests on checkable fact. Style-only clusters return
     STYLE_ONLY_INSUFFICIENT, which is a deliberate non-finding.
  2. THRESHOLDS ARE MEASURED, NOT GUESSED. The defaults below are informed
     guesses and are almost certainly wrong for any particular cohort. Run
     calibrate() over known-human work to get a real false-positive rate per
     threshold, then choose one with evidence.

Tiers
-----
  1 VERIFIABLE   fabricated citations, invented statistics, misattributed
                 claims. Strongest, because the instructor can check them.
  2 PROVENANCE   version history, submission telemetry, absent process
                 residue. NOT ASSESSABLE FROM TEXT -- this module reports
                 that it cannot see them and prompts the instructor to look.
  3 SUBSTANCE    no continuity with the student's other artifacts, missing
                 the assignment's particulars, internal contradiction.
  4 LEAKAGE      prompt residue, unrendered markdown, paste artifacts. Rare
                 but close to decisive.
  S STYLE        register and formatting habits. Corroborating only.
"""

from __future__ import annotations

import json
import re
import statistics
from typing import Any, Dict, List, Optional

MIN_ASSESSABLE_CHARS = 400
MODEL_MAX_TOKENS = 3000
MODEL_TEMPERATURE = 0.2

# Default trigger points for the style tells. These are starting guesses --
# see calibrate(). Rates are per 1000 words unless noted.
STYLE_THRESHOLDS = {
    "em_dash_per_1k": 3.0,
    "antithesis_per_1k": 2.0,
    "bullet_line_ratio": 0.40,
    "mean_sentence_words": 25.0,
    "long_word_ratio": 0.14,
    "emoji_any": 1,
}

# The share of style tells that must fire before style is called "consistent
# with generated text". Still cannot flag on its own.
DEFAULT_STYLE_TRIGGER = 0.40

_EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF←-⇿⬀-⯿]"
)
_ANTITHESIS = re.compile(
    r"\b(?:not just|isn'?t just|isn'?t (?:a|an|the)?|it'?s not|rather than|instead of)\b[^.!?]{0,80}?"
    r"(?:,|—|--|\bbut\b|\bit'?s\b)",
    re.IGNORECASE,
)
_PROMPT_RESIDUE = re.compile(
    r"(as an ai (?:language )?model|certainly[!,]? here'?s|here'?s (?:a|an|the) "
    r"(?:draft|revised|persona|version)|\[insert [^\]]+\]|\byour name here\b|"
    r"i cannot (?:browse|access)|knowledge cutoff)",
    re.IGNORECASE,
)
_MD_RESIDUE = re.compile(r"(\*\*[^*\n]+\*\*|^#{1,6}\s+\S|^\s*[-*]\s+\*\*)", re.MULTILINE)
_BULLET_LINE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+\S", re.MULTILINE)


def _words(text: str) -> List[str]:
    return re.findall(r"[A-Za-z']+", text)


def _sentences(text: str) -> List[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]


def style_features(text: str) -> Dict[str, Any]:
    """Deterministic style measurements. No model call, so these are stable
    and reproducible -- which is what makes calibration meaningful."""
    words = _words(text)
    n_words = max(len(words), 1)
    per_1k = 1000.0 / n_words

    sentences = _sentences(text)
    sent_lens = [len(_words(s)) for s in sentences] or [0]
    lines = [l for l in text.splitlines() if l.strip()]

    feats = {
        "word_count": len(words),
        "em_dash_per_1k": (text.count("—") + text.count("--")) * per_1k,
        "antithesis_per_1k": len(_ANTITHESIS.findall(text)) * per_1k,
        "bullet_line_ratio": (len(_BULLET_LINE.findall(text)) / len(lines)) if lines else 0.0,
        "mean_sentence_words": statistics.mean(sent_lens),
        # Long-word share stands in for reading level without needing a
        # syllable dictionary. It is the single most ESL-biased feature here,
        # which is precisely why style can never flag on its own.
        "long_word_ratio": sum(1 for w in words if len(w) >= 10) / n_words,
        "emoji_any": 1 if _EMOJI.search(text) else 0,
    }

    triggered = {k: bool(feats[k] >= STYLE_THRESHOLDS[k]) for k in STYLE_THRESHOLDS}
    fired = sum(triggered.values())
    return {
        "measurements": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in feats.items()},
        "triggered": triggered,
        "tells_fired": fired,
        "tells_total": len(triggered),
        "style_score": round(fired / len(triggered), 3),
    }


def leakage_signals(text: str) -> List[Dict[str, str]]:
    """Tier 4. Deterministic, rare, and close to decisive when present."""
    out = []
    for m in _PROMPT_RESIDUE.finditer(text):
        out.append({"kind": "prompt_residue", "evidence": m.group(0)[:120]})
    md = _MD_RESIDUE.findall(text)
    if md:
        out.append(
            {
                "kind": "unrendered_markdown",
                "evidence": f"{len(md)} markdown artifact(s), e.g. {str(md[0])[:60]}",
            }
        )
    return out


def _build_prompt(document: str, assignment_brief: str, prior_artifacts: str) -> str:
    brief = f"\nASSIGNMENT BRIEF:\n{assignment_brief}\n" if assignment_brief.strip() else ""
    prior = (
        f"\nTHE STUDENT'S OWN EARLIER ARTIFACTS (for continuity checking):\n{prior_artifacts}\n"
        if prior_artifacts.strip()
        else ""
    )
    return f"""Examine a student submission for checkable evidence about how it was produced. You are gathering evidence for an instructor to review, NOT reaching a verdict.
{brief}{prior}
SUBMISSION:
{document}

Report ONLY things you can point at concretely. Two rules that matter more than completeness:

- NEVER state or imply that the document was AI-generated. That is not a determination you can make from text, and it is not what is being asked.
- Report NOTHING you cannot quote. If a category is empty, leave it empty. Empty categories are the expected result for most real submissions and are a useful answer.

TIER 1 -- verifiable claims:
- citations that appear fabricated or cannot correspond to a real source (name a checkable reason: implausible volume/page, author-venue mismatch, a title that does not exist)
- statistics attributed to EXTERNAL literature that cannot be traced to a real source
- claims attributed to a real, named source that the source does not make

CRITICAL EXCLUSION for Tier 1: a student reporting their OWN primary research is
not an unsourced statistic. "Three of six participants abandoned the process",
"users took an average of 4.2 minutes", "I interviewed six people at the library"
are the student describing data they collected -- that is exactly what the
assignment asks for, and it is the signature of good work, not suspicious work.
Never report the student's own field data, interview counts, or observed metrics
as a Tier 1 finding. Tier 1 is only for claims about the OUTSIDE world that the
instructor could look up and fail to find.

TIER 3 -- substance:
- specifics the assignment required that are absent (the student's own product, their interviewees, their prior artifact). Only report this if an ASSIGNMENT BRIEF was supplied above -- without one you do not know what was required, and guessing produces findings against submissions that met a brief you never saw.
- internal contradictions within the submission
- contradictions against the student's earlier artifacts, if provided
- whether the submission answers a generic version of the task rather than this brief
- register uniformity: does the whole document hold one voice, or does it vary as human writing usually does

Return ONLY a JSON object (no markdown fences). Use single quotes for any quotation inside a string value; never place an unescaped double quote inside one.
{{
  "tier1_verifiable": [{{"kind": "fabricated_citation|unsourced_statistic|misattributed_claim", "quote": "the exact text", "why_checkable": "what the instructor should look up"}}],
  "tier3_substance": [{{"kind": "missing_specifics|internal_contradiction|contradicts_prior_work|generic_response|uniform_register", "quote": "the exact text or a description of what is absent", "note": "why this is worth asking about"}}],
  "notes": "anything ambiguous, or reasons a finding above might have an innocent explanation"
}}"""


def _extract_json(text: str) -> Dict[str, Any]:
    s = text.strip()
    if s.startswith("```"):
        s = s.split("```")[1]
        if s.startswith("json"):
            s = s[4:]
    a, b = s.find("{"), s.rfind("}")
    if a != -1 and b != -1 and b > a:
        s = s[a : b + 1]
    return json.loads(s)


def check_authorship_signals(
    bot,
    document: str,
    assignment_brief: str = "",
    prior_artifacts: str = "",
    style_trigger: float = DEFAULT_STYLE_TRIGGER,
) -> Dict[str, Any]:
    """Gather authorship evidence across tiers. Returns findings plus an
    `outcome` of NO_SIGNAL / STYLE_ONLY_INSUFFICIENT / INVESTIGATE.

    INVESTIGATE requires at least one tier-1, tier-3 or tier-4 finding.
    Style never reaches it alone, however many tells fire.
    """
    document = (document or "").strip()
    if len(document) < MIN_ASSESSABLE_CHARS:
        return {"ok": False, "error": f"too short to assess ({len(document)} chars)"}

    style = style_features(document)
    leakage = leakage_signals(document)

    tier1: List[Dict] = []
    tier3: List[Dict] = []
    model_notes = ""
    try:
        resp = bot._invoke_model_with_retry(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": MODEL_MAX_TOKENS,
                "messages": [
                    {
                        "role": "user",
                        "content": _build_prompt(document, assignment_brief, prior_artifacts),
                    }
                ],
                "temperature": MODEL_TEMPERATURE,
            }
        )
        body = json.loads(resp["body"].read())
        parsed = _extract_json(body["content"][0]["text"])
        tier1 = parsed.get("tier1_verifiable") or []
        tier3 = parsed.get("tier3_substance") or []
        model_notes = parsed.get("notes", "")
    except Exception as e:
        model_notes = f"substance/citation analysis unavailable: {e}"

    hard_hits = len(tier1) + len(tier3) + len(leakage)
    style_consistent = style["style_score"] >= style_trigger

    if hard_hits:
        outcome = "INVESTIGATE"
        summary = (
            f"{hard_hits} checkable finding(s). Style tells fired "
            f"{style['tells_fired']}/{style['tells_total']}"
            f"{' (corroborating)' if style_consistent else ''}."
        )
    elif style_consistent:
        outcome = "STYLE_ONLY_INSUFFICIENT"
        summary = (
            f"Style is consistent with generated text ({style['tells_fired']}/"
            f"{style['tells_total']} tells), but nothing checkable was found. "
            "Not a flag: these tells also describe formal academic writing, and "
            "they fire more often on students who learned English academically."
        )
    else:
        outcome = "NO_SIGNAL"
        summary = "No checkable findings and style is unremarkable."

    return {
        "ok": True,
        "outcome": outcome,
        "summary": summary,
        "tier1_verifiable": tier1,
        "tier3_substance": tier3,
        "tier4_leakage": leakage,
        "style": style,
        "tier2_provenance": {
            "assessable_from_text": False,
            "check_yourself": [
                "Document version history (Google Docs / Word): did the text accumulate, or arrive in one paste?",
                "Canvas submission telemetry: draft saves, time on task.",
                "Process residue: drafts, abandoned directions, messy intermediate artifacts.",
            ],
        },
        "notes": model_notes,
        "disclaimer": (
            "Evidence for a conversation, not a determination of authorship. No "
            "part of this output establishes that a document was AI-generated. "
            "Style findings corroborate; they never flag on their own."
        ),
    }


def calibrate(documents: List[str], thresholds: Optional[List[float]] = None) -> Dict[str, Any]:
    """Measure the style-tell false-positive rate on known-human work.

    Feed this documents you are confident a human wrote -- pre-2022
    submissions are ideal. Every document that trips a threshold is, by
    construction, a false positive. Pick a threshold from the resulting table
    rather than choosing one a priori.
    """
    thresholds = thresholds or [0.2, 0.3, 0.4, 0.5, 0.6, 0.8]
    scored = [style_features(d) for d in documents if len(d.strip()) >= MIN_ASSESSABLE_CHARS]
    if not scored:
        return {"ok": False, "error": "no documents long enough to assess"}

    n = len(scored)
    table = []
    for t in thresholds:
        fp = sum(1 for s in scored if s["style_score"] >= t)
        table.append(
            {"threshold": t, "false_positives": fp, "false_positive_rate": round(fp / n, 3)}
        )

    per_tell = {
        k: round(sum(1 for s in scored if s["triggered"][k]) / n, 3) for k in STYLE_THRESHOLDS
    }
    return {
        "ok": True,
        "documents_scored": n,
        "style_score_mean": round(statistics.mean(s["style_score"] for s in scored), 3),
        "style_score_max": max(s["style_score"] for s in scored),
        "false_positive_rate_by_threshold": table,
        "per_tell_trigger_rate": per_tell,
        "how_to_read": (
            "Every document here is known-human, so any trip is a false positive. "
            "per_tell_trigger_rate shows which individual tells misfire most on your "
            "students' real writing -- a tell firing on most human work carries no "
            "information and should be dropped or re-thresholded."
        ),
    }
