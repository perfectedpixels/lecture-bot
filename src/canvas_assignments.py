"""
Canvas assignment helper — identifies the next upcoming assignment
and provides rubric-grounded context for the homework help feature.

Used by the Streamlit app to show an "Assignment X Homework Help" prompt
and feed rubric + description context into the bot for student Q&A.
"""

import os
import re
import json
import requests
from datetime import datetime, timezone
from typing import Optional, List, Dict
from html.parser import HTMLParser

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

CANVAS_BASE_URL = os.environ.get("CANVAS_BASE_URL", "https://canvas.uw.edu")
CANVAS_API_TOKEN = os.environ.get("CANVAS_API_TOKEN", "")
HEADERS = {"Authorization": f"Bearer {CANVAS_API_TOKEN}"}

# ---------------------------------------------------------------------------
# Grading handbook rubric lookup
# ---------------------------------------------------------------------------
# Maps Canvas assignment name patterns (lowercased substrings) to handbook
# rubric section keys.  The handbook is split on "Assignment N:" headers.

_HANDBOOK_SLUG_MAP = {
    "persona": "Assignment 2.1: Persona Development",
    "journey map": "Assignment 3: Customer Journey Map",
    "paper prototype": "Assignment 4: Paper Prototype",
    "wireframe": "Assignment 5: Wireframes",
    "design aesthetics": "Assignment 2: Design Aesthetics Evaluation",
    "design principles": "Assignment 2: Design Aesthetics Evaluation",
    "heuristic": "Assignment 6: Heuristic Evaluation",
}

_handbook_sections: Dict[str, str] = {}


def _load_handbook(path: str = "data/grading/grading-handbook-512-515.txt"):
    """Parse the grading handbook into per-assignment sections (lazy, once)."""
    global _handbook_sections
    if _handbook_sections:
        return
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        # Try relative to the app/ directory (Streamlit working dir)
        p = Path(__file__).parent.parent / path
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    # Split on the rubrics marker
    if "--- ASSIGNMENT RUBRICS ---" not in text:
        return
    rubrics_part = text.split("--- ASSIGNMENT RUBRICS ---")[1]
    # Remove instructor notes
    if "--- INSTRUCTOR NOTES ---" in rubrics_part:
        rubrics_part = rubrics_part.split("--- INSTRUCTOR NOTES ---")[0]
    # Split into individual assignment sections
    current_key = None
    current_lines: list = []
    for line in rubrics_part.split("\n"):
        # Check if this line starts a new assignment section
        if re.match(r"^Assignment \d", line.strip()):
            if current_key and current_lines:
                _handbook_sections[current_key] = "\n".join(current_lines).strip()
            current_key = line.strip()
            current_lines = [line]
        else:
            current_lines.append(line)
    if current_key and current_lines:
        _handbook_sections[current_key] = "\n".join(current_lines).strip()
    if _handbook_sections:
        print(f"✓ Loaded {len(_handbook_sections)} handbook rubric sections")


def _find_handbook_rubric(assignment_name: str) -> str:
    """Find the detailed handbook rubric for a Canvas assignment by name matching."""
    _load_handbook()
    if not _handbook_sections:
        return ""
    name_lower = assignment_name.lower()
    for pattern, handbook_key in _HANDBOOK_SLUG_MAP.items():
        if pattern in name_lower:
            section = _handbook_sections.get(handbook_key, "")
            if section:
                return f"DETAILED GRADING RUBRIC (from instructor handbook):\n{section}"
    return ""


# ---------------------------------------------------------------------------
# HTML → text
# ---------------------------------------------------------------------------

class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self._skip = True
        if tag in ("p", "br", "div", "h1", "h2", "h3", "h4", "li", "tr"):
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head"):
            self._skip = False
        if tag in ("p", "div", "h1", "h2", "h3", "h4", "ul", "ol", "table"):
            self._parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self._parts.append(data)

    def text(self) -> str:
        raw = "".join(self._parts)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def _html_to_text(html: str) -> str:
    p = _HTMLText()
    p.feed(html or "")
    return p.text()


