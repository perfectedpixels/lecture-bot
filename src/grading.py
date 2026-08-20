"""
Instructor-side grading assistance: assess a student submission against the
course's own grading handbook and return per-criterion findings, a suggested
score, and draft feedback.

Deliberately encodes the grading method the handbook already documents
(data/grading/grading-handbook-512-515.txt) rather than inventing one:
its Performance Scale, its three fast-grading questions, each assignment's
Instructor Evaluation Checklist, and each assignment's Decision Tree score
bands. The model's job is to apply Jason's rubric consistently, not to bring
its own grading philosophy.

This is an INSTRUCTOR tool, so guardrails.STUDENT_INTERFACE_ADDENDUM (never
do a student's work for them) deliberately does NOT apply -- grading is the
instructor's own work. guardrails.BASELINE_RULES still does. Everything it
returns is explicitly a draft for instructor review, never a final grade.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import canvas_assignments as ca
import guardrails
from explore_topic import _extract_json_object

# Grading wants repeatability far more than variety -- two runs over the same
# submission should land on the same score. Kept at 0 for that reason.
GRADING_TEMPERATURE = 0.0
GRADING_MAX_TOKENS = 2048
# Below this, there isn't enough substance to grade fairly; the tool reports
# "not gradable" instead of inventing an assessment of near-empty input.
MIN_GRADABLE_CHARS = 120
MAX_SCORE = 4.0


def _course_policy() -> str:
    """The handbook's own calibration material (philosophy, artifact pipeline,
    Performance Scale, fast-grading method) -- everything before the
    per-assignment rubrics. This is what keeps suggested scores anchored to
    Jason's documented scale rather than a generic A-F intuition."""
    from pathlib import Path

    p = Path(ca.__file__).parent.parent / "data/grading/grading-handbook-512-515.txt"
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8")
    return text.split("--- ASSIGNMENT RUBRICS ---")[0].strip()


def list_rubrics() -> List[str]:
    """Assignment rubric section names available in the handbook."""
    ca._load_handbook()
    return sorted(ca._handbook_sections.keys())


def get_rubric(assignment: str) -> Dict[str, Any]:
    """Resolve a loose assignment name ("persona", "Assignment 2.1",
    "Persona Development") to its full handbook rubric section. Reuses the
    same _HANDBOOK_SLUG_MAP that the student-facing homework-help path uses,
    so instructor and student views can never drift onto different rubrics."""
    ca._load_handbook()
    sections = ca._handbook_sections
    if not sections:
        return {"found": False, "error": "grading handbook not available", "available": []}

    query = assignment.strip().lower()

    # 1. exact section key, 2. substring of a section key, 3. slug map
    for key in sections:
        if key.lower() == query:
            return {"found": True, "assignment": key, "rubric": sections[key]}
    for key in sections:
        if query in key.lower():
            return {"found": True, "assignment": key, "rubric": sections[key]}
    for pattern, key in ca._HANDBOOK_SLUG_MAP.items():
        if pattern in query and key in sections:
            return {"found": True, "assignment": key, "rubric": sections[key]}

    return {"found": False, "error": f"no rubric matches {assignment!r}", "available": sorted(sections)}


def _build_grading_prompt(submission: str, rubric_key: str, rubric: str, policy: str) -> str:
    return f"""You are assisting the instructor with grading a student submission for a graduate UX course. You are NOT talking to the student -- everything you produce is a private draft for the instructor to review, edit, and decide on.

{guardrails.BASELINE_RULES}

COURSE GRADING HANDBOOK (the instructor's own calibration material -- use this scale, not a generic one):
{policy}

RUBRIC FOR THIS ASSIGNMENT ({rubric_key}):
{rubric}

STUDENT SUBMISSION:
{submission}

INSTRUCTIONS:
- Apply the rubric above exactly as written. Do not invent criteria it doesn't contain.
- Use the assignment's Decision Tree to pick the score band, then the Performance Scale to land on a specific value. Name which Decision Tree branch you matched.
- Ground every claim in the submission itself: quote or closely paraphrase the specific text you're reacting to. If you cannot point to evidence, don't make the claim.
- Judge reasoning, synthesis, and framework use. Per the handbook, do NOT let visual polish or formatting drive the score.
- Be honest about weak work. Inflated scores are not kind -- they cost the student the feedback they need.
- If the submission is off-topic, unreadable, or too thin to assess against this rubric, say so via "gradable": false instead of forcing a score.

Return ONLY a JSON object (no markdown fences):
{{
  "gradable": true,
  "suggested_score": 3.5,
  "decision_tree_branch": "which branch of the assignment's decision tree this matched, quoted",
  "confidence": "high | medium | low",
  "strongest_insight": "the single best thing in this submission, per the handbook's fast-grading method",
  "major_gap": "the single most important thing missing or weak",
  "criteria": [
    {{
      "criterion": "an item from the Instructor Evaluation Checklist, verbatim",
      "met": "yes | partial | no",
      "evidence": "specific quote or close paraphrase from the submission",
      "comment": "one sentence on why this rating"
    }}
  ],
  "draft_feedback": "3-5 sentences addressed to the student, in the instructor's voice: what worked, what to strengthen, and why it matters. No score mentioned.",
  "instructor_notes": "anything the instructor should double-check before accepting this -- ambiguity, possible misread, borderline call, or suspected continuity break with prior artifacts"
}}"""


def grade_submission(
    bot,
    submission: str,
    assignment: str,
    max_results: int = 0,
) -> Dict[str, Any]:
    """Assess `submission` against `assignment`'s handbook rubric.

    Returns the parsed assessment plus the rubric it used, so the instructor
    can see exactly what criteria produced the suggestion. `max_results` is
    accepted for signature symmetry with the other tools but unused: grading
    reads the rubric directly from the handbook rather than doing semantic
    retrieval, because a partial/fuzzy rubric chunk would silently change the
    criteria a student is graded against.
    """
    submission = (submission or "").strip()
    if len(submission) < MIN_GRADABLE_CHARS:
        return {
            "gradable": False,
            "error": f"submission is too short to grade fairly ({len(submission)} chars, minimum {MIN_GRADABLE_CHARS})",
        }

    found = get_rubric(assignment)
    if not found.get("found"):
        return {"gradable": False, **found}

    policy = _course_policy()
    prompt = _build_grading_prompt(submission, found["assignment"], found["rubric"], policy)

    response = bot._invoke_model_with_retry(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": GRADING_MAX_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": GRADING_TEMPERATURE,
        }
    )
    body = json.loads(response["body"].read())
    text = body["content"][0]["text"]

    try:
        result = _extract_json_object(text)
    except (json.JSONDecodeError, ValueError):
        # Never fabricate a score from an unparseable response -- hand the raw
        # text back so the instructor can still read it.
        return {"gradable": False, "error": "could not parse structured assessment", "raw": text}

    score = result.get("suggested_score")
    if isinstance(score, (int, float)):
        if not 0 <= score <= MAX_SCORE:
            result["score_warning"] = f"model returned {score}, outside the 0-{MAX_SCORE} scale; treat as unreliable"
    elif result.get("gradable"):
        result["score_warning"] = "model did not return a numeric score"

    result["assignment"] = found["assignment"]
    result["rubric_used"] = found["rubric"]
    result["disclaimer"] = "Draft assessment for instructor review only. Not a final grade; verify before releasing to any student."
    return result
