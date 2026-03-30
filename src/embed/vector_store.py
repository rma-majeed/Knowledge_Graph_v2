"""ChromaDB vector store wrapper.

Wraps ChromaDB PersistentClient for chunk embedding storage and retrieval.
Provides upsert() for idempotent embedding storage and query() for top-N
semantic search with metadata co-location.
"""
from __future__ import annotations

import chromadb


class VectorStore:
    """Wraps ChromaDB PersistentClient for chunk embedding storage and retrieval.

    Args:
        chroma_path: Path to the ChromaDB persistence directory.
    """

    def __init__(self, chroma_path: str = "data/chroma_db") -> None:
        self._client = chromadb.PersistentClient(path=chroma_path)
        try:
            self._collection = self._client.get_or_create_collection(
                name="chunks",
                configuration={"hnsw": {"space": "cosine"}},
            )
        except Exception:
            # Collection exists with configuration already persisted
            self._collection = self._client.get_collection(name="chunks")

    def upsert(
        self,
        chunk_ids: list[int],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        """Upsert embeddings with metadata into the ChromaDB collection."""
        ids = [str(cid) for cid in chunk_ids]
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def query(
        self,
        query_embedding: list[float],
        n_results: int = 10,
    ) -> list[dict]:
        """Query for the top-N most similar chunks.

        Returns list of dicts with keys: chunk_id, text, metadata, distance.
        Applies min(n_results, count) guard to prevent NotEnoughElementsException.
        """
        actual_n = min(n_results, self._collection.count())
        if actual_n == 0:
            return []
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=actual_n,
            include=["documents", "metadatas", "distances"],
        )
        return [
            {
                "chunk_id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            }
            for i in range(len(results["ids"][0]))
        ]

    def count(self) -> int:
        """Return total number of embeddings stored."""
        return self._collection.count()
