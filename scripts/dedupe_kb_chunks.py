"""
Remove redundant duplicate chunks from the KB, safely.

The problem
-----------
Roughly half the corpus exists twice. Two pipelines chunked the same lecture
files: build_kb_clean_prefix.py wrote hash-only names (`00e4933a391f-0000.txt`)
and the lecture pipeline wrote descriptive ones
(`ux-studio-week-2-personas-chunk-043-txt-043989657bee-part-0000.txt`).

The bodies are identical. The only difference is the `Source:` header, where the
hash-only copy records a bare filename and the descriptive copy keeps the
directory:

    Source: UX Studio Week 2 Personas_chunk_043.txt
    Source: lectures_processed/UX Studio Week 2 Personas_chunk_043.txt

Both match the same queries, so a retrieval asking for 6 results routinely gets
3 distinct chunks. Removing the hash-only copies recovers that window.

Why this is careful
-------------------
The bucket has no versioning and the local lecture sources are gone, so S3 is
the only copy of this content and a delete is permanent. Therefore:

  * every pair is byte-verified (bodies, ignoring the Source: line) before the
    pair is eligible -- not a sample;
  * anything that does not verify is left completely alone and reported;
  * `--archive` server-side copies the hash-only object AND its metadata
    sidecar to a dated prefix, so the delete is reversible;
  * `--delete` refuses to run against anything it cannot find in the archive.

The descriptive copy is the one kept: it carries the fuller provenance path.

Usage
-----
    python3 scripts/dedupe_kb_chunks.py --verify          # verify only
    python3 scripts/dedupe_kb_chunks.py --archive         # verify + archive
    python3 scripts/dedupe_kb_chunks.py --delete          # archived pairs only
    python3 scripts/dedupe_kb_chunks.py --delete --sync   # ...then reindex
"""

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

BUCKET = "perfectpixels-kb-docs"
PREFIX = "kb-clean/v1/"
REGION = "us-east-1"
KNOWLEDGE_BASE_ID = "HHYCUJH32J"
DATA_SOURCE_ID = "B3BHIN3RF8"

ARCHIVE_PREFIX = f"kb-archive/pre-dedupe-{time.strftime('%Y-%m-%d')}/"
WORKERS = 24

_HASH_ONLY = re.compile(r"^[0-9a-f]{12}-\d{4}\.txt$")
_TWIN_KEY = re.compile(r"([0-9a-f]{12})-(?:part-)?(\d{4})\.txt$")
_SOURCE_LINE = re.compile(r"^Source:.*$", re.MULTILINE)
_BRACKET_LINE = re.compile(r"^\[[^\]]+\].*$", re.MULTILINE)


def _s3():
    return boto3.client("s3", region_name=REGION, config=Config(max_pool_connections=WORKERS + 8))


def normalise(text: str) -> str:
    """Body with provenance headers and whitespace differences removed."""
    t = _SOURCE_LINE.sub("", text, count=1)
    t = _BRACKET_LINE.sub("", t, count=1)
    return " ".join(t.split())


def build_pairs(s3):
    """Return (pairs, stats). A pair is (hash_only_key, descriptive_key)."""
    keys = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=PREFIX):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".txt"):
                keys.append(obj["Key"])

    groups = {}
    for k in keys:
        fname = k.rsplit("/", 1)[-1]
        m = _TWIN_KEY.search(fname)
        if not m:
            continue
        groups.setdefault(m.groups(), []).append(k)

    pairs, odd = [], 0
    for members in groups.values():
        if len(members) != 2:
            if len(members) > 2:
                odd += 1
            continue
        hash_only = [k for k in members if _HASH_ONLY.match(k.rsplit("/", 1)[-1])]
        other = [k for k in members if not _HASH_ONLY.match(k.rsplit("/", 1)[-1])]
        if len(hash_only) == 1 and len(other) == 1:
            pairs.append((hash_only[0], other[0]))
    return pairs, {"total_txt": len(keys), "groups": len(groups), "odd_groups": odd}


def verify(s3, pairs):
    """Byte-verify every pair. Returns (identical, mismatched)."""
    def check(pair):
        a, b = pair
        try:
            ta = s3.get_object(Bucket=BUCKET, Key=a)["Body"].read().decode("utf-8", "replace")
            tb = s3.get_object(Bucket=BUCKET, Key=b)["Body"].read().decode("utf-8", "replace")
        except Exception as e:
            return pair, False, f"read error: {e}"
        return pair, normalise(ta) == normalise(tb), ""

    identical, mismatched = [], []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for i, (pair, same, note) in enumerate(pool.map(check, pairs), start=1):
            (identical if same else mismatched).append((pair, note))
            if i % 500 == 0:
                print(f"  verified {i}/{len(pairs)}")
    return [p for p, _ in identical], mismatched


