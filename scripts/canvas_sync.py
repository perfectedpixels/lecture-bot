"""
Sync assignments from Canvas LMS API and align with lecture material.

Pulls live assignment data from UW Canvas, detects concept overlap with
lecture content, and outputs an alignment report + chunked files for KB ingestion.

Setup:
    1. Generate a Canvas access token:
       Canvas → Account → Settings → Approved Integrations → + New Access Token
    2. Add to .env:
       CANVAS_API_TOKEN=<your token>
       CANVAS_BASE_URL=https://canvas.uw.edu
       CANVAS_COURSE_IDS=515_ID,512_ID   (comma-separated numeric course IDs)
    3. Run:
       python3 scripts/canvas_sync.py

Docs: https://canvas.instructure.com/doc/api/assignments.html
"""

import os
import re
import json
import hashlib
import requests
from pathlib import Path
from html.parser import HTMLParser
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CANVAS_BASE_URL = os.environ.get("CANVAS_BASE_URL", "https://canvas.uw.edu")
CANVAS_API_TOKEN = os.environ.get("CANVAS_API_TOKEN", "")
CANVAS_COURSE_IDS = [
    cid.strip()
    for cid in os.environ.get("CANVAS_COURSE_IDS", "").split(",")
    if cid.strip()
]

HEADERS = {"Authorization": f"Bearer {CANVAS_API_TOKEN}"}
OUTPUT_DIR = "data/canvas_assignments"
CHUNK_DIR = "data/assignments_chunked"
ALIGNMENT_FILE = "data/canvas_lecture_alignment.json"

# Reuse the same concept keywords from process_assignments.py
CONCEPT_KEYWORDS = {
    "personas": ["persona", "user persona", "empathy map", "archetype"],
    "heuristics": [
        "heuristic", "nielsen", "usability heuristic", "design principle",
    ],
    "usability": [
        "usability", "usability test", "usability study", "usability script",
        "task analysis",
    ],
    "user-research": [
        "interview", "survey", "qualitative", "quantitative", "user research",
        "field study",
    ],
    "prototyping": [
        "prototype", "wireframe", "mockup", "paper prototype", "lo-fi", "hi-fi",
    ],
    "design-thinking": [
        "design thinking", "ideation", "brainstorm", "journey map", "storyboard",
    ],
    "ai-design": [
        "ai", "artificial intelligence", "llm", "agent", "prompt",
        "machine learning",
    ],
    "presentation": [
        "presentation", "pitch", "final project", "deliverable",
    ],
    "branding": [
        "brand", "branding", "identity", "logo", "visual identity",
    ],
    "accessibility": [
        "accessibility", "wcag", "screen reader", "a11y", "assistive",
    ],
}


# ---------------------------------------------------------------------------
# HTML → text
# ---------------------------------------------------------------------------

class _HTMLTextExtractor(HTMLParser):
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

    def get_text(self) -> str:
        raw = "".join(self._parts)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def html_to_text(html: str) -> str:
    ext = _HTMLTextExtractor()
    ext.feed(html)
    return ext.get_text()


# ---------------------------------------------------------------------------
# Canvas API helpers
# ---------------------------------------------------------------------------

def _api_get(path: str, params: Optional[dict] = None) -> list:
    """GET with pagination. Returns aggregated list of JSON objects."""
    url = f"{CANVAS_BASE_URL}/api/v1{path}"
    all_items: list = []
    while url:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            all_items.extend(data)
        else:
            all_items.append(data)
        # Canvas pagination via Link header
        url = None
        link_header = resp.headers.get("Link", "")
        for part in link_header.split(","):
            if 'rel="next"' in part:
                url = part.split("<")[1].split(">")[0]
                params = None  # params are baked into the next URL
                break
    return all_items


def fetch_course_info(course_id: str) -> dict:
    """Fetch basic course metadata."""
    items = _api_get(f"/courses/{course_id}")
    return items[0] if items else {}


def fetch_assignments(course_id: str) -> List[dict]:
    """Fetch all assignments for a course, including descriptions."""
    return _api_get(
        f"/courses/{course_id}/assignments",
        params={
            "per_page": "100",
            "order_by": "due_at",
            "include[]": "all_dates",
        },
    )


