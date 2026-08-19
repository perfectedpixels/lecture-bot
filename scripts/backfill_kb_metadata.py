"""
Backfill `layer` metadata sidecars onto chunks already sitting in
s3://perfectpixels-kb-docs/kb-clean/v1/, without re-chunking or re-uploading
the text content itself.

Classifies purely by filename prefix (already a reliable signal — confirmed
by reading all 4 producer scripts):
  grading-course-policy-*  -> layer=directive, doc_type=course-policy
  grading-rubric-{name}-*  -> layer=directive, doc_type=rubric, assignment={name}
  lecture-*                -> layer=reference, doc_type=lecture
  assignment-{course}-*    -> layer=reference, doc_type=assignment, course={course}
  anything else (hash-only generic-rechunker output, _manifest.json, existing
  .metadata.json sidecars themselves) -> skipped, left untagged (safe default)

Usage:
    python3 scripts/backfill_kb_metadata.py --dry-run
    python3 scripts/backfill_kb_metadata.py
    python3 scripts/backfill_kb_metadata.py --force   # re-tag even if a sidecar already exists

After a real (non-dry-run) pass, triggers a Bedrock KB ingestion job and polls
it to completion so the new metadata is actually indexed.
"""

import argparse
import json
import re
import sys
import time

import boto3

BUCKET = "perfectpixels-kb-docs"
PREFIX = "kb-clean/v1/"
KNOWLEDGE_BASE_ID = "HHYCUJH32J"
DATA_SOURCE_ID = "B3BHIN3RF8"

_RUBRIC_RE = re.compile(r"^grading-rubric-(?P<name>.+?)-part-\d+-[0-9a-f]+\.txt$")
_ASSIGNMENT_RE = re.compile(r"^assignment-(?P<course>[^-]+)-.+-part-\d+-[0-9a-f]+\.txt$")


def classify(filename: str):
    """Return (layer, extra_attrs) or None to skip."""
    if filename.startswith("grading-course-policy-"):
        return "directive", {"doc_type": "course-policy"}
    m = _RUBRIC_RE.match(filename)
    if m:
        return "directive", {"doc_type": "rubric", "assignment": m.group("name")}
    if filename.startswith("lecture-"):
        return "reference", {"doc_type": "lecture"}
    m = _ASSIGNMENT_RE.match(filename)
    if m:
        return "reference", {"doc_type": "assignment", "course": m.group("course")}
    return None


def list_txt_and_sidecar_keys(s3):
    """Return (txt_keys, existing_sidecar_keys) under PREFIX."""
    paginator = s3.get_paginator("list_objects_v2")
    txt_keys = []
    sidecar_keys = set()
    for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith(".metadata.json"):
                sidecar_keys.add(key)
            elif key.endswith(".txt"):
                txt_keys.append(key)
    return txt_keys, sidecar_keys


def run(dry_run: bool, force: bool):
    s3 = boto3.client("s3")
    txt_keys, existing_sidecars = list_txt_and_sidecar_keys(s3)
    print(f"Found {len(txt_keys)} chunk .txt objects under s3://{BUCKET}/{PREFIX}")

    counts = {"directive": 0, "reference": 0, "skipped": 0, "already_tagged": 0}
    to_write = []  # (key, layer, extra_attrs)

    for key in txt_keys:
        filename = key.rsplit("/", 1)[-1]
        sidecar_key = f"{key}.metadata.json"
        if not force and sidecar_key in existing_sidecars:
            counts["already_tagged"] += 1
            continue
        result = classify(filename)
        if result is None:
            counts["skipped"] += 1
            continue
        layer, extra = result
        counts[layer] += 1
        to_write.append((key, layer, extra))

    print(
        f"directive={counts['directive']}  reference={counts['reference']}  "
        f"skipped(untagged)={counts['skipped']}  already_tagged={counts['already_tagged']}"
    )

    if dry_run:
        print("\n--dry-run: no writes performed. Re-run without --dry-run to apply.")
        return

    if not to_write:
        print("\nNothing to write.")
        return

    print(f"\nWriting {len(to_write)} sidecar objects...")
    for i, (key, layer, extra) in enumerate(to_write, start=1):
        body = json.dumps({"metadataAttributes": {"layer": layer, **extra}}, ensure_ascii=False)
        s3.put_object(
            Bucket=BUCKET,
            Key=f"{key}.metadata.json",
            Body=body.encode("utf-8"),
            ContentType="application/json",
        )
        if i % 100 == 0 or i == len(to_write):
            print(f"  {i}/{len(to_write)}")

    print("\nTriggering Bedrock KB ingestion job to pick up the new metadata...")
    bedrock_agent = boto3.client("bedrock-agent")
    job = bedrock_agent.start_ingestion_job(
        knowledgeBaseId=KNOWLEDGE_BASE_ID, dataSourceId=DATA_SOURCE_ID
    )
    job_id = job["ingestionJob"]["ingestionJobId"]
    print(f"Ingestion job started: {job_id}")

    for _ in range(60):
        resp = bedrock_agent.get_ingestion_job(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            dataSourceId=DATA_SOURCE_ID,
            ingestionJobId=job_id,
        )
        status = resp["ingestionJob"]["status"]
        stats = resp["ingestionJob"].get("statistics", {})
        print(f"  status={status}  {stats}")
        if status in ("COMPLETE", "FAILED"):
            if status == "FAILED":
                print("Ingestion FAILED:", resp["ingestionJob"].get("failureReasons"))
                sys.exit(1)
            break
        time.sleep(15)
    else:
        print("Timed out waiting for ingestion job to complete — check the console.")
        sys.exit(1)

    print("\nDone. Verify with a filtered retrieve() call (layer=directive).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print counts only, write nothing")
    parser.add_argument("--force", action="store_true", help="Re-tag objects that already have a sidecar")
    args = parser.parse_args()
    run(dry_run=args.dry_run, force=args.force)
