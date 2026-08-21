#!/usr/bin/env python3
"""
One-step transcript ingestion pipeline.

Drop raw .txt or .rtf files into data/new_lectures/, then run:

    python3 scripts/ingest_transcripts.py

The script will:
  1. Convert RTF → text (if any .rtf files)
  2. Scrub timestamps, speaker labels, and filler words
  3. Detect concepts via keyword matching
  4. Chunk into 400-token segments with 50-token overlap
  5. Write tagged chunks with inline metadata headers
  6. Upload to S3 (perfectpixels-kb-docs/kb-clean/v1/)
  7. Move originals to data/new_lectures/done/

After running, sync the Bedrock KB in the AWS console to index
the new content.
"""

import os
import re
import hashlib
import boto3
from pathlib import Path

from kb_metadata import write_sidecar, upload_chunk_with_sidecar

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

INPUT_DIR = "data/new_lectures"
OUTPUT_DIR = "data/lectures_chunked"
S3_BUCKET = "perfectpixels-kb-docs"
S3_PREFIX = "kb-clean/v1/"
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
SPEAKER_NAME = "Jason Levine"

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
        "artificial intelligence", "machine learning", "llm", "generative ai",
        "neural network", "ai agent",
    ],
    "branding": ["brand", "branding", "identity", "logo", "visual identity"],
    "accessibility": [
        "accessibility", "wcag", "screen reader", "a11y", "assistive",
    ],
    "presentation": ["presentation", "pitch", "final project", "deliverable"],
}


# ---------------------------------------------------------------------------
# RTF conversion
# ---------------------------------------------------------------------------

def convert_rtf(rtf_path: Path) -> str:
    """Convert RTF to plain text. Requires striprtf."""
    try:
        from striprtf.striprtf import rtf_to_text
        raw = rtf_path.read_text(encoding="utf-8", errors="replace")
        return rtf_to_text(raw)
    except ImportError:
        print("  ⚠ striprtf not installed — run: pip install striprtf")
        return ""


# ---------------------------------------------------------------------------
# Transcript scrubbing
# ---------------------------------------------------------------------------

_TIMESTAMP_RE = re.compile(
    r"""
    \[?\(?\d{1,2}:\d{2}(?::\d{2})?\)?\]?  # [0:12:34] or (12:34) or 1:23:45
    """,
    re.VERBOSE,
)

_FILLER_RE = re.compile(
    r"\b(um+|uh+|ah+|er+|like,?\s|you know,?\s|I mean,?\s|sort of,?\s|kind of,?\s)",
    re.IGNORECASE,
)


def strip_webvtt(text: str) -> str:
    """Remove WEBVTT structure: the header, cue numbers, and cue timing lines.

    Zoom exports transcripts as WEBVTT, which interleaves the spoken text with
    a cue number and a `00:00:04.850 --> 00:00:07.650` timing line for every
    utterance. _TIMESTAMP_RE below cannot handle this: it matches the `00:00:04`
    portion only, leaving `.850 --> .650` plus a bare cue number behind. A
    survey of the live KB found this had already happened to 854 chunks (26% of
    the corpus, ~187k words) covering every recent lecture -- roughly a fifth of
    the tokens in those chunks are timing debris competing with real content in
    the embeddings.

    Matching is structural rather than regex-per-line: a bare integer is only
    dropped when the following line is actually a cue timing, so a line of prose
    that happens to be a number survives."""
    if "-->" not in text:
        return text
    lines = text.splitlines()
    out, i, n = [], 0, len(lines)
    while i < n:
        stripped = lines[i].strip()
        if stripped.upper().startswith("WEBVTT") or stripped.startswith("NOTE "):
            i += 1
            continue
        # Cue number, but only when the next line confirms it by being a timing.
        if stripped.isdigit() and i + 1 < n and "-->" in lines[i + 1]:
            i += 2
            continue
        if "-->" in stripped:
            i += 1
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def scrub_transcript(text: str, speaker: str = SPEAKER_NAME) -> str:
    """Remove timestamps, speaker labels, filler words, and collapse whitespace."""
    # WEBVTT structure first -- _TIMESTAMP_RE mangles it rather than removing it.
    text = strip_webvtt(text)

    # Timestamps
    text = _TIMESTAMP_RE.sub("", text)

    # Speaker labels: "Jason Levine:", "[Jason Levine]", "Jason Levine -"
    for pat in [
        rf"{re.escape(speaker)}\s*[:\-|]",
        rf"\[{re.escape(speaker)}\]",
    ]:
        text = re.sub(pat, "", text, flags=re.IGNORECASE)

    # Filler words (light pass — keeps natural flow)
    text = _FILLER_RE.sub("", text)

    # Clean up artifacts from filler removal (double commas, leading commas)
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r"\s,", ",", text)

    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Concept detection
