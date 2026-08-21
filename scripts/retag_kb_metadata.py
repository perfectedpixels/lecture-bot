"""
Re-tag every chunk in the KB with a `layer` and `doc_type`, replacing the
filename-prefix classification that scripts/backfill_kb_metadata.py used.

Why this exists
---------------
The original backfill matched on filename prefixes (`lecture-*`, `assignment-*`,
`grading-*`). Only 201 of 6,237 chunks actually use those prefixes, so ~97% of
the corpus went untagged and was invisible to layer-filtered retrieval.

The reliable signal is inside the file, not in its name. Every chunk starts with
a `Source:` line carrying its original path, and the hand-authored seed documents
additionally declare their own `content_type` in a metadata block. This script
reads that, in priority order:

    1. embedded `- content_type: X` from the document's own metadata block
    2. the `Source:` header path
    3. the filename (last resort)

Two deliberate decisions
------------------------
`layer=directive` means "governs grading" and nothing else -- rubrics and course
policy only. The operating-model seed docs declare `content_type: directive`, but
that is a different sense of the word (methodology guidance, not grading
criteria). Merging them would put methodology text into the channel that
grade_submission and feedback_mode rely on and dilute rubric retrieval, so those
documents are tagged `doc_type=framework` under `layer=reference` instead.

Sidecars are MERGED, not replaced. Existing attributes written by the producer
scripts (`assignment`, `course`, `concepts`) are preserved; only `layer` and
`doc_type` are set. Metadata is kept deliberately small -- this KB previously hit
an S3 Vectors metadata size limit, so this does not copy `keywords`/`domain`
across.

Usage
-----
    python3 scripts/retag_kb_metadata.py --dry-run     # classify, write nothing
    python3 scripts/retag_kb_metadata.py               # write + trigger sync
    python3 scripts/retag_kb_metadata.py --no-sync     # write, skip ingestion
"""

import argparse
import collections
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import boto3
from botocore.config import Config

BUCKET = "perfectpixels-kb-docs"
PREFIX = "kb-clean/v1/"
REGION = "us-east-1"
KNOWLEDGE_BASE_ID = "HHYCUJH32J"
DATA_SOURCE_ID = "B3BHIN3RF8"

# Enough to cover the Source: line plus a seed document's metadata block,
# without paying to download whole chunks.
HEAD_BYTES = 1500
WORKERS = 24

_CONTENT_TYPE_RE = re.compile(r"^\s*-\s*content_type:\s*(\S+)", re.MULTILINE)
_SOURCE_RE = re.compile(r"^Source:\s*(.+)$", re.MULTILINE)

# Bracketed headers written by the named producer pipelines.
_BRACKET_RE = re.compile(r"^\[(Rubric|Course Policy|Assignment|Lecture)\s*:", re.MULTILINE)

_BRACKET_MAP = {
    "Rubric": ("directive", "rubric"),
    "Course Policy": ("directive", "course-policy"),
    "Assignment": ("reference", "assignment"),
    "Lecture": ("reference", "lecture"),
}

# A document's self-declared content_type -> our doc_type. Note "directive"
# here is the operating-model sense and maps to framework, NOT layer=directive.
_CONTENT_TYPE_MAP = {
    "lecture": "lecture",
    "framework": "framework",
    "directive": "framework",
    "case-study": "case-study",
    "case_study": "case-study",
    "assignment": "assignment",
    "rubric": "rubric",
}


def classify(head: str, filename: str):
    """Return (layer, doc_type, signal) for one chunk."""
    bracket = _BRACKET_RE.search(head)
    if bracket:
        layer, doc_type = _BRACKET_MAP[bracket.group(1)]
        return layer, doc_type, "bracket-header"

    ct = _CONTENT_TYPE_RE.search(head)
    source = _SOURCE_RE.search(head)
    source_path = (source.group(1).strip() if source else "").lower()
    hay = f"{source_path} {filename.lower()}"

    # Repo documentation that got ingested alongside the course material --
    # the seed README describing the build pipeline. Not course content, and
    # not something a student question should ever surface.
    if re.search(r"(^|/)readme\.md|(^|[-_])readme[-_]md", hay):
        return "reference", "meta", "path"

    # Bio/professional material is checked before the generic lecture rule:
    # the CV and portfolio files live under lectures_processed/ but are not
    # lectures, and the previous retrieval guard only matched "portfolio",
    # silently leaving the CV chunks unweighted.
    if re.search(r"(^|[-_/])cv([-_.]|$)|jason[-_]levine[-_]cv", hay):
        return "reference", "cv", "path"
    if "portfolio" in hay:
        return "reference", "portfolio", "path"
    if "case-stud" in hay or "case_stud" in hay:
        return "reference", "case-study", "path"
    if "operating-model" in hay or "operating_model" in hay:
        return "reference", "framework", "path"

    if ct:
        mapped = _CONTENT_TYPE_MAP.get(ct.group(1).strip().lower())
        if mapped:
            layer = "directive" if mapped in ("rubric", "course-policy") else "reference"
            return layer, mapped, "content_type"

    if "lecture" in hay or "transcript" in hay:
        return "reference", "lecture", "path"

    # Unrecognised: still reachable through unfiltered retrieval, but not
    # asserted to be something it might not be.
    return "reference", "unclassified", "fallback"