# ---------------------------------------------------------------------------
# Canvas API
# ---------------------------------------------------------------------------

def _api_get(path: str, params: Optional[dict] = None) -> list:
    url = f"{CANVAS_BASE_URL}/api/v1{path}"
    all_items: list = []
    while url:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            all_items.extend(data)
        else:
            all_items.append(data)
        url = None
        for part in resp.headers.get("Link", "").split(","):
            if 'rel="next"' in part:
                url = part.split("<")[1].split(">")[0]
                params = None
                break
    return all_items


def fetch_assignments(course_id: str) -> List[dict]:
    """Fetch all assignments for a course including rubric data."""
    return _api_get(
        f"/courses/{course_id}/assignments",
        params={"per_page": "100", "order_by": "due_at", "include[]": "rubric_assessment"},
    )


def get_upcoming_assignment(course_id: str) -> Optional[Dict]:
    """
    Return the next assignment whose due date is in the future.
    Falls back to the most recently due assignment if none are upcoming.
    Includes rubric text and cleaned description.
    """
    if not CANVAS_API_TOKEN:
        return None

    try:
        assignments = fetch_assignments(course_id)
    except Exception as e:
        print(f"⚠ Canvas API error: {e}")
        return None

    now = datetime.now(timezone.utc)
    upcoming = []
    past = []

    for a in assignments:
        due = a.get("due_at")
        if not due:
            continue
        try:
            due_dt = datetime.fromisoformat(due.replace("Z", "+00:00"))
        except ValueError:
            continue
        entry = _build_entry(a, due_dt)
        if due_dt > now:
            upcoming.append(entry)
        else:
            past.append(entry)

    # Sort upcoming by soonest first, past by most recent first
    upcoming.sort(key=lambda x: x["due_dt"])
    past.sort(key=lambda x: x["due_dt"], reverse=True)

    return upcoming[0] if upcoming else (past[0] if past else None)


def get_all_upcoming(course_id: str) -> List[Dict]:
    """Return all future assignments, soonest first."""
    if not CANVAS_API_TOKEN:
        return []

    try:
        assignments = fetch_assignments(course_id)
    except Exception as e:
        print(f"⚠ Canvas API error: {e}")
        return []

    now = datetime.now(timezone.utc)
    upcoming = []
    for a in assignments:
        due = a.get("due_at")
        if not due:
            continue
        try:
            due_dt = datetime.fromisoformat(due.replace("Z", "+00:00"))
        except ValueError:
            continue
        if due_dt > now:
            upcoming.append(_build_entry(a, due_dt))

    upcoming.sort(key=lambda x: x["due_dt"])
    return upcoming


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_entry(a: dict, due_dt: datetime) -> Dict:
    """Build a normalized assignment dict from Canvas API response."""
    desc_text = _html_to_text(a.get("description", ""))
    rubric_text = _format_rubric(a.get("rubric"))
    rubric_title = (a.get("rubric_settings") or {}).get("title", "")
    points = a.get("points_possible", 0)
    name = a["name"]

    # If Canvas rubric is missing or generic (single criterion), pull from handbook
    handbook_rubric = ""
    canvas_criteria_count = len(a.get("rubric") or [])
    if canvas_criteria_count <= 1:
        handbook_rubric = _find_handbook_rubric(name)

    # Convert UTC to Pacific for display (Canvas stores all dates in UTC)
    try:
        from zoneinfo import ZoneInfo
        display_dt = due_dt.astimezone(ZoneInfo("America/Los_Angeles"))
    except ImportError:
        # Python < 3.9 fallback: UTC-7 (PDT)
        from datetime import timedelta as _td
        display_dt = due_dt - _td(hours=7)

    return {
        "id": a["id"],
        "name": name,
        "due_at": a["due_at"],
        "due_dt": due_dt,
        "due_display": display_dt.strftime("%A, %B %-d"),
        "points": points,
        "description": desc_text,
        "rubric_text": rubric_text,
        "rubric_title": rubric_title,
        "handbook_rubric": handbook_rubric,
        "html_url": a.get("html_url", ""),
    }


