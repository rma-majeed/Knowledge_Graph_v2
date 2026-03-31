"""BM25 keyword index for hybrid retrieval (RAG-01).

Uses rank_bm25.BM25Okapi. Index is in-memory; rebuilt from SQLite chunks
at pipeline startup or on first query. No persistence to disk in v1.

Usage:
    from src.query.bm25_index import BM25Indexer
    indexer = BM25Indexer()
    indexer.build(chunks)           # chunks: list of chunk dicts
    results = indexer.query("warranty", n_results=10)
"""
from __future__ import annotations


class BM25Indexer:
    """Wraps rank_bm25.BM25Okapi for keyword-based chunk retrieval.

    Build from a list of chunk dicts (same shape as retriever.vector_search output).
    Tokenization is simple whitespace split + lowercase — no stemming or stopword removal.
    This matches the consulting document vocabulary where domain terms should be preserved.
    """

    def __init__(self) -> None:
        self._bm25 = None
        self._chunks: list[dict] = []
        self._built = False

    def build(self, chunks: list[dict]) -> None:
        """Build BM25 index from chunk list.

        If chunks is empty, index is marked as empty and query() returns [].
        Called at query pipeline startup or after each ingest batch.

        Args:
            chunks: List of chunk dicts with at minimum a "text" key and "chunk_id".
        """
        self._built = True
        self._chunks = chunks
        if not chunks:
            self._bm25 = None
            return

        from rank_bm25 import BM25Okapi
        corpus = [c.get("text", "").lower().split() for c in chunks]
        self._bm25 = BM25Okapi(corpus)

    def query(self, query_text: str, n_results: int = 10) -> list[dict]:
        """Return top-N chunks ranked by BM25 score for query_text.

        Returns chunk dicts with source="bm25" and distance=1.0/(bm25_score+1e-9)
        so that the RRF fusion can treat distance consistently with vector results
        (lower distance = more relevant). Only chunks with score > 0 are returned.

        Args:
            query_text: Natural language query string.
            n_results: Maximum number of results to return.

        Returns:
            List of chunk dicts with keys: chunk_id, text, filename, page_num,
            source="bm25", distance=float. Returns [] if index is empty.

        Raises:
            RuntimeError: If query() is called before build().
        """
        if not self._built:
            raise RuntimeError("BM25 index not built. Call build() first.")

        if self._bm25 is None:
            # Empty corpus — return empty results gracefully
            return []

        tokens = query_text.lower().split()
        scores = self._bm25.get_scores(tokens)

        # Pair chunks with their BM25 scores and filter zero-score chunks
        ranked = sorted(
            [(score, chunk) for score, chunk in zip(scores, self._chunks) if score > 0],
            key=lambda x: x[0],
            reverse=True,
        )[:n_results]

        results = []
        for score, chunk in ranked:
            results.append({
                **chunk,
                "source": "bm25",
                "distance": 1.0 / (score + 1e-9),  # lower = better, for RRF rank ordering
            })
        return results