# ---------------------------------------------------------------------------

def detect_concepts(text: str) -> list:
    text_lower = text.lower()
    found = []
    for concept, keywords in CONCEPT_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            found.append(concept)
    return found if found else ["general"]


# ---------------------------------------------------------------------------
# Chunking (400 tokens, 50 overlap — matches existing pipeline)
# ---------------------------------------------------------------------------

def chunk_text(text: str, max_tokens: int = 400, overlap: int = 50) -> list:
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
# S3 duplicate check
# ---------------------------------------------------------------------------

def get_existing_lecture_names(bucket: str, prefix: str, local_dir: str = OUTPUT_DIR) -> set:
    """
    Find lecture names that already have chunks, checking local directories
    first (fast, no permissions needed) then S3 as fallback.
    """
    existing = set()
    _chunk_re = re.compile(r"^lecture-(.+)-part-\d{4}-[a-f0-9]+\.txt$")

    # 1. Check local chunks directory (new pipeline output)
    local_path = Path(local_dir)
    if local_path.exists():
        for f in local_path.glob("lecture-*.txt"):
            m = _chunk_re.match(f.name)
            if m:
                existing.add(m.group(1))

    # 2. Check done/ folder for previously ingested originals
    done_path = Path(INPUT_DIR) / "done"
    if done_path.exists():
        for f in list(done_path.glob("*.txt")) + list(done_path.glob("*.rtf")):
            existing.add(f.stem)

    # 3. Check raw_transcripts/ (original pipeline source)
    raw_path = Path("data/raw_transcripts")
    if raw_path.exists():
        for f in list(raw_path.glob("*.txt")) + list(raw_path.glob("*.rtf")):
            existing.add(f.stem)

    # 4. Check processed_transcripts/ chunk names (old pipeline output)
    proc_path = Path("data/processed_transcripts")
    if proc_path.exists():
        for f in proc_path.glob("*_chunk_000.txt"):
            # "Amazon Trade-In_chunk_000.txt" → "Amazon Trade-In"
            existing.add(f.name.replace("_chunk_000.txt", ""))

    # 5. Try S3 as additional check (may fail if ListObjects not permitted)
    try:
        s3 = boto3.client("s3", region_name=AWS_REGION)
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"].split("/")[-1]
                if key.startswith("lecture-"):
                    m = _chunk_re.match(key)
                    if m:
                        existing.add(m.group(1))
    except Exception:
        pass  # S3 list not permitted — local checks are sufficient

    return existing


# ---------------------------------------------------------------------------
# S3 upload
# ---------------------------------------------------------------------------

