"""BGE cross-encoder reranker for RAG-02.

Wraps BAAI/bge-reranker-v2-m3 via sentence-transformers CrossEncoder.
Model is lazily loaded on first rerank() call — no download at import time.

Hardware: CPU inference with use_fp16=False (32GB RAM, 4GB VRAM constraint).
Latency: ~130ms per 16-pair batch on CPU; ~200ms for 30 candidates.

Usage:
    from src.query.reranker import Reranker
    reranker = Reranker()
    reranked_chunks = reranker.rerank(query, chunks, top_n=20)
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_BGE_MODEL_ID = "BAAI/bge-reranker-v2-m3"
_DEFAULT_BATCH_SIZE = 16
_singleton: "Reranker | None" = None


def get_reranker() -> "Reranker":
    """Return the module-level Reranker singleton (created on first call)."""
    global _singleton
    if _singleton is None:
        _singleton = Reranker()
    return _singleton


class Reranker:
    """Lazy-loading BGE cross-encoder reranker.

    The sentence-transformers CrossEncoder model is loaded on first rerank() call.
    Subsequent calls reuse the loaded model (module-level caching via self._model).

    Attributes:
        _model: CrossEncoder instance, or None if not yet loaded.
    """

    def __init__(self) -> None:
        self._model = None

    def _load_model(self):
        """Load BAAI/bge-reranker-v2-m3 via sentence-transformers (CPU, fp32).

        Called automatically on first rerank() invocation.
        Subsequent calls are no-ops (model already loaded).
        """
        if self._model is not None:
            return
        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(
                _BGE_MODEL_ID,
                max_length=512,
                device="cpu",
            )
            # Disable fp16 for CPU stability on Windows (4GB VRAM constraint)
            if hasattr(self._model.model, "half"):
                pass  # keep fp32 — do not call .half()
            logger.info("BGE reranker loaded: %s", _BGE_MODEL_ID)
        except Exception as exc:
            logger.warning("BGE reranker failed to load (%s) — reranking disabled", exc)
            self._model = None

    def _reorder(self, chunks: list[dict], scores: list[float]) -> list[dict]:
        """Re-order chunks by score descending. Pure function — does not touch _model.

        Args:
            chunks: List of chunk dicts to reorder.
            scores: Parallel list of float scores from CrossEncoder.predict().

        Returns:
            Chunks sorted by score descending. Adds "_rerank_score" key to each.
        """
        paired = sorted(
            zip(scores, chunks),
            key=lambda x: x[0],
            reverse=True,
        )
        result = []
        for score, chunk in paired:
            c = dict(chunk)
            c["_rerank_score"] = float(score)
            result.append(c)
        return result

    def rerank(
        self,
        query: str,
        chunks: list[dict],
        top_n: int | None = None,
        batch_size: int = _DEFAULT_BATCH_SIZE,
    ) -> list[dict]:
        """Score (query, chunk_text) pairs and return re-ordered chunks.

        Lazily loads the CrossEncoder model on first call. If model fails to load
        (network unavailable, sentence-transformers not installed), returns chunks
        in original order (graceful fallback).

        Args:
            query: The user query string.
            chunks: Candidate chunks from BM25+vector+graph merge.
            top_n: If set, return only the top-N chunks after reranking.
            batch_size: Number of pairs per CrossEncoder batch (default 16 for CPU).

        Returns:
            Chunks sorted by cross-encoder score descending, with "_rerank_score" added.
            Returns chunks unchanged if model unavailable.
        """
        if not chunks:
            return []

        self._load_model()
        if self._model is None:
            logger.warning("Reranker unavailable — returning chunks in original order")
            return chunks

        pairs = [[query, c.get("text", "")] for c in chunks]

        try:
            scores = self._model.predict(pairs, batch_size=batch_size, show_progress_bar=False)
            reranked = self._reorder(chunks, list(scores))
        except Exception as exc:
            logger.warning("Reranker.predict() failed (%s) — returning original order", exc)
            return chunks

        if top_n is not None:
            return reranked[:top_n]
        return reranked
