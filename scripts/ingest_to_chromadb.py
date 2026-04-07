#!/usr/bin/env python3
"""
One-time script to ingest lecture segments into the local ChromaDB vector store.
Replaces the S3 upload + Bedrock Knowledge Base sync workflow.

Usage:
    python scripts/ingest_to_chromadb.py [data_dir]
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vector_store import VectorStore


def ingest_directory(data_dir: str):
    """Ingest all .txt files from a directory into ChromaDB."""
    data_path = Path(data_dir)
    if not data_path.exists():
        print(f"Error: {data_dir} does not exist")
        sys.exit(1)

    txt_files = sorted(data_path.glob("*.txt"))
    if not txt_files:
        print(f"No .txt files found in {data_dir}")
        sys.exit(1)

    print(f"Found {len(txt_files)} files in {data_dir}")

    documents = []
    metadatas = []
    ids = []

    for txt_file in txt_files:
        content = txt_file.read_text(encoding="utf-8").strip()
        if not content:
            continue

        documents.append(content)
        metadatas.append({
            "source": str(txt_file.name),
            "path": str(txt_file),
        })
        ids.append(txt_file.stem)

    print(f"Ingesting {len(documents)} documents...")
    store = VectorStore()
    store.ingest(documents, metadatas, ids)
    print(f"Done. Total documents in store: {store.count()}")


def main():
    project_root = Path(__file__).parent.parent

    # Default: ingest both 512 and 515 canvas extracts if they exist
    dirs_to_ingest = []
    for dirname in ["canvas_extracted_512", "canvas_extracted"]:
        candidate = project_root / "data" / dirname
        if candidate.exists():
            dirs_to_ingest.append(str(candidate))

    if sys.argv[1:]:
        dirs_to_ingest = sys.argv[1:]

    if not dirs_to_ingest:
        print("No data directories found. Pass a directory path as argument.")
        sys.exit(1)

    for data_dir in dirs_to_ingest:
        ingest_directory(data_dir)


if __name__ == "__main__":
    main()