def fetch_modules(course_id: str) -> List[dict]:
    """Fetch course modules (weeks/units) with items."""
    modules = _api_get(f"/courses/{course_id}/modules", params={"per_page": "100"})
    for mod in modules:
        mod["items"] = _api_get(
            f"/courses/{course_id}/modules/{mod['id']}/items",
            params={"per_page": "100"},
        )
    return modules


# ---------------------------------------------------------------------------
# Concept detection & lecture alignment
# ---------------------------------------------------------------------------

def detect_concepts(text: str) -> List[str]:
    text_lower = text.lower()
    found = []
    for concept, keywords in CONCEPT_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            found.append(concept)
    return found if found else ["general"]


def load_teaching_concepts(path: str = "data/teaching_concepts.json") -> dict:
    if Path(path).exists():
        return json.loads(Path(path).read_text())
    return {}


def align_assignment_to_concepts(
    assignment_text: str,
    teaching_concepts: dict,
) -> List[Dict]:
    """
    Score each teaching concept against the assignment text.
    Returns sorted list of {concept, score, matched_keywords}.
    """
    text_lower = assignment_text.lower()
    results = []
    for concept_name, concept_data in teaching_concepts.items():
        matched = []
        for kw in concept_data.get("keywords", []):
            if kw.lower() in text_lower:
                matched.append(kw)
        if matched:
            results.append({
                "concept": concept_name,
                "score": len(matched),
                "matched_keywords": matched,
                "definition": concept_data.get("definition", ""),
            })
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Chunking (same params as other scripts: 400 tokens, 50 overlap)
# ---------------------------------------------------------------------------

def chunk_text(text: str, max_tokens: int = 400, overlap: int = 50) -> List[str]:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + max_tokens, len(words))
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk.strip())
        start += max_tokens - overlap
    return chunks


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process_course(course_id: str, teaching_concepts: dict) -> dict:
    """
    Pull assignments from Canvas, detect concepts, align with lectures,
    and write chunked files for KB ingestion.
    """
    print(f"\n{'='*60}")
    course = fetch_course_info(course_id)
    course_name = course.get("name", f"Course {course_id}")
    course_code = course.get("course_code", course_id)
    print(f"Course: {course_name} ({course_code})")
    print(f"{'='*60}")

    assignments = fetch_assignments(course_id)
    print(f"  Found {len(assignments)} assignments")

    out_raw = Path(OUTPUT_DIR) / course_code
    out_raw.mkdir(parents=True, exist_ok=True)
    out_chunks = Path(CHUNK_DIR)
    out_chunks.mkdir(parents=True, exist_ok=True)

    alignment_results = []

    for asn in assignments:
        name = asn.get("name", "Untitled")
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        desc_html = asn.get("description") or ""
        desc_text = html_to_text(desc_html) if desc_html else ""
        due = asn.get("due_at", "no due date")
        points = asn.get("points_possible", 0)

        # Combine name + description for concept detection
        full_text = f"{name}\n\n{desc_text}"

        if len(full_text.split()) < 15:
            print(f"  Skipping {name} (too short)")
            continue

        concepts = detect_concepts(full_text)
        lecture_alignment = align_assignment_to_concepts(full_text, teaching_concepts)

        print(
            f"  {name}: {len(desc_text.split())} words | "
            f"concepts: {concepts} | "
            f"aligned to {len(lecture_alignment)} teaching concepts"
        )

        # Save raw JSON
        raw_path = out_raw / f"{slug}.json"
        raw_path.write_text(json.dumps({
            "id": asn["id"],
            "name": name,
            "slug": slug,
            "due_at": due,
            "points_possible": points,
            "description_text": desc_text,
            "concepts": concepts,
            "lecture_alignment": lecture_alignment[:5],
            "html_url": asn.get("html_url", ""),
        }, indent=2))

        # Chunk for KB ingestion
        chunks = chunk_text(full_text, max_tokens=400, overlap=50)
        for i, chunk in enumerate(chunks):
            content_hash = hashlib.md5(chunk.encode()).hexdigest()[:12]
            chunk_filename = f"assignment-{course_code}-{slug}-part-{i:04d}-{content_hash}.txt"
            top_concepts = [a["concept"] for a in lecture_alignment[:3]]
            header = (
                f"[Assignment: {name}]\n"
                f"[Course: {course_code}]\n"
                f"[Concepts: {', '.join(concepts)}]\n"
                f"[Aligned Teaching Concepts: {', '.join(top_concepts)}]\n"
                f"[Due: {due}]\n\n"
            )
            (out_chunks / chunk_filename).write_text(header + chunk, encoding="utf-8")

        alignment_results.append({
            "course": course_code,
            "assignment": name,
            "slug": slug,
            "due_at": due,
            "points": points,
            "concepts": concepts,
            "top_lecture_alignments": [
                {"concept": a["concept"], "score": a["score"], "keywords": a["matched_keywords"]}
                for a in lecture_alignment[:5]
            ],
            "chunk_count": len(chunks),
        })

    return {
        "course_id": course_id,
        "course_name": course_name,
        "course_code": course_code,
        "assignments": alignment_results,
    }


