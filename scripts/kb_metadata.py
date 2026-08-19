"""
Shared helper for tagging KB chunks with Bedrock-recognized metadata sidecars.

Bedrock attaches `{"metadataAttributes": {...}}` from a `<key>.txt.metadata.json`
sidecar object to every chunk it derives from the paired `<key>.txt` source
object, regardless of chunking strategy. Writing `layer: "directive"` on
grading-handbook chunks (vs. `layer: "reference"` on lecture/assignment
chunks) lets retrieval do a metadata-filtered "directive channel" query
alongside normal semantic search, so grading criteria reliably surface
instead of competing on equal footing with general lecture content.

Used by process_grading.py, process_lectures.py, ingest_transcripts.py,
process_assignments.py, canvas_sync.py, and backfill_kb_metadata.py.
"""

import json
from pathlib import Path


def write_sidecar(chunk_path: Path, layer: str, **extra_attrs) -> Path:
    """Write a `<chunk_path>.metadata.json` sidecar next to a local chunk file."""
    attrs = {"layer": layer, **extra_attrs}
    sidecar_path = chunk_path.with_name(chunk_path.name + ".metadata.json")
    sidecar_path.write_text(
        json.dumps({"metadataAttributes": attrs}, ensure_ascii=False),
        encoding="utf-8",
    )
    return sidecar_path


def upload_chunk_with_sidecar(s3, local_txt_path: Path, bucket: str, key: str) -> None:
    """Upload a chunk .txt file, then its .metadata.json sidecar if one exists
    alongside it (same directory, `<name>.txt.metadata.json`)."""
    s3.upload_file(str(local_txt_path), bucket, key)
    sidecar_path = local_txt_path.with_name(local_txt_path.name + ".metadata.json")
    if sidecar_path.exists():
        s3.upload_file(str(sidecar_path), bucket, f"{key}.metadata.json")
