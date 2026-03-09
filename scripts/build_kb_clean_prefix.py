#!/usr/bin/env python3
"""
Build a clean, deterministic KB prefix in S3.

This script mirrors source text/markdown docs from an S3 bucket into a target
prefix as normalized chunks, while preserving source provenance in each chunk.
It does not modify or delete original source objects.

Ported from ppmg for use with lecture-bot when using the same S3 bucket
(perfectpixels-kb-docs) and chunking format as the portfolio chatbot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List

import boto3
from botocore.config import Config


TEXT_EXTENSIONS = (".txt", ".md", ".markdown")


@dataclass
class SourceObject:
    key: str
    size: int


def list_source_objects(
    s3, bucket: str, exclude_prefixes: List[str]
) -> Iterable[SourceObject]:
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if any(key.startswith(prefix) for prefix in exclude_prefixes):
                continue
            if not key.lower().endswith(TEXT_EXTENSIONS):
                continue
            if obj.get("Size", 0) <= 0:
                continue
            yield SourceObject(key=key, size=obj["Size"])


def normalize_text(raw: bytes) -> str:
    return raw.decode("utf-8", errors="ignore").replace("\r\n", "\n").replace(
        "\r", "\n"
    )


def chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and < chunk_size")

    text = text.strip()
    if not text:
        return []

    step = chunk_size - overlap
    chunks: List[str] = []
    for start in range(0, len(text), step):
        chunk = text[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        if start + chunk_size >= len(text):
            break
    return chunks


def target_key(prefix: str, source_key: str, part_idx: int) -> str:
    basename = source_key.split("/")[-1]
    src_hash = hashlib.sha1(source_key.encode("utf-8")).hexdigest()[:12]
    safe_name = "".join(
        ch if ch.isalnum() else "-" for ch in basename.lower()
    ).strip("-")
    return f"{prefix.rstrip('/')}/{safe_name}-{src_hash}-part-{part_idx:04}.txt"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="personal")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--bucket", default="perfectpixels-kb-docs")
    parser.add_argument("--target-prefix", default="kb-clean/v1")
    parser.add_argument(
        "--exclude-prefix",
        action="append",
        default=["kb-clean/", "rechunked/"],
        help="Exclude source keys that start with this prefix (repeatable).",
    )
    parser.add_argument("--chunk-size", type=int, default=1200)
    parser.add_argument("--overlap", type=int, default=200)
    args = parser.parse_args()

    session = boto3.Session(
        profile_name=args.profile, region_name=args.region
    )
    s3 = session.client(
        "s3", config=Config(retries={"max_attempts": 10, "mode": "standard"})
    )

    sources = list(list_source_objects(s3, args.bucket, args.exclude_prefix))
    print(f"source_objects={len(sources)}")

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bucket": args.bucket,
        "target_prefix": args.target_prefix,
        "chunk_size": args.chunk_size,
        "overlap": args.overlap,
        "sources": [],
    }

    uploaded = 0
    for source in sources:
        obj = s3.get_object(Bucket=args.bucket, Key=source.key)
        text = normalize_text(obj["Body"].read())
        chunks = chunk_text(text, args.chunk_size, args.overlap)
        if not chunks:
            continue

        source_out = {"key": source.key, "size": source.size, "chunks": []}
        for idx, chunk in enumerate(chunks):
            key = target_key(args.target_prefix, source.key, idx)
            body = f"Source: {source.key}\n\n{chunk}\n".encode("utf-8")
            s3.put_object(
                Bucket=args.bucket,
                Key=key,
                Body=body,
                ContentType="text/plain; charset=utf-8",
            )
            uploaded += 1
            source_out["chunks"].append(key)
        manifest["sources"].append(source_out)

    manifest_key = f"{args.target_prefix.rstrip('/')}/_manifest.json"
    s3.put_object(
        Bucket=args.bucket,
        Key=manifest_key,
        Body=json.dumps(manifest, indent=2).encode("utf-8"),
        ContentType="application/json",
    )
    print(f"uploaded_chunks={uploaded}")
    print(f"manifest={manifest_key}")


if __name__ == "__main__":
    main()