def print_alignment_report(results: List[dict]):
    """Print a human-readable alignment summary."""
    print(f"\n{'='*60}")
    print("CANVAS ↔ LECTURE ALIGNMENT REPORT")
    print(f"{'='*60}")

    for course in results:
        print(f"\n📚 {course['course_name']} ({course['course_code']})")
        print(f"   {len(course['assignments'])} assignments processed\n")

        for asn in course["assignments"]:
            print(f"   📝 {asn['assignment']}")
            print(f"      Due: {asn['due_at']} | Points: {asn['points']} | Chunks: {asn['chunk_count']}")
            print(f"      Concepts: {', '.join(asn['concepts'])}")
            if asn["top_lecture_alignments"]:
                print("      Lecture alignment:")
                for align in asn["top_lecture_alignments"][:3]:
                    print(f"        → {align['concept']} (score {align['score']}: {', '.join(align['keywords'][:4])})")
            else:
                print("      ⚠ No strong lecture alignment found")
            print()


def main():
    if not CANVAS_API_TOKEN:
        print("ERROR: CANVAS_API_TOKEN not set in .env")
        print("Generate one at: Canvas → Account → Settings → Approved Integrations → + New Access Token")
        return

    if not CANVAS_COURSE_IDS:
        print("ERROR: CANVAS_COURSE_IDS not set in .env")
        print("Set comma-separated numeric course IDs, e.g.: CANVAS_COURSE_IDS=12345,67890")
        return

    teaching_concepts = load_teaching_concepts()
    if teaching_concepts:
        print(f"Loaded {len(teaching_concepts)} teaching concepts for alignment")
    else:
        print("⚠ No teaching_concepts.json found — alignment will be limited to keyword detection")

    all_results = []
    for course_id in CANVAS_COURSE_IDS:
        try:
            result = process_course(course_id, teaching_concepts)
            all_results.append(result)
        except requests.HTTPError as e:
            print(f"\n❌ Failed to fetch course {course_id}: {e}")
            if e.response is not None and e.response.status_code == 401:
                print("   → Token may be expired or invalid. Regenerate at Canvas → Settings → Approved Integrations")
            elif e.response is not None and e.response.status_code == 403:
                print("   → You may not have access to this course. Verify the course ID and your enrollment.")
            continue

    # Save alignment report
    Path(ALIGNMENT_FILE).write_text(json.dumps(all_results, indent=2))
    print(f"\nAlignment data saved to {ALIGNMENT_FILE}")

    # Print report
    print_alignment_report(all_results)

    total_chunks = sum(
        asn["chunk_count"]
        for course in all_results
        for asn in course["assignments"]
    )
    print(f"\nTotal: {total_chunks} chunks ready in {CHUNK_DIR}/")
    print("Next: upload to S3 and sync the Bedrock KB to index the new content.")


if __name__ == "__main__":
    main()
