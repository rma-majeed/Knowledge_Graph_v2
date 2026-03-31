---
phase: 07-rag-retrieval-quality-improvements
plan: "03"
subsystem: query
tags: [reranker, cross-encoder, bge, rag, pipeline, feature-flags]
dependency_graph:
  requires: ["07-01"]
  parallel_with: ["07-02"]
  provides: ["RAG-02", "RAG-05-partial"]
  affects: ["src/query/pipeline.py", "src/query/reranker.py", "src/config/retrieval_config.py"]
tech_stack:
  added: ["sentence-transformers>=2.7.0"]
  patterns: ["lazy-load model", "pure helper _reorder()", "feature flag env var", "in-function import for monkeypatch"]
key_files:
  created:
    - src/query/reranker.py
    - src/config/retrieval_config.py
  modified:
    - src/query/pipeline.py
    - requirements.txt
decisions:
  - "_model is None before first rerank() ensures no BGE model download at import time"
  - "RAG_ENABLE_RERANKER import inside function body so monkeypatch works in tests"
  - "Reranker() instantiated per-call (no module singleton) — lazy load is per-instance"
  - "_reorder() pure function (no model touch) enables score injection in unit tests"
  - "retrieval_config.py created now (Rule 3 fix) rather than waiting for 07-05"
metrics:
  duration_seconds: 414
  completed_date: "2026-03-31"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 2
---

# Phase 07 Plan 03: BGE Cross-Encoder Reranker Summary

**One-liner:** Lazy-loading BGE cross-encoder reranker (BAAI/bge-reranker-v2-m3 via sentence-transformers) wired into query pipeline after graph expansion, behind RAG_ENABLE_RERANKER feature flag.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement Reranker class (src/query/reranker.py) | b8e35d9 | src/query/reranker.py, requirements.txt |
| 2 | Wire Reranker into query pipeline | ebceeaf | src/query/pipeline.py, src/config/retrieval_config.py |

## What Was Built

### src/query/reranker.py

`Reranker` class with:
- `__init__()` sets `self._model = None` — no download at construction
- `_load_model()` imports `CrossEncoder` from sentence-transformers on first call; catches all exceptions and leaves `_model = None` on failure (graceful degradation)
- `_reorder(chunks, scores)` — pure function, sorts (score, chunk) pairs descending, adds `_rerank_score` key to each chunk; does not touch `_model`
- `rerank(query, chunks, top_n, batch_size)` — lazy-loads model, calls `CrossEncoder.predict()` on (query, chunk_text) pairs in batches, returns original order if model unavailable

### src/config/retrieval_config.py

Feature flag module for all RAG improvements:
- `RAG_ENABLE_BM25` — default `True`
- `RAG_ENABLE_RERANKER` — default `True`
- `RAG_ENABLE_PARENT_DOC` — default `False` (opt-in)
- `RAG_ENABLE_ENRICHMENT` — default `False` (opt-in)

Each flag reads from env var (`_bool_env()` helper), supports `'true'`/`'false'` case-insensitive.

### src/query/pipeline.py changes

Step 4b inserted in both `answer_question()` and `stream_answer_question()`:

```python
# Step 4b: Cross-encoder reranking (RAG-02) — after graph expand, before budget truncation
from src.config.retrieval_config import RAG_ENABLE_RERANKER
if RAG_ENABLE_RERANKER and chunks:
    from src.query.reranker import Reranker
    reranker = Reranker()
    chunks = reranker.rerank(retrieval_query, chunks)
```

Pipeline flow: rewrite → expand queries → vector search → graph expand → **rerank** → truncate_to_budget → build prompt → LLM.

## Test Results

| Test | Status |
|------|--------|
| test_reranker_lazy_load | XPASS |
| test_reranker_reorders_chunks | XPASS |
| test_feature_flags_default_values | XPASS (bonus — retrieval_config.py created) |
| test_feature_flags_env_override | XPASS (bonus — retrieval_config.py created) |
| Full suite | 39 passed, 12 xfailed, 44 xpassed, 0 failures |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created src/config/retrieval_config.py ahead of schedule**
- **Found during:** Task 2
- **Issue:** `pipeline.py` imports `RAG_ENABLE_RERANKER` from `src.config.retrieval_config`. Module didn't exist (planned for 07-05), making pipeline import fail when `RAG_ENABLE_RERANKER=true` branch executed.
- **Fix:** Created minimal `retrieval_config.py` with all four RAG feature flags (`RAG_ENABLE_BM25`, `RAG_ENABLE_RERANKER`, `RAG_ENABLE_PARENT_DOC`, `RAG_ENABLE_ENRICHMENT`) with correct defaults matching the 07-05 test expectations.
- **Files modified:** src/config/retrieval_config.py (created)
- **Commit:** ebceeaf
- **Impact:** RAG-05 xfail stubs for `test_feature_flags_*` now XPASS as a bonus — 07-05 can build on this module without recreation.

## Known Stubs

None — all functionality is wired end-to-end. The Reranker gracefully falls back to original chunk order if `sentence-transformers` is not installed or the BGE model is unavailable, so the pipeline works without the model downloaded.

## Self-Check: PASSED
