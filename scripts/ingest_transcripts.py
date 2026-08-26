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

import json
import os
import re
import hashlib
import boto3
from pathlib import Path

from kb_metadata import write_sidecar, upload_chunk_with_sidecar, get_policy
from kbpolicy import blocking

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

# Disfluencies. Anchored on BOTH sides: the previous pattern had no trailing
# boundary, so `er+` ate the head of "error" -> "or", `ah+` of "ahead" -> "ead",
# and `um+` of "umbrella" -> "brella". Verified against the May 21 transcript,
# where it had already damaged four occurrences of "ahead" and one "error".
_FILLER_RE = re.compile(
    r"\b(?:u+m+|u+h+|e+r+m+|h+m+|a+h+|o+h+|uh[- ]?huh|mm[- ]?hmm)\b[,.]?\s*",
    re.IGNORECASE,
)

# Discourse markers, only when comma-delimited -- which is how they appear as
# filler. The old pattern stripped every "like ", turning "they like to admit"
# into "they to admit" and "we like to think" into "we to think". Requiring the
# commas keeps "like" as a verb or preposition intact.
_MARKER_RE = re.compile(
    r",\s*(?:you know|i mean|sort of|kind of|like|right|okay|so)\s*,",
    re.IGNORECASE,
)

# Whole utterances carrying no content -- the "yeah" / "mm-hmm" backchannel that
# fills a recorded class. Applied per line, which after WEBVTT stripping is one
# spoken utterance. Deliberately excludes "yes", "no", "good", "correct":
# standing alone those are often a real answer to a real question.
_ASIDE_LINE_RE = re.compile(
    r"^\s*(?:"
    r"yeah|yep|yup|uh[- ]?huh|mm[- ]?hmm|hmm|okay|ok|alright|all right|right|"
    r"sure|cool|nice|thanks|thank you|hi|hello|hey|bye|goodbye|exactly|"
    r"oh|ah|um|uh|sorry|excuse me|one sec|one second|hold on"
    r")[\s,.!?…]*$",
    re.IGNORECASE,
)

