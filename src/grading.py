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


def _calibration_dir():
    from pathlib import Path

    return Path(ca.__file__).parent.parent / "data/grading/calibration"


def load_calibration(rubric_key: str) -> Optional[Dict[str, Any]]:
    """4.0 calibration for an assignment, or None if none is stored.

    Matched on the calibration file's `assignment` field rather than its
    filename, so a file has to name the handbook section it calibrates
    exactly -- a typo yields no calibration rather than silently calibrating
    the wrong assignment.
    """
    from pathlib import Path

    d = _calibration_dir()
    if not d.exists():
        return None
    for p in sorted(d.glob("*.json")):
        try:
            data = json.loads(Path(p).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"⚠ Skipping unreadable calibration file {p.name}: {e}")
            continue
        if data.get("assignment") == rubric_key:
            return data
    return None


def _format_calibration(cal: Optional[Dict[str, Any]]) -> str:
    """Render calibration into the grading prompt, or an empty string."""
    if not cal:
        return ""

    parts = ["CALIBRATION FOR THIS ASSIGNMENT (what full marks actually look like here):"]

    rules = cal.get("derived_rules") or {}
    if rules.get("what_4_0_looks_like"):
        parts.append(f"\nThe 4.0 bar: {rules['what_4_0_looks_like']}")
    if rules.get("distinguishing_markers"):
        parts.append("\nWhat separates 4.0 from 3.x here:")
        parts += [f"- {m}" for m in rules["distinguishing_markers"]]
    if rules.get("common_failure_modes"):
        parts.append("\nCommon failure modes:")
        parts += [f"- {m}" for m in rules["common_failure_modes"]]

    exemplar = cal.get("exemplar") or {}
    if exemplar.get("text"):
        parts.append(
            f"\nANCHOR SUBMISSION (scored {exemplar.get('score', 4.0)}):\n{exemplar['text']}"
        )
        # Without this, a single anchor drags the model toward surface
        # matching -- penalising a strong submission for picking a different
        # domain, format or length than the anchor happened to use.
        parts.append(
            "\nUse the anchor to calibrate the LEVEL OF REASONING that earns full marks. "
            "Do NOT reward similarity to it or penalise difference from it in topic, "
            "domain, structure, format, or length. A submission that reaches the same "
            "depth of reasoning by a different route is equally a 4.0."
        )

    return "\n".join(parts)


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


def _build_grading_prompt(
    submission: str, rubric_key: str, rubric: str, policy: str, calibration: str = ""
) -> str:
    calibration_block = f"\n{calibration}\n" if calibration else ""
    return f"""You are assisting the instructor with grading a student submission for a graduate UX course. You are NOT talking to the student -- everything you produce is a private draft for the instructor to review, edit, and decide on.

{guardrails.BASELINE_RULES}

COURSE GRADING HANDBOOK (the instructor's own calibration material -- use this scale, not a generic one):
{policy}

RUBRIC FOR THIS ASSIGNMENT ({rubric_key}):
{rubric}
{calibration_block}
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


def derive_calibration(bot, submission: str, assignment: str) -> Dict[str, Any]:
    """Turn a submission the instructor scored 4.0 into draft rubric language.

    Produces the `derived_rules` half of a calibration file: what the 4.0 bar
    is for this assignment, what separates it from 3.x, and the failure modes
    this exemplar avoids. Deliberately outputs *rules* rather than storing the
    submission, so calibration can be kept indefinitely without retaining
    student work -- see data/grading/calibration/README.md.

    This is a drafting aid. Whatever the instructor saves shapes every later
    grade for the assignment, so the output is meant to be read and edited,
    not saved as-is.
    """
    submission = (submission or "").strip()
    if len(submission) < MIN_GRADABLE_CHARS:
        return {"ok": False, "error": f"submission too short to derive calibration from ({len(submission)} chars)"}

    found = get_rubric(assignment)
    if not found.get("found"):
        return {"ok": False, **found}

    prompt = f"""An instructor scored the submission below 4.0 (full marks) for this assignment. Extract what makes it a 4.0, as reusable grading criteria for evaluating OTHER submissions.

{guardrails.BASELINE_RULES}

RUBRIC FOR THIS ASSIGNMENT ({found['assignment']}):
{found['rubric']}

THE 4.0 SUBMISSION:
{submission}

INSTRUCTIONS:
- Describe the QUALITY OF REASONING that earns full marks, not the topic, domain, format, or length this particular submission happened to use. Another student writing about something completely different must be able to hit the same bar.
- Ground each rule in something actually present in this submission, but state it generally enough to apply to other work.
- Tie the rules to the rubric's existing checklist items and decision tree; do not introduce new criteria the rubric doesn't support.
- Failure modes should describe what weaker submissions do INSTEAD, not merely the absence of what this one did.

Return ONLY a JSON object (no markdown fences):
{{
  "what_4_0_looks_like": "2-3 sentences on the bar for full marks on this assignment, transferable across topics",
  "distinguishing_markers": ["3-5 specific things that separate a 4.0 from a 3.x here"],
  "common_failure_modes": ["3-5 things weaker submissions do instead"],
  "notes_for_instructor": "anything ambiguous, or where this exemplar may be atypical and shouldn't be generalised from"
}}"""

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
        rules = _extract_json_object(text)
    except (json.JSONDecodeError, ValueError):
        return {"ok": False, "error": "could not parse derived rules", "raw": text}

    slug = found["assignment"].split(":", 1)[-1].strip().lower().replace(" ", "-")
    return {
        "ok": True,
        "assignment": found["assignment"],
        "suggested_filename": f"{slug}.json",
        "calibration_file": {"assignment": found["assignment"], "derived_rules": rules},
        "next_step": (
            f"Review and edit, then save as data/grading/calibration/{slug}.json. "
            "These rules shape every later grade for this assignment, so read them "
            "before saving. Storing the exemplar text itself is optional and separate "
            "-- see the README in that directory first."
        ),
    }


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
    cal = load_calibration(found["assignment"])
    prompt = _build_grading_prompt(
        submission, found["assignment"], found["rubric"], policy, _format_calibration(cal)
    )

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
    # Make it visible which basis produced this score -- an uncalibrated
    # grade and a calibrated one aren't equally trustworthy, and that
    # shouldn't be invisible in the output.
    result["calibrated"] = bool(cal)
    if cal:
        result["calibration_used"] = {
            "has_derived_rules": bool((cal.get("derived_rules") or {}).get("what_4_0_looks_like")),
            "has_anchor_submission": bool((cal.get("exemplar") or {}).get("text")),
        }
    result["disclaimer"] = "Draft assessment for instructor review only. Not a final grade; verify before releasing to any student."
    return result