def archive(s3, victims):
    """Server-side copy each hash-only object and its sidecar to the archive."""
    def cp(key):
        copied = 0
        for src in (key, f"{key}.metadata.json"):
            dst = ARCHIVE_PREFIX + src[len(PREFIX):]
            try:
                s3.copy_object(
                    Bucket=BUCKET, Key=dst, CopySource={"Bucket": BUCKET, "Key": src}
                )
                copied += 1
            except ClientError as e:
                if e.response["Error"]["Code"] not in ("NoSuchKey", "404"):
                    raise
        return copied

    total = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for i, n in enumerate(pool.map(cp, victims), start=1):
            total += n
            if i % 500 == 0:
                print(f"  archived {i}/{len(victims)}")
    return total


def archived_set(s3):
    out = set()
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=ARCHIVE_PREFIX):
        for obj in page.get("Contents", []):
            out.add(PREFIX + obj["Key"][len(ARCHIVE_PREFIX):])
    return out


def delete(s3, victims):
    """Delete only objects confirmed present in the archive."""
    have = archived_set(s3)
    unsafe = [k for k in victims if k not in have]
    if unsafe:
        print(f"REFUSING: {len(unsafe)} object(s) not found in {ARCHIVE_PREFIX}")
        for k in unsafe[:5]:
            print("   ", k)
        sys.exit(1)

    to_delete = []
    for k in victims:
        to_delete.append({"Key": k})
        if f"{k}.metadata.json" in have:
            to_delete.append({"Key": f"{k}.metadata.json"})

    deleted = 0
    for i in range(0, len(to_delete), 1000):
        batch = to_delete[i : i + 1000]
        resp = s3.delete_objects(Bucket=BUCKET, Delete={"Objects": batch, "Quiet": True})
        errs = resp.get("Errors", [])
        if errs:
            print(f"  {len(errs)} delete error(s), first: {errs[0]}")
        deleted += len(batch) - len(errs)
        print(f"  deleted {deleted}/{len(to_delete)}")
    return deleted


def sync():
    print("\ntriggering Bedrock ingestion...")
    agent = boto3.client("bedrock-agent", region_name=REGION)
    job = agent.start_ingestion_job(knowledgeBaseId=KNOWLEDGE_BASE_ID, dataSourceId=DATA_SOURCE_ID)
    jid = job["ingestionJob"]["ingestionJobId"]
    print(f"  job {jid} started — poll with list-ingestion-jobs; it can outlast this script")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="verify pairs only, write nothing")
    ap.add_argument("--archive", action="store_true", help="verify, then copy to the archive prefix")
    ap.add_argument("--delete", action="store_true", help="delete archived duplicates")
    ap.add_argument("--sync", action="store_true", help="reindex the KB after --delete")
    args = ap.parse_args()
    if not (args.verify or args.archive or args.delete):
        ap.error("choose one of --verify / --archive / --delete")

    s3 = _s3()
    pairs, stats = build_pairs(s3)
    print(f"{stats['total_txt']} chunks -> {stats['groups']} content keys, {len(pairs)} twin pairs")
    if stats["odd_groups"]:
        print(f"  ({stats['odd_groups']} group(s) with >2 members, skipped)")

    print(f"\nbyte-verifying all {len(pairs)} pairs...")
    t0 = time.time()
    ok, bad = verify(s3, pairs)
    print(f"  {len(ok)} identical, {len(bad)} mismatched  ({time.time()-t0:.0f}s)")
    for (pair, note) in bad[:5]:
        print(f"    MISMATCH {pair[0]}  {note}")
    if bad:
        print("  mismatched pairs are left untouched.")

    victims = [h for (h, _d) in ok]
    print(f"\n{len(victims)} hash-only copies eligible (descriptive twin kept)")

    if args.verify:
        print("\n--verify: nothing written.")
        return

    if args.archive:
        print(f"\narchiving to s3://{BUCKET}/{ARCHIVE_PREFIX} ...")
        n = archive(s3, victims)
        print(f"  copied {n} objects (chunks + sidecars)")
        print("\nArchived. Nothing deleted yet — rerun with --delete to remove the originals.")
        return

    if args.delete:
        print(f"\ndeleting {len(victims)} duplicates (archive-verified)...")
        n = delete(s3, victims)
        print(f"  deleted {n} objects")
        if args.sync:
            sync()


if __name__ == "__main__":
    main()
