---
phase: 07-rag-retrieval-quality-improvements
plan: "02"
subsystem: query-pipeline
tags: [bm25, hybrid-search, rrf, reciprocal-rank-fusion, rag-01, feature-flags]
dependency_graph:
  requires:
    - "07-01"  # test infrastructure xfail stubs
  provides:
    - BM25Indexer (src/query/bm25_index.py)
    - rrf_fuse (src/query/rrf.py)
    - BM25+RRF pipeline integration
    - retrieval_config feature flags (partial — full in 07-05)
  affects:
    - src/query/pipeline.py
    - src/config/retrieval_config.py
tech_stack:
  added:
    - rank_bm25>=0.2.2
  patterns:
    - BM25Okapi keyword ranking with whitespace tokenization
    - Reciprocal Rank Fusion (k=60) for multi-source merge
    - Feature-flag-guarded hybrid retrieval (RAG_ENABLE_BM25)
    - Lazy import pattern for monkeypatching in tests
key_files:
  created:
    - src/query/bm25_index.py
    - src/query/rrf.py
    - src/config/retrieval_config.py
  modified:
    - src/query/pipeline.py
    - requirements.txt
decisions:
  - "BM25Indexer._built flag tracks build() calls to distinguish 'empty corpus' from 'never built'"
  - "rrf_fuse preserves first occurrence of duplicate chunk_ids — earlier lists take precedence"
  - "retrieval_config.py created early (07-02) to unblock pipeline integration; 07-05 owns full feature flag test coverage"
  - "_build_bm25_index returns None on any failure — silent fallback to pure vector results"
metrics:
  duration: "~18 minutes"
  completed: "2026-03-31"
  tasks_completed: 3
  files_created: 3
  files_modified: 2
---

# Phase 07 Plan 02: BM25 Hybrid Search + Reciprocal Rank Fusion Summary

BM25 keyword indexer and RRF fusion wired into the query pipeline behind a feature flag, addressing vocabulary mismatch failures where semantic vector search misses exact domain terms like "warranty".

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | BM25Indexer (bm25_index.py) | 3998a82 | src/query/bm25_index.py, requirements.txt |
| 2 | rrf_fuse (rrf.py) | 619b01d | src/query/rrf.py |
| 3 | Pipeline integration | 4883300 | src/query/pipeline.py, src/config/retrieval_config.py |

## What Was Built

**BM25Indexer** (`src/query/bm25_index.py`): Wraps `rank_bm25.BM25Okapi` for keyword-based chunk retrieval. Built from a list of chunk dicts at pipeline startup. Tokenization uses `text.lower().split()` — simple whitespace with no stemming, preserving automotive domain terms. Returns chunks with `source="bm25"` and `distance=1.0/(score+1e-9)` (lower = more relevant). Raises `RuntimeError` if `query()` called before `build()`. Empty corpus returns `[]` gracefully.

**rrf_fuse** (`src/query/rrf.py`): Implements Reciprocal Rank Fusion (Cormack et al. 2009) with `k=60`. Merges arbitrary numbers of ranked lists using `score = sum(1/(rank + 60))`. Deduplicates by `str(chunk_id)`. Annotates each result with `_rrf_score`. Chunks appearing in multiple sources (BM25 + vector) rank highest.

**Pipeline integration** (`src/query/pipeline.py`): Added `_build_bm25_index()` helper that fetches all chunks from SQLite and builds the index. In both `answer_question()` and `stream_answer_question()`: (1) runs BM25 search across all query variants when `RAG_ENABLE_BM25=True`, (2) calls `rrf_fuse(bm25_chunks, vector_chunks)` to merge, (3) passes fused results to `graph_expand()`. Falls back silently to pure vector results when BM25 build fails.

**Feature flags** (`src/config/retrieval_config.py`): Created as a prerequisite for pipeline integration. Reads `RAG_ENABLE_BM25`, `RAG_ENABLE_RERANKER`, `RAG_ENABLE_PARENT_DOC`, `RAG_ENABLE_ENRICHMENT` from environment. Defaults: BM25=True, reranker=True, parent-doc=False, enrichment=False.

## Test Results

All BM25/RRF xfail stubs now xpass:
- `test_bm25_indexer_build_and_query` — XPASS
- `test_bm25_indexer_empty_corpus` — XPASS
- `test_rrf_fuse_merges_two_ranked_lists` — XPASS
- `test_rrf_fuse_deduplicates` — XPASS

Feature flag tests (RAG-05 stubs) also xpass due to retrieval_config.py creation:
- `test_feature_flags_default_values` — XPASS
- `test_feature_flags_env_override` — XPASS

Full suite: **39 passed, 46 xpassed, 10 xfailed** — zero regressions.

## Deviations from Plan

### Auto-added Missing Critical Functionality

**1. [Rule 2 - Missing Prereq] Created src/config/retrieval_config.py early**
- **Found during:** Task 3 — pipeline.py imports `from src.config.retrieval_config import RAG_ENABLE_BM25`
- **Issue:** Plan references retrieval_config.py (a 07-05 artifact) but Task 3 adds an import inside answer_question(); without the module, any call to answer_question() would raise ImportError
- **Fix:** Created minimal retrieval_config.py with all 4 feature flags using env var reads; same implementation that 07-05 would have created
- **Bonus:** Feature flag tests (test_feature_flags_*) now xpass ahead of plan
- **Files modified:** src/config/retrieval_config.py (created)
- **Commit:** 4883300

**2. [Rule 1 - Bug] Fixed BM25Indexer query-before-build detection**
- **Found during:** Task 1 — plan code used ambiguous `not self._chunks` check which returns True for empty corpus, preventing RuntimeError from being raised correctly
- **Fix:** Added explicit `self._built` flag to track whether `build()` has been called; this correctly distinguishes "built with empty corpus" from "never built"
- **Files modified:** src/query/bm25_index.py

## Known Stubs

None — all created files have functional implementations, not placeholders.

## Self-Check: PASSED

- [x] `src/query/bm25_index.py` exists and exports `BM25Indexer`
- [x] `src/query/rrf.py` exists and exports `rrf_fuse`
- [x] `src/query/pipeline.py` contains `rrf_fuse` and `_build_bm25_index`
- [x] `src/config/retrieval_config.py` exists
- [x] `requirements.txt` contains `rank_bm25>=0.2.2`
- [x] Commits 3998a82, 619b01d, 4883300 exist in git log
- [x] All 4 BM25/RRF tests xpass
- [x] Zero test regressions (39 passed, 46 xpassed, 10 xfailed)