def upload_chunks(output_dir: str, bucket: str, prefix: str, file_prefix: str = "lecture-") -> int:
    s3 = boto3.client("s3", region_name=AWS_REGION)
    out = Path(output_dir)
    uploaded = 0
    for f in sorted(out.glob(f"{file_prefix}*.txt")):
        upload_chunk_with_sidecar(s3, f, bucket, f"{prefix}{f.name}")
        uploaded += 1
    return uploaded


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def ingest(input_dir: str = INPUT_DIR, output_dir: str = OUTPUT_DIR, force: bool = False,
           doc_type: str = "lecture", layer: str = "reference"):
    file_prefix = "lecture-" if doc_type == "lecture" else f"{doc_type}-"
    inp = Path(input_dir)
    out = Path(output_dir)
    inp.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)

    # Gather .txt and .rtf files
    files = sorted(list(inp.glob("*.txt")) + list(inp.glob("*.rtf")))
    if not files:
        print(f"No .txt or .rtf files in {input_dir}/")
        print(f"Drop your raw transcripts there and re-run.")
        return

    print(f"Found {len(files)} file(s) in {input_dir}/\n")

    # Check S3 for existing lectures to avoid duplicates
    if force:
        print("--force: skipping duplicate check\n")
        existing_names = set()
    else:
        print("Checking S3 for existing lectures...")
        existing_names = get_existing_lecture_names(S3_BUCKET, S3_PREFIX)
        if existing_names:
            print(f"  Found {len(existing_names)} existing lecture(s) in S3\n")
        else:
            print("  No existing lectures found (or S3 check skipped)\n")

    all_chunks = []
    skipped_dupes = []

    for filepath in files:
        filename = filepath.stem

        # Dedup: check if this lecture name already has chunks in S3
        if filename in existing_names:
            print(f"  ⏭ Skipping {filepath.name} — already in KB (use --force to re-ingest)")
            skipped_dupes.append(filepath.name)
            continue

        # Read / convert
        if filepath.suffix.lower() == ".rtf":
            print(f"  Converting RTF: {filepath.name}")
            text = convert_rtf(filepath)
        else:
            text = filepath.read_text(encoding="utf-8", errors="replace")

        if not text or len(text.split()) < 20:
            print(f"  Skipping {filepath.name} (too short)")
            continue

        # Scrub
        text = scrub_transcript(text)
        word_count = len(text.split())

        # Detect concepts
        concepts = detect_concepts(text)

        # Chunk
        chunks = chunk_text(text, max_tokens=400, overlap=50)

        print(
            f"  {filepath.name}: {word_count} words → {len(chunks)} chunks "
            f"| concepts: {concepts}"
        )

        # Write tagged chunks
        for i, chunk in enumerate(chunks):
            content_hash = hashlib.md5(chunk.encode()).hexdigest()[:12]
            chunk_filename = f"{file_prefix}{filename}-part-{i:04d}-{content_hash}.txt"
            label = "Lecture" if doc_type == "lecture" else doc_type.title()
            header = (
                f"[{label}: {filename.replace('-', ' ').replace('_', ' ').title()}]\n"
                f"[Concepts: {', '.join(concepts)}]\n"
                f"[Type: {doc_type}]\n\n"
            )
            chunk_path = out / chunk_filename
            chunk_path.write_text(header + chunk, encoding="utf-8")
            write_sidecar(chunk_path, layer=layer, doc_type=doc_type, concepts=concepts)
            all_chunks.append(chunk_filename)

    if not all_chunks:
        print("\nNo chunks produced.")
        return

    print(f"\nTotal: {len(all_chunks)} chunks in {output_dir}/\n")

    # Upload to S3
    print(f"Uploading to s3://{S3_BUCKET}/{S3_PREFIX} ...")
    uploaded = upload_chunks(output_dir, S3_BUCKET, S3_PREFIX, file_prefix)
    print(f"Uploaded {uploaded} chunks.\n")

    # Move originals to done/
    done = inp / "done"
    done.mkdir(exist_ok=True)
    for f in files:
        f.rename(done / f.name)
    print(f"Moved originals to {done}/")

    if skipped_dupes:
        print(f"\n⏭ Skipped {len(skipped_dupes)} duplicate(s): {', '.join(skipped_dupes)}")
        print("  Use --force to re-ingest them.")

    print("\nDone! Sync the Bedrock KB in the AWS console to index the new content.")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input-dir", default=INPUT_DIR)
    ap.add_argument("--output-dir", default=OUTPUT_DIR)
    ap.add_argument("--force", action="store_true", help="re-ingest even if the name already exists")
    ap.add_argument("--doc-type", default="lecture",
                    help="lecture (default) | framework | case-study | ...")
    ap.add_argument("--layer", default="reference",
                    help='reference (default) | directive -- "directive" governs grading, use with care')
    a = ap.parse_args()
    ingest(input_dir=a.input_dir, output_dir=a.output_dir, force=a.force,
           doc_type=a.doc_type, layer=a.layer)
