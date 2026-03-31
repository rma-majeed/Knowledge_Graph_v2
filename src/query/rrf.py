"""Reciprocal Rank Fusion for hybrid BM25 + vector retrieval (RAG-01).

RRF formula: score(chunk) = sum over ranked_lists of 1.0 / (rank + k)
where rank is 1-based and k=60 (empirically optimal per 2009 Cormack et al.).

Usage:
    from src.query.rrf import rrf_fuse
    merged = rrf_fuse(bm25_results, vector_results)
    # Returns deduplicated list sorted by RRF score descending.
"""
from __future__ import annotations

_RRF_K = 60  # Standard RRF constant — do not change without benchmarking


def rrf_fuse(*ranked_lists: list[dict], k: int = _RRF_K) -> list[dict]:
    """Merge multiple ranked chunk lists using Reciprocal Rank Fusion.

    Each chunk's final score is the sum of 1/(rank + k) across all lists it
    appears in. Chunks appearing in multiple lists receive higher scores.
    Deduplication is by str(chunk_id).

    Args:
        *ranked_lists: One or more lists of chunk dicts. Each list is ordered
            best-first (rank 1 = index 0). Chunks must have a "chunk_id" key.
        k: RRF constant (default 60). Higher k reduces the impact of top ranks.

    Returns:
        Deduplicated list of chunk dicts sorted by RRF score descending.
        The original chunk dict from the first list occurrence is preserved.
        An "_rrf_score" key is added to each returned chunk.
    """
    scores: dict[str, float] = {}
    chunk_store: dict[str, dict] = {}

    for ranked in ranked_lists:
        for rank_0based, chunk in enumerate(ranked):
            cid = str(chunk.get("chunk_id", ""))
            if not cid:
                continue
            rank_1based = rank_0based + 1
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (rank_1based + k)
            if cid not in chunk_store:
                chunk_store[cid] = chunk

    merged = sorted(chunk_store.values(), key=lambda c: scores[str(c["chunk_id"])], reverse=True)
    for chunk in merged:
        cid = str(chunk["chunk_id"])
        chunk["_rrf_score"] = scores[cid]
    return merged
