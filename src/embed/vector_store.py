"""ChromaDB vector store wrapper.

Stub — implementation in Phase 2 Plan 03.
"""
from __future__ import annotations

from typing import Any


class VectorStore:
    """Wraps ChromaDB PersistentClient for chunk embedding storage and retrieval.

    Args:
        chroma_path: Path to the ChromaDB persistence directory.

    Raises:
        NotImplementedError: Until Plan 03 implements this class.
    """

    def __init__(self, chroma_path: str = "data/chroma_db") -> None:
        raise NotImplementedError("VectorStore not yet implemented — see Plan 03")

    def upsert(
        self,
        chunk_ids: list[int],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        """Upsert embeddings with metadata into the ChromaDB collection."""
        raise NotImplementedError

    def query(
        self,
        query_embedding: list[float],
        n_results: int = 10,
    ) -> list[dict]:
        """Query for the top-N most similar chunks.

        Returns list of dicts with keys: chunk_id, text, metadata, distance.
        """
        raise NotImplementedError

    def count(self) -> int:
        """Return total number of embeddings stored."""
        raise NotImplementedError
