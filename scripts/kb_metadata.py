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
import os
from pathlib import Path

from kbpolicy import Policy, blocking


class PolicyRefusal(RuntimeError):
    """Raised when a chunk fails the publishability gate.

    The knowledge base answers questions for anonymous visitors on a public
    site, so anything uploaded here can be quoted verbatim to the world. This
    is the last checkpoint before that happens.
    """


# Loaded once. Set KB_POLICY_DISABLED=1 only for local experiments against a
# throwaway bucket — never when writing to the shared KB.
_POLICY = None


def get_policy() -> Policy:
    """Shared, lazily-loaded policy instance."""
    global _POLICY
    if _POLICY is None:
        _POLICY = Policy.load(Path(__file__).with_name("policy.yaml"))
    return _POLICY


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
    alongside it (same directory, `<name>.txt.metadata.json`).

    Every chunk passes the publishability gate first. This is deliberately at
    the shared upload point rather than in one caller, so all ingestion paths
    (transcripts, lectures, assignments, grading, canvas sync) are covered by
    construction — a new script cannot bypass it by forgetting to check.
    """
    if os.environ.get("KB_POLICY_DISABLED") != "1":
        text = local_txt_path.read_text(encoding="utf-8", errors="replace")
        violations = blocking(get_policy().check_content(text, source=str(local_txt_path)))
        if violations:
            detail = "\n".join("  " + str(v) for v in violations)
            raise PolicyRefusal(
                f"refusing to upload {local_txt_path.name} — "
                f"content is not publishable:\n{detail}\n"
                "This chunk would be retrievable by anyone using the public "
                "chatbot. Remove the offending content or exclude the document."
            )

    s3.upload_file(str(local_txt_path), bucket, key)
    sidecar_path = local_txt_path.with_name(local_txt_path.name + ".metadata.json")
    if sidecar_path.exists():
        s3.upload_file(str(sidecar_path), bucket, f"{key}.metadata.json")
