"""Phase 7: RAG Retrieval Quality — xfail stubs and unit tests.

Tests cover RAG-01 through RAG-05. All stubs use xfail(strict=False) so they
appear as xfail (expected failure) until the implementation lands, then auto-pass
as xpass without requiring test file changes.

Run subset: pytest tests/test_retrieval_quality.py -q
Full suite:  pytest tests/ -q
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# RAG-01: BM25 hybrid search + Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=False, reason="RAG-01: bm25_index.py not yet implemented")
def test_bm25_indexer_build_and_query(bm25_corpus):
    """BM25Indexer builds from corpus and returns ranked chunk_ids for a keyword query."""
    from src.query.bm25_index import BM25Indexer
    indexer = BM25Indexer()
    indexer.build(bm25_corpus)
    results = indexer.query("warranty", n_results=3)
    assert isinstance(results, list)
    assert len(results) <= 3
    # chunk_id "1" and "4" both mention "warranty" — at least one should appear
    result_ids = [r["chunk_id"] for r in results]
    assert any(cid in result_ids for cid in ["1", "4"])


@pytest.mark.xfail(strict=False, reason="RAG-01: bm25_index.py not yet implemented")
def test_bm25_indexer_empty_corpus():
    """BM25Indexer.query() returns [] gracefully on empty corpus (no crash)."""
    from src.query.bm25_index import BM25Indexer
    indexer = BM25Indexer()
    indexer.build([])
    results = indexer.query("warranty", n_results=5)
    assert results == []


@pytest.mark.xfail(strict=False, reason="RAG-01: rrf.py not yet implemented")
def test_rrf_fuse_merges_two_ranked_lists(bm25_corpus):
    """rrf_fuse() merges BM25 and vector ranked lists, scores by 1/(rank+60)."""
    from src.query.rrf import rrf_fuse
    bm25_ranked = [bm25_corpus[0], bm25_corpus[3]]   # warranty chunks
    vector_ranked = [bm25_corpus[3], bm25_corpus[1]]  # partial overlap
    merged = rrf_fuse(bm25_ranked, vector_ranked)
    assert isinstance(merged, list)
    assert len(merged) >= 2
    # chunk_id "4" appears in both lists — should score highest
    top_id = str(merged[0]["chunk_id"])
    assert top_id == "4"


@pytest.mark.xfail(strict=False, reason="RAG-01: rrf.py not yet implemented")
def test_rrf_fuse_deduplicates(bm25_corpus):
    """rrf_fuse() output contains no duplicate chunk_ids."""
    from src.query.rrf import rrf_fuse
    merged = rrf_fuse(bm25_corpus[:3], bm25_corpus[1:4])
    ids = [str(r["chunk_id"]) for r in merged]
    assert len(ids) == len(set(ids)), "rrf_fuse returned duplicate chunk_ids"


# ---------------------------------------------------------------------------
# RAG-02: BGE cross-encoder reranker
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=False, reason="RAG-02: reranker.py not yet implemented")
def test_reranker_reorders_chunks(bm25_corpus, mock_reranker_scores):
    """Reranker.rerank() returns chunks re-ordered by cross-encoder score descending."""
    from src.query.reranker import Reranker
    # Use a mock that bypasses model download
    reranker = Reranker.__new__(Reranker)
    reranker._model = None
    # Inject scores directly to test ordering logic
    reranker._scores = mock_reranker_scores  # [0.92, 0.31, 0.15, 0.88, 0.42]
    # chunk 0 score=0.92, chunk 3 score=0.88 → those should be top 2
    reranked = reranker._reorder(bm25_corpus, mock_reranker_scores)
    assert reranked[0]["chunk_id"] == "1"   # score 0.92
    assert reranked[1]["chunk_id"] == "4"   # score 0.88


@pytest.mark.xfail(strict=False, reason="RAG-02: reranker.py not yet implemented")
def test_reranker_lazy_load():
    """Reranker._model is None before first rerank() call (lazy loading)."""
    from src.query.reranker import Reranker
    r = Reranker()
    assert r._model is None


# ---------------------------------------------------------------------------
# RAG-03: Contextual chunk enrichment
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=False, reason="RAG-03: enricher.py not yet implemented")
def test_enrich_chunk_context_returns_string():
    """enrich_chunk_context() returns a non-empty string summary for a given chunk text."""
    from src.ingest.enricher import enrich_chunk_context
    mock_client = type("C", (), {})()

    def fake_complete(*a, **kw):
        class R:
            class choices:
                class _0:
                    class message:
                        content = "Context: This document discusses warranty management systems."
                _0 = _0()
            choices = [_0()]
        return R()

    mock_client.chat = type("Chat", (), {"completions": type("Comp", (), {"create": staticmethod(fake_complete)})()})()
    result = enrich_chunk_context("warranty cost reduction text", mock_client, "test-model")
    assert isinstance(result, str)
    assert len(result) > 10


@pytest.mark.xfail(strict=False, reason="RAG-03: enricher.py not yet implemented")
def test_enrich_chunk_context_fallback_on_error():
    """enrich_chunk_context() returns original text when LLM call fails (graceful fallback)."""
    from src.ingest.enricher import enrich_chunk_context

    class BrokenClient:
        class chat:
            class completions:
                @staticmethod
                def create(*a, **kw):
                    raise RuntimeError("LM Studio unavailable")

    result = enrich_chunk_context("some chunk text", BrokenClient(), "model")
    assert result == "some chunk text"


# ---------------------------------------------------------------------------
# RAG-04: Parent-document retrieval
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=False, reason="RAG-04: expand_to_parent() not yet implemented in assembler.py")
def test_expand_to_parent_uses_parent_text(sample_enriched_chunks):
    """expand_to_parent() replaces chunk text with parent text when available."""
    from src.query.assembler import expand_to_parent
    # chunk_id "10" has a parent in the map
    parent_texts = {"10": "Full parent passage about warranty management with broader context."}
    chunk = sample_enriched_chunks[0]
    expanded = expand_to_parent(chunk, parent_texts)
    assert expanded["text"] == parent_texts["10"]


@pytest.mark.xfail(strict=False, reason="RAG-04: expand_to_parent() not yet implemented in assembler.py")
def test_expand_to_parent_no_op_when_missing(sample_enriched_chunks):
    """expand_to_parent() returns chunk unchanged when no parent mapping exists."""
    from src.query.assembler import expand_to_parent
    chunk = sample_enriched_chunks[0]
    expanded = expand_to_parent(chunk, {})   # empty parent map
    assert expanded["text"] == chunk["text"]


# ---------------------------------------------------------------------------
# RAG-05: Feature flags — all improvements configurable and additive
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=False, reason="RAG-05: retrieval_config.py not yet implemented")
def test_feature_flags_default_values(monkeypatch):
    """RAG feature flags default to expected values when env vars are unset."""
    for var in ("RAG_ENABLE_BM25", "RAG_ENABLE_RERANKER", "RAG_ENABLE_PARENT_DOC", "RAG_ENABLE_ENRICHMENT"):
        monkeypatch.delenv(var, raising=False)
    import importlib
    import src.config.retrieval_config as rc
    importlib.reload(rc)
    assert rc.RAG_ENABLE_BM25 is True
    assert rc.RAG_ENABLE_RERANKER is True
    assert rc.RAG_ENABLE_PARENT_DOC is False   # opt-in
    assert rc.RAG_ENABLE_ENRICHMENT is False   # opt-in


@pytest.mark.xfail(strict=False, reason="RAG-05: retrieval_config.py not yet implemented")
def test_feature_flags_env_override(monkeypatch):
    """RAG feature flags can be individually overridden via environment variables."""
    monkeypatch.setenv("RAG_ENABLE_BM25", "false")
    monkeypatch.setenv("RAG_ENABLE_RERANKER", "false")
    monkeypatch.setenv("RAG_ENABLE_PARENT_DOC", "true")
    monkeypatch.setenv("RAG_ENABLE_ENRICHMENT", "true")
    import importlib
    import src.config.retrieval_config as rc
    importlib.reload(rc)
    assert rc.RAG_ENABLE_BM25 is False
    assert rc.RAG_ENABLE_RERANKER is False
    assert rc.RAG_ENABLE_PARENT_DOC is True
    assert rc.RAG_ENABLE_ENRICHMENT is True
