"""
Build the content-fingerprint manifest the upload tool uses to reject duplicates.

Why this exists
---------------
Rejecting a duplicate by filename only catches the easy case. The one worth
catching is the same lecture re-exported under a new name -- "Week 8 final.txt"
against an existing "UX Studio Week 8 - using AI tools.txt" -- which no name
comparison can see. This manifest stores a small fingerprint of each document's
actual words, so the upload tool can recognise the content regardless of what
the file is called or where a pipeline happened to cut its chunks.

For each document already in the KB it records:

    {normalized_name: {"sketch": [256 ints], "chunks": n, "words": n}}

`sketch` is a bottom-k sketch of 8-word shingles (see ingest_transcripts.
content_sketch). Comparing two sketches estimates Jaccard overlap, so a
threshold of ~0.55 flags a re-upload while leaving two genuinely different
lectures on the same topic alone.

The manifest is written to s3://<bucket>/kb-manifest/manifest.json --
deliberately OUTSIDE kb-clean/v1/, so Bedrock never ingests the manifest as if
it were course content.

Usage
-----
    python3 scripts/build_kb_manifest.py              # build and upload
    python3 scripts/build_kb_manifest.py --dry-run    # report only
    python3 scripts/build_kb_manifest.py --check FILE # test one file against it
"""

import argparse
import collections
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import boto3
from botocore.config import Config

sys.path.insert(0, str(Path(__file__).parent))

from ingest_transcripts import (  # noqa: E402
    AWS_REGION,
    S3_BUCKET,
    S3_PREFIX,
    content_sketch,
    find_content_duplicate,
    load_manifest,
    normalize_doc_name,
    save_manifest,
    scrub_transcript,
)

WORKERS = 32


def build(bucket: str, prefix: str) -> dict:
    s3 = boto3.client(
        "s3", region_name=AWS_REGION, config=Config(max_pool_connections=WORKERS + 8)
    )
    keys = [
        o["Key"]
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix)
        for o in page.get("Contents", [])
        if o["Key"].endswith(".txt")
    ]
    print(f"reading {len(keys)} chunks from s3://{bucket}/{prefix} ...")

    def get(k):
        try:
            return k, s3.get_object(Bucket=bucket, Key=k)["Body"].read().decode("utf-8", "replace")
        except Exception:
            return k, ""

    docs = collections.defaultdict(list)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for i, (key, body) in enumerate(pool.map(get, keys), start=1):
            if body:
                docs[normalize_doc_name(key.split("/")[-1])].append(body)
            if i % 1000 == 0:
                print(f"  {i}/{len(keys)}")
    print(f"  read in {time.time() - t0:.0f}s -> {len(docs)} distinct documents")

    manifest = {}
    for name, bodies in docs.items():
        text = "\n".join(bodies)
        # Fingerprint the SCRUBBED text on both sides of the comparison. Stored
        # chunks still carry WEBVTT debris and "Jason Levine:" labels, whereas an
        # upload is scrubbed before it is fingerprinted -- so sketching the raw
        # stored text compared clean words against dirty ones and the overlap
        # collapsed. Observed: re-uploading the Week 6 transcript, which is
        # already in the KB, scored 29% and would have been waved through as new.
        manifest[name] = {
            "sketch": content_sketch(scrub_transcript(text)),
            "chunks": len(bodies),
            "words": len(text.split()),
        }
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="build and report; upload nothing")
    ap.add_argument("--check", metavar="FILE", help="test one local file against the stored manifest")
    args = ap.parse_args()

    if args.check:
        manifest = load_manifest(S3_BUCKET)
        if not manifest:
            print("No manifest stored yet — run without --check first.")
            sys.exit(1)
        raw = Path(args.check).read_text(encoding="utf-8", errors="replace")
        dupe, sim = find_content_duplicate(scrub_transcript(raw), manifest)
        print(f"manifest holds {len(manifest)} documents")
        if dupe:
            print(f"DUPLICATE of '{dupe}' — {sim:.0%} content overlap")
        else:
            print(f"no duplicate (closest match {sim:.0%})")
        return

    manifest = build(S3_BUCKET, S3_PREFIX)
    big = sorted(manifest.items(), key=lambda kv: -kv[1]["chunks"])[:10]
    print("\nlargest documents:")
    for name, rec in big:
        print(f"  {rec['chunks']:>4} chunks  {rec['words']:>7,} words  {name}")

    if args.dry_run:
        print("\n--dry-run: manifest not uploaded.")
        return

    save_manifest(S3_BUCKET, manifest)
    print(f"\nWrote manifest for {len(manifest)} documents to s3://{S3_BUCKET}/kb-manifest/manifest.json")


if __name__ == "__main__":
    main()