def _format_rubric(rubric: Optional[list]) -> str:
    """Convert Canvas rubric JSON into readable text for the bot prompt."""
    if not rubric:
        return ""
    lines = ["RUBRIC:"]
    for criterion in rubric:
        desc = criterion.get("description", "Criterion")
        long_desc = criterion.get("long_description") or ""
        pts = criterion.get("points", 0)
        lines.append(f"\n  {desc} ({pts} pts)")
        if long_desc:
            lines.append(f"    {long_desc}")
        ratings = criterion.get("ratings", [])
        if ratings:
            lines.append("    Rating levels:")
            for r in ratings:
                r_desc = r.get("description", "")
                r_long = r.get("long_description", "")
                r_pts = r.get("points", "")
                detail = f" — {r_long}" if r_long else ""
                lines.append(f"      • {r_desc} ({r_pts} pts){detail}")
    return "\n".join(lines)


def build_homework_help_prompt(assignment: Dict, student_question: str, lang: str = "en") -> str:
    """
    Build a prompt that grounds the bot in the assignment rubric + description
    so it can give rubric-aware feedback to the student's question.
    Uses the detailed handbook rubric when the Canvas rubric is missing/generic.
    """
    canvas_rubric = assignment.get("rubric_text", "")
    handbook_rubric = assignment.get("handbook_rubric", "")

    # Prefer handbook rubric (more detailed); include Canvas rubric too if present
    if handbook_rubric and canvas_rubric:
        rubric_block = f"{handbook_rubric}\n\n{canvas_rubric}"
    elif handbook_rubric:
        rubric_block = handbook_rubric
    elif canvas_rubric:
        rubric_block = canvas_rubric
    else:
        rubric_block = "(No rubric available for this assignment.)"

    desc_block = assignment["description"][:2000] if assignment["description"] else "(No description available.)"

    if lang == "zh":
        return f"""你是 Professor Levine，正在帮助学生完成以下作业。

作业名称：{assignment['name']}
截止日期：{assignment['due_display']}
分值：{assignment['points']} 分

作业说明：
{desc_block}

{rubric_block}

学生的问题：{student_question}

请用简体中文回答。根据评分标准和作业要求，给出具体、可操作的建议，帮助学生达到最高评分等级。
使用评分标准中的具体评价维度（如设计推理、框架应用、洞察质量等）来指导你的建议。
引用课程讲座中的相关概念和框架来支持你的建议。
绝对不要替学生写作业、改写他们的内容、或生成任何可直接提交的文本。只解释哪些方面需要改进、为什么需要改进，并指出相关的概念和框架，让学生自己思考和完成。"""

    return f"""You are {assignment.get('_persona', 'Professor Levine')}, helping a student with an upcoming assignment.

ASSIGNMENT: {assignment['name']}
DUE: {assignment['due_display']}
POINTS: {assignment['points']}

ASSIGNMENT DESCRIPTION:
{desc_block}

{rubric_block}

STUDENT'S QUESTION: {student_question}

INSTRUCTIONS:
- Give specific, actionable advice grounded in the rubric criteria above.
- Use the specific evaluation dimensions from the rubric (e.g., design reasoning, framework application, insight quality, artifact completeness) to structure your guidance.
- When the rubric includes a decision tree or checklist, reference those specific criteria so the student knows exactly what to aim for.
- Help the student understand what a 4.0 (Exceptional) submission looks like vs. a 3.x or lower.
- Reference relevant concepts and frameworks from your lectures to support your guidance.
- NEVER write, rewrite, or fix the student's work. Do not produce assignment text, persona descriptions, journey maps, wireframe labels, rubric responses, or any deliverable content on their behalf.
- Instead, explain WHAT needs improvement and WHY, referencing the rubric dimensions. Point them to the right concepts and frameworks, then let them do the thinking and writing.
- If a student pastes their draft and asks you to "fix it" or "make it better," identify the specific rubric dimensions where it falls short and explain what stronger work looks like — but do not rewrite it.
- If their question is vague, ask a clarifying question to help them focus.
- Be encouraging but honest about what the rubric expects."""
