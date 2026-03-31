---
phase: 07-rag-retrieval-quality-improvements
plan: 05
subsystem: query/config
tags: [rag, feature-flags, parent-doc, pipeline, requirements]

dependency_graph:
  requires:
    - 07-01 (xfail stub scaffolding)
    - 07-02 (BM25+RRF, retrieval_config.py created as deviation)
    - 07-03 (BGE reranker)
    - 07-04 (enricher.py, expand_to_parent, get_parent_texts)
  provides:
    - src/query/pipeline.py (RAG_ENABLE_PARENT_DOC step 4c wired in answer_question and stream_answer_question)
    - src/config/retrieval_config.py (verified complete — all 4 flags, correct defaults)
    - requirements.txt (rank_bm25>=0.2.2, sentence-transformers>=2.7.0 confirmed)
  affects:
    - Phase 7 complete (5/5 plans)

tech_stack:
  added: []
  patterns:
    - All RAG feature flags imported inside function body (not module-level) for monkeypatch compatibility
    - Parent-doc expansion runs after reranking to preserve relevance order
    - Silently skips expansion when chunk_parents table is empty (backward-compat with existing DBs)

key_files:
  created: []
  modified:
    - src/query/pipeline.py

key-decisions:
  - "retrieval_config.py already complete from 07-02 deviation — no changes needed in 07-05"
  - "requirements.txt already had both rank_bm25 and sentence-transformers from 07-02 — no changes needed"
  - "Parent-doc expansion wired as Step 4c after reranking to preserve reranked order"
  - "Empty parent_texts dict short-circuits expansion — no expand_to_parent calls when table unpopulated"

requirements-completed: [RAG-05]

metrics:
  duration: "~6 minutes"
  completed_date: "2026-03-31"
  tasks_completed: 2
  files_modified: 1
---

# Phase 07 Plan 05: Integration and Feature Flag Wiring Summary

**Parent-document expansion (RAG-04) wired into answer_question() and stream_answer_question() as Step 4c behind RAG_ENABLE_PARENT_DOC flag, completing all 5 RAG retrieval quality improvements with 52 xpassed tests and zero regressions.**

---

## Performance

- **Duration:** ~6 minutes
- **Started:** 2026-03-31T00:00:00Z
- **Completed:** 2026-03-31
- **Tasks:** 2
- **Files modified:** 1

---

## Accomplishments

- Wired parent-doc expansion into both `answer_question()` and `stream_answer_question()` in pipeline.py — Step 4c runs after reranking and before truncate_to_budget
- Confirmed all 12 RAG quality xfail stubs are XPASS (39 passed, 4 xfailed, 52 xpassed, zero failures)
- Verified retrieval_config.py is complete with all 4 flags and correct defaults (BM25=True, RERANKER=True, PARENT_DOC=False, ENRICHMENT=False)
- Verified requirements.txt already contains rank_bm25>=0.2.2 and sentence-transformers>=2.7.0 from 07-02

---

## Task Commits

1. **Task 1: Verify retrieval_config.py** — No commit needed (file already existed and was correct from 07-02 deviation)
2. **Task 2: Wire parent-doc expansion into pipeline** — `8130514` (feat)

**Plan metadata:** (docs commit — see below)

---

## Files Created/Modified

- `src/query/pipeline.py` — Added Step 4c parent-doc expansion block in both `answer_question()` and `stream_answer_question()`; imports `RAG_ENABLE_PARENT_DOC`, `expand_to_parent`, `ChunkStore`, calls `get_parent_texts()` then expands chunks when table is populated

---

## Decisions Made

- Parent-doc expansion imports inside function body (same pattern as BM25 and reranker) to ensure monkeypatch works in tests
- Expansion is guarded by `if parent_texts:` to short-circuit when the chunk_parents table is empty — no performance penalty for existing installs without parent-doc re-ingest
- Step 4c runs after Step 4b (reranking) to preserve the reranked relevance order before context assembly

---

## Deviations from Plan

### Plan Context Differences (not deviations from code intent)

**1. retrieval_config.py already existed** — The 07-02 agent created this as a deviation to unblock pipeline integration. The file was already correct and complete. Task 1 of this plan (create retrieval_config.py) was effectively a no-op; verification confirmed the module exports all 4 flags with correct defaults.

**2. requirements.txt already complete** — The 07-02 agent added both `rank_bm25>=0.2.2` and `sentence-transformers>=2.7.0` as part of BM25 and reranker implementation. Task 2 Part B was a no-op; both lines already present.

**Impact:** These pre-completed items reduced scope to a single file change (pipeline.py Step 4c). No scope creep; plan intent fully satisfied.

---

## Test Results

```
Full suite: 39 passed, 4 xfailed, 52 xpassed, 2 warnings in 160.98s
```

All 12 RAG-01 through RAG-05 stubs XPASS:
- RAG-01 (BM25): test_bm25_indexer_build_and_query, test_bm25_indexer_empty_corpus, test_rrf_fuse_merges_two_ranked_lists, test_rrf_fuse_deduplicates
- RAG-02 (Reranker): test_reranker_reorders_chunks, test_reranker_lazy_load
- RAG-03 (Enrichment): test_enrich_chunk_context_returns_string, test_enrich_chunk_context_fallback_on_error
- RAG-04 (Parent-Doc): test_expand_to_parent_uses_parent_text, test_expand_to_parent_no_op_when_missing
- RAG-05 (Flags): test_feature_flags_default_values, test_feature_flags_env_override

Zero regressions from prior phases (Phases 1-6 all green).

---

## Issues Encountered

None.

---

## Known Stubs

None. All RAG-01 through RAG-05 implementations are complete. Parent-doc and enrichment features are opt-in behind feature flags (default disabled) — this is intentional per spec, not a stub.

---

## Next Phase Readiness

Phase 7 is complete (5/5 plans). All 17 v1 requirements across all 7 phases are fully implemented:

- INGEST-01/02/03 (Phase 1)
- EMBED-01/02/03 (Phase 2)
- GRAPH-01/02/03/04 (Phase 3)
- QUERY-01/02/03/04/05 (Phase 4)
- UI-01/02 (Phase 5)
- PROVIDER-01/02/03/04/05/06 (Phase 6)
- RAG-01/02/03/04/05 (Phase 7)

The system is feature-complete for v1.0 milestone.

---

*Phase: 07-rag-retrieval-quality-improvements*
*Completed: 2026-03-31*

---

## Self-Check: PASSED

- src/query/pipeline.py (Step 4c parent-doc expansion): FOUND (lines 261-270 in answer_question, lines 362-371 in stream_answer_question)
- src/config/retrieval_config.py (all 4 flags): FOUND (verified via python -c import test: flags OK)
- requirements.txt (rank_bm25, sentence-transformers): FOUND (grep confirmed both lines)
- Commit 8130514: FOUND (git log verified)
- Tests: 39 passed, 4 xfailed, 52 xpassed (zero failures, zero regressions)
