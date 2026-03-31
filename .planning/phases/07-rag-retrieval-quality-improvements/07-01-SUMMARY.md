---
phase: 07-rag-retrieval-quality-improvements
plan: "01"
subsystem: tests
tags: [tdd, xfail, fixtures, bm25, reranker, enrichment, parent-doc, feature-flags]
dependency_graph:
  requires: []
  provides:
    - tests/test_retrieval_quality.py (12 xfail stubs for RAG-01..RAG-05)
    - tests/conftest.py Phase 7 fixtures
  affects:
    - tests/conftest.py
tech_stack:
  added: []
  patterns:
    - xfail(strict=False) stubs for TDD wave-0 (same as phases 1-6)
    - try/except imports inside test functions (same as 06-01)
key_files:
  created:
    - tests/test_retrieval_quality.py
  modified:
    - tests/conftest.py
decisions:
  - xfail(strict=False) for all RAG-01..RAG-05 stubs — auto-pass once implementations land
  - fixtures added as append-only block after Phase 6 section — no existing fixtures modified
metrics:
  duration_seconds: 473
  completed_date: "2026-03-31"
  tasks_completed: 2
  files_modified: 2
---

# Phase 7 Plan 01: Test Infrastructure — RAG Retrieval Quality Summary

**One-liner:** xfail stub test file (12 stubs, RAG-01..RAG-05) and Phase 7 conftest fixtures (bm25_corpus, mock_reranker_scores, sample_enriched_chunks, chunk_parent_map).

---

## What Was Built

### Task 1: Phase 7 fixtures in conftest.py

Four fixtures appended to `tests/conftest.py` after the existing Phase 6 section:

- **`bm25_corpus`** — 5-chunk list matching retriever.py chunk shape `{chunk_id, text, filename, page_num, source, distance}`. Two chunks contain "warranty" (IDs "1" and "4") to exercise keyword ranking.
- **`mock_reranker_scores`** — List of 5 floats `[0.92, 0.31, 0.15, 0.88, 0.42]` simulating CrossEncoder.predict() output. Index-aligned with bm25_corpus.
- **`sample_enriched_chunks`** — 2 chunks: one with `enriched_text` set, one with `enriched_text=None` — covers both branches of the enrichment path.
- **`chunk_parent_map`** — Dict mapping child_chunk_id to parent_chunk_id (identity mapping for v1) for parent-document retrieval tests.

### Task 2: tests/test_retrieval_quality.py

190-line file with 12 xfail stubs grouped by requirement:

| Requirement | Tests | Imports asserted |
|-------------|-------|-----------------|
| RAG-01: BM25 + RRF | 4 | `src.query.bm25_index.BM25Indexer`, `src.query.rrf.rrf_fuse` |
| RAG-02: Reranker | 2 | `src.query.reranker.Reranker` |
| RAG-03: Enrichment | 2 | `src.ingest.enricher.enrich_chunk_context` |
| RAG-04: Parent-doc | 2 | `src.query.assembler.expand_to_parent` |
| RAG-05: Feature flags | 2 | `src.config.retrieval_config` |

All imports are inside test function bodies (try-via-xfail) so missing modules do not cause collection failures.

---

## Verification Results

```
# Targeted run
12 xfailed in 13.41s

# Full suite (no regressions)
39 passed, 16 xfailed, 40 xpassed, 2 warnings in 178.53s
```

Zero collection errors. Zero test failures. Zero regressions in prior phases.

---

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | fcab6bd | feat(07-01): add Phase 7 RAG quality fixtures to conftest.py |
| 2 | 36a0f67 | feat(07-01): create test_retrieval_quality.py with 12 xfail stubs (RAG-01..RAG-05) |

---

## Deviations from Plan

None — plan executed exactly as written.

---

## Known Stubs

All stubs are intentional xfail test stubs, not data stubs. No hardcoded empty values or placeholder data flow to UI. The following modules are expected to be absent until later plans:

| Module | Expected in Plan |
|--------|-----------------|
| `src/query/bm25_index.py` | 07-02 |
| `src/query/rrf.py` | 07-02 |
| `src/query/reranker.py` | 07-03 |
| `src/ingest/enricher.py` | 07-04 |
| `src/query/assembler.expand_to_parent` | 07-04 |
| `src/config/retrieval_config.py` | 07-05 |

---

## Self-Check: PASSED

Files exist:
- tests/test_retrieval_quality.py — FOUND
- tests/conftest.py (modified) — FOUND

Commits exist:
- fcab6bd — FOUND
- 36a0f67 — FOUND