# Recorded-meeting pleasantries and audio-check chatter. These recur in every
# Zoom lecture and carry no teaching content.
_PLEASANTRY_RE = re.compile(
    r"\b(?:"
    r"how are you(?: doing| today)?|how's everyone|how is everyone|"
    r"can you hear me|can everyone hear me|can everybody hear me|"
    r"are you able to hear me|is my (?:audio|screen|mic) (?:working|okay|ok)|"
    r"nice to see you|good to see you|good morning|good afternoon|good evening|"
    r"let me share my screen|can you see my screen|sorry about that"
    r")\b[\s,.!?…]*",
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

    # Drop whole backchannel utterances BEFORE collapsing lines, while each
    # line is still one utterance from the WEBVTT cue structure.
    text = "\n".join(l for l in text.splitlines() if not _ASIDE_LINE_RE.match(l))

    # Meeting pleasantries and audio-check chatter
    text = _PLEASANTRY_RE.sub("", text)

    # Comma-delimited discourse markers, then disfluencies
    text = _MARKER_RE.sub(", ", text)
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

def normalize_doc_name(name: str) -> str:
    """Reduce a filename or S3 chunk key to a comparable document identity.

    Four pipelines have written into this KB, each with its own naming scheme:

        UX Studio Week 8 - using AI tools.txt                  (an upload)
        ux-studio-week-8---using-ai-tools-txt-83d9...-part-0000.txt
        ux-studio-week-2-personas-chunk-000-txt-b634...-part-0000.txt
        lecture-GMT20260402-010351_Recording.transcript-part-0000-b46e....txt

    All four collapse to the same string here, so a duplicate is recognized no
    matter which pipeline first ingested it. The previous check matched only
    `^lecture-...`, which could see 222 of 3,511 keys -- 94% of the corpus was
    invisible to it, and re-uploading an existing lecture silently produced a
    second copy. That is how the KB reached 47% duplication."""
    s = re.sub(r"\.(txt|md|rtf)$", "", name, flags=re.I)
    s = re.sub(r"-part-\d{4}", "", s)
    s = re.sub(r"[-_]chunk[-_]\d+", "", s, flags=re.I)
    s = re.sub(r"[-_][0-9a-f]{12}\b", "", s)
    s = re.sub(r"^(lecture|framework|rubric|assignment|case-study)-", "", s, flags=re.I)
    s = re.sub(r"[-_]txt\b", "", s, flags=re.I)
    s = re.sub(r"[^a-z0-9]+", "-", s.lower())
    return s.strip("-")


MANIFEST_KEY = "kb-manifest/manifest.json"
SKETCH_K = 256
SHINGLE_WORDS = 8


def content_sketch(text: str, k: int = SKETCH_K, shingle: int = SHINGLE_WORDS) -> list:
    """A bottom-k sketch of the document's word shingles.

    Name matching alone cannot catch the same lecture re-exported under a new
    filename ("Week 8 final.txt" vs "UX Studio Week 8 - using AI tools.txt"),
    which is the accidental re-upload worth rejecting. Comparing shingles of the
    words themselves is independent of both the filename and of where a given
    pipeline happened to cut its chunks.

    Bottom-k rather than storing every shingle: a 20k-word transcript has ~20k
    shingles, and keeping the 256 numerically smallest hashes estimates Jaccard
    similarity to within a few percent while keeping the manifest small enough
    to fetch on page load."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    if len(words) < shingle:
        return []
    hashes = {
        int(hashlib.md5(" ".join(words[i:i + shingle]).encode()).hexdigest()[:16], 16)
        for i in range(len(words) - shingle + 1)
    }
    return sorted(hashes)[:k]


def sketch_similarity(a: list, b: list) -> float:
    """Estimated Jaccard overlap of two bottom-k sketches (0.0 - 1.0)."""
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    k = min(len(a), len(b))
    union_bottom = sorted(sa | sb)[:k]
    if not union_bottom:
        return 0.0
    return len(set(union_bottom) & sa & sb) / len(union_bottom)


def load_manifest(bucket: str) -> dict:
    """{normalized_name: {"sketch": [...], "chunks": n}}. Empty if absent."""
    try:
        s3 = boto3.client("s3", region_name=AWS_REGION)
        body = s3.get_object(Bucket=bucket, Key=MANIFEST_KEY)["Body"].read()
        return json.loads(body.decode("utf-8"))
    except Exception:
        return {}


def save_manifest(bucket: str, manifest: dict) -> None:
    """Stored OUTSIDE kb-clean/v1/ so Bedrock never ingests the manifest itself."""
    s3 = boto3.client("s3", region_name=AWS_REGION)
    s3.put_object(
        Bucket=bucket,
        Key=MANIFEST_KEY,
        Body=json.dumps(manifest).encode("utf-8"),
        ContentType="application/json",
    )


SHORTLIST_THRESHOLD = 0.20
CONFIRM_THRESHOLD = 0.55
PROBE_COUNT = 12
PROBE_WORDS = 9


def rank_candidates(text: str, manifest: dict) -> list:
    """[(similarity, name)] sorted high to low."""
    sketch = content_sketch(text)
    scored = [
        (sketch_similarity(sketch, rec.get("sketch") or []), name)
        for name, rec in manifest.items()
    ]
    return sorted(scored, reverse=True)


def _document_text(bucket: str, prefix: str, normalized_name: str) -> str:
    """Concatenate every stored chunk belonging to one document."""
    s3 = boto3.client("s3", region_name=AWS_REGION)
    parts = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith(".txt"):
                continue
            if normalize_doc_name(key.split("/")[-1]) != normalized_name:
                continue
            try:
                parts.append(
                    s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8", "replace")
                )
            except Exception:
                pass
    return "\n".join(parts)


def confirm_duplicate(text: str, candidate: str, bucket: str, prefix: str) -> float:
    """Fraction of distinctive passages from `text` that appear verbatim in the
    stored document `candidate`. Exact matching, so unlike the sketch score it
    does not decay when two copies were transcribed or scrubbed differently."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    if len(words) < PROBE_WORDS * 4:
        return 0.0
    body = _document_text(bucket, prefix, candidate)
    if not body:
        return 0.0
    hay = " ".join(re.findall(r"[a-z0-9]+", body.lower()))
    step = max(1, (len(words) - PROBE_WORDS) // (PROBE_COUNT + 1))
    probes = [
        " ".join(words[i:i + PROBE_WORDS])
        for i in range(step, len(words) - PROBE_WORDS, step)
    ][:PROBE_COUNT]
    if not probes:
        return 0.0
    return sum(1 for p in probes if p in hay) / len(probes)


def find_content_duplicate(
    text: str, manifest: dict, bucket: str = S3_BUCKET, prefix: str = S3_PREFIX
) -> tuple:
    """Return (name, confidence) if `text` is already in the KB, else (None, best).

    Two stages, because one is not enough:

      1. The bottom-k sketch shortlists candidates cheaply. It cannot be the
         sole test -- five 2020 COMMLD-512 recordings scored only 45-52% against
         the very documents that already contain them verbatim, because each
         lecture had been transcribed and scrubbed twice with different results.
         A 0.55 cutoff would have admitted all five as new.
      2. Anything above a deliberately low shortlist bar is then confirmed by
         probing 12 distinctive 9-word passages against the stored document's
         actual text. Exact matching does not decay with processing differences,
         which is what makes it decisive.

    A sharp single peak in stage 1 -- high against one document, ~0 against every
    other -- is the signature of a re-upload, and stage 2 is what settles it."""
    ranked = rank_candidates(text, manifest)
    if not ranked:
        return None, 0.0
    best_sim = ranked[0][0]
    for sim, name in ranked[:3]:
        if sim < SHORTLIST_THRESHOLD:
            break
        overlap = confirm_duplicate(text, name, bucket, prefix)
        if overlap >= CONFIRM_THRESHOLD:
            return name, overlap
    return None, best_sim


def get_existing_doc_names(bucket: str, prefix: str) -> tuple:
    """Every document already in the KB, as normalized names.

    Returns (names, ok). `ok` is False when the S3 listing failed -- the caller
    must surface that rather than treat an empty set as "nothing is ingested
    yet", which would wave every upload through as new."""
    names = set()
    try:
        s3 = boto3.client("s3", region_name=AWS_REGION)
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"].split("/")[-1]
                if key.endswith(".metadata.json"):
                    continue
                n = normalize_doc_name(key)
                if n:
                    names.add(n)
    except Exception as e:
        return names, False
    return names, True


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
    refused = []

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

        # Publishability gate. Checked here, before any processing, so a
        # document that cannot be published fails immediately with a clear
        # reason rather than after chunking. kb_metadata.upload_chunk_with_sidecar
        # re-checks at upload as a backstop.
        gate_violations = blocking(
            get_policy().check_content(text, source=filepath.name)
        )
        if gate_violations:
            print(f"  ✋ REFUSED {filepath.name} — not publishable:")
            for v in gate_violations:
                print(f"       {v.rule}: {v.detail}")
            print("       Left in place; not ingested, not moved to done/.")
            refused.append(filepath)
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
        if refused:
            # Surface the reason rather than exiting on a bare "nothing happened".
            print(f"\n✋ REFUSED {len(refused)} file(s) — left in {input_dir}/:")
            for f in refused:
                print(f"     {f.name}")
            print("  These are not publishable to a public knowledge base.")
        return

    print(f"\nTotal: {len(all_chunks)} chunks in {output_dir}/\n")

    # Upload to S3
    print(f"Uploading to s3://{S3_BUCKET}/{S3_PREFIX} ...")
    uploaded = upload_chunks(output_dir, S3_BUCKET, S3_PREFIX, file_prefix)
    print(f"Uploaded {uploaded} chunks.\n")

    # Move originals to done/. Refused files stay put — moving them would make
    # a document that was never ingested look processed, and the next person to
    # look would find an empty input dir and assume it worked.
    done = inp / "done"
    done.mkdir(exist_ok=True)
    moved = 0
    for f in files:
        if f in refused:
            continue
        f.rename(done / f.name)
        moved += 1
    print(f"Moved {moved} original(s) to {done}/")

    if skipped_dupes:
        print(f"\n⏭ Skipped {len(skipped_dupes)} duplicate(s): {', '.join(skipped_dupes)}")
        print("  Use --force to re-ingest them.")

    if refused:
        print(f"\n✋ REFUSED {len(refused)} file(s) — left in {input_dir}/:")
        for f in refused:
            print(f"     {f.name}")
        print("  These are not publishable to a public knowledge base.")
        print("  Remove the offending content, or keep them out of the KB.")

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
