"""
Local vector store using ChromaDB.
Replaces Bedrock Knowledge Base + OpenSearch Serverless.
"""

import chromadb
from pathlib import Path
from typing import List, Dict, Optional


DEFAULT_PERSIST_DIR = str(Path(__file__).parent.parent / "data" / "chromadb")
COLLECTION_NAME = "lecture_segments"


class VectorStore:
    def __init__(self, persist_dir: str = DEFAULT_PERSIST_DIR):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def ingest(
        self,
        documents: List[str],
        metadatas: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None,
    ):
        """Add documents to the vector store."""
        if ids is None:
            ids = [f"doc_{i}" for i in range(len(documents))]
        self.collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )

    def query(self, text: str, n_results: int = 5) -> List[Dict]:
        """
        Query the vector store. Returns list of:
        {"text": str, "source": str, "metadata": dict, "score": float}
        """
        results = self.collection.query(
            query_texts=[text],
            n_results=min(n_results, self.collection.count() or 1),
        )

        items = []
        for i in range(len(results["documents"][0])):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0.0
            items.append({
                "text": results["documents"][0][i],
                "source": meta.get("source", "unknown"),
                "metadata": meta,
                "score": 1.0 - distance,  # convert distance to similarity
            })
        return items

    def count(self) -> int:
        return self.collection.count()