def _sync():
    """Trigger a Bedrock ingestion job and poll it to completion."""
    print("\ntriggering Bedrock ingestion...")
    agent = boto3.client("bedrock-agent", region_name=REGION)
    job = agent.start_ingestion_job(knowledgeBaseId=KNOWLEDGE_BASE_ID, dataSourceId=DATA_SOURCE_ID)
    job_id = job["ingestionJob"]["ingestionJobId"]
    print(f"  job {job_id}")
    for _ in range(80):
        r = agent.get_ingestion_job(
            knowledgeBaseId=KNOWLEDGE_BASE_ID, dataSourceId=DATA_SOURCE_ID, ingestionJobId=job_id
        )["ingestionJob"]
        print(f"  status={r['status']}  {r.get('statistics', {})}")
        if r["status"] in ("COMPLETE", "FAILED"):
            if r["status"] == "FAILED":
                print("FAILED:", r.get("failureReasons"))
                sys.exit(1)
            break
        time.sleep(15)
    else:
        # Tagging every chunk touches ~30x more metadata than the original
        # backfill did, so this can outrun the poll window. Say so plainly
        # instead of printing success -- the job is still running, and
        # reporting "Done" here would be a lie the caller acts on.
        print(
            f"\nStill IN_PROGRESS after {80 * 15 // 60} minutes -- the job is fine, "
            "this poll loop just gave up first.\n"
            "Re-check with: aws bedrock-agent list-ingestion-jobs --region us-east-1 "
            f"--knowledge-base-id {KNOWLEDGE_BASE_ID} --data-source-id {DATA_SOURCE_ID} "
            "--max-results 1 --sort-by '{\"attribute\":\"STARTED_AT\",\"order\":\"DESCENDING\"}'"
        )
        return
    print("\nDone. Verify with a layer-filtered retrieve.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="classify and report; write nothing")
    ap.add_argument("--no-sync", action="store_true", help="write sidecars but skip KB ingestion")
    ap.add_argument("--sync-only", action="store_true", help="skip writing; just run the KB ingestion")
    args = ap.parse_args()

    if args.sync_only:
        _sync()
        return

    s3 = boto3.client("s3", region_name=REGION, config=Config(max_pool_connections=WORKERS + 8))

    txt_keys, sidecars = [], {}
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=PREFIX):
        for obj in page.get("Contents", []):
            k = obj["Key"]
            if k.endswith(".metadata.json"):
                sidecars[k] = True
            elif k.endswith(".txt"):
                txt_keys.append(k)
    print(f"{len(txt_keys)} chunks, {len(sidecars)} existing sidecars")

    def head_of(key):
        try:
            body = s3.get_object(Bucket=BUCKET, Key=key, Range=f"bytes=0-{HEAD_BYTES}")["Body"].read()
            return key, body.decode("utf-8", errors="replace")
        except Exception as e:
            print(f"⚠ could not read {key}: {e}")
            return key, ""

    print(f"reading headers with {WORKERS} workers...")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        heads = list(pool.map(head_of, txt_keys))
    print(f"  read {len(heads)} in {time.time()-t0:.0f}s")

    raw = []
    for key, head in heads:
        fname = key.rsplit("/", 1)[-1]
        layer, doc_type, signal = classify(head, fname)
        raw.append([key, fname, layer, doc_type, signal])

    # Twin resolution. Roughly half the corpus exists twice: once under a
    # hash-only name and once under a descriptive one. The two differ only in
    # the Source: header -- the hash-only copy records a bare filename with no
    # directory, so the path signal has nothing to match and it falls through
    # as unclassified. The pair is the same content, so inherit the sibling's
    # classification rather than guessing from the text.
    def twin_key(fname):
        m = re.search(r"([0-9a-f]{12})-(?:part-)?(\d{4})\.txt$", fname)
        return m.groups() if m else None

    resolved = {}
    for _, fname, layer, doc_type, _ in raw:
        tk = twin_key(fname)
        if tk and doc_type != "unclassified":
            resolved.setdefault(tk, (layer, doc_type))

    inherited = 0
    for row in raw:
        if row[3] == "unclassified":
            tk = twin_key(row[1])
            if tk and tk in resolved:
                row[2], row[3] = resolved[tk]
                row[4] = "twin"
                inherited += 1

    plan, dist, signals = [], collections.Counter(), collections.Counter()
    for key, _fname, layer, doc_type, signal in raw:
        dist[(layer, doc_type)] += 1
        signals[signal] += 1
        plan.append((key, layer, doc_type))
    if inherited:
        print(f"\nresolved {inherited} chunks from their duplicate twin")

    print("\nclassification:")
    for (layer, doc_type), n in dist.most_common():
        print(f"  {n:6d}  layer={layer:<9} doc_type={doc_type}")
    print("\nsignal used:")
    for s, n in signals.most_common():
        print(f"  {n:6d}  {s}")

    directive = sum(n for (l, _), n in dist.items() if l == "directive")
    print(f"\ngrading directive channel: {directive} chunks (rubrics + course policy only)")

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return

    print(f"\nwriting {len(plan)} sidecars (merging into existing)...")

    def write_one(item):
        key, layer, doc_type = item
        sk = f"{key}.metadata.json"
        attrs = {}
        if sk in sidecars:
            try:
                attrs = json.loads(
                    s3.get_object(Bucket=BUCKET, Key=sk)["Body"].read().decode("utf-8")
                ).get("metadataAttributes", {})
            except Exception:
                attrs = {}
        attrs["layer"] = layer
        attrs["doc_type"] = doc_type
        s3.put_object(
            Bucket=BUCKET,
            Key=sk,
            Body=json.dumps({"metadataAttributes": attrs}, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for i, _ in enumerate(pool.map(write_one, plan), start=1):
            if i % 1000 == 0:
                print(f"  {i}/{len(plan)}")
    print(f"  wrote {len(plan)} in {time.time()-t0:.0f}s")

    if args.no_sync:
        print("\n--no-sync: skipping ingestion. Run a KB sync before the tags take effect.")
        return

    _sync()


if __name__ == "__main__":
    main()
