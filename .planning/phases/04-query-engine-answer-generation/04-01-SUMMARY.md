---
phase: 04-query-engine-answer-generation
plan: "01"
subsystem: query
tags: [scaffold, xfail, stubs, tdd, query-engine]
dependency_graph:
  requires: []
  provides: [src/query package stubs, xfail test stubs for QUERY-01 through QUERY-05]
  affects: [04-02-retriever, 04-03-assembler, 04-04-pipeline]
tech_stack:
  added: []
  patterns: [xfail-strict-false stubs, NotImplementedError source stubs, lm_studio pytest marker]
key_files:
  created:
    - src/query/__init__.py
    - src/query/retriever.py
    - src/query/assembler.py
    - src/query/pipeline.py
    - tests/test_query_retriever.py
    - tests/test_query_assembler.py
    - tests/test_query_pipeline.py
  modified: []
decisions:
  - "lm_studio marker was already registered in tests/conftest.py — no modification needed"
  - "strict=False used on all xfail stubs so tests show xfailed rather than errors before implementation"
metrics:
  duration: ~5 minutes
  completed: 2026-03-31
  tasks_completed: 2
  files_created: 7
  files_modified: 0
---

# Phase 4 Plan 01: Test Infrastructure Summary

**One-liner:** xfail test scaffold and NotImplementedError source stubs for src/query package covering QUERY-01 through QUERY-05.

## What Was Created

### Source stubs (`src/query/`)

| File | Public API | Implemented by |
|------|-----------|----------------|
| `__init__.py` | Package marker | — |
| `retriever.py` | `vector_search`, `graph_expand`, `deduplicate_chunks`, `hybrid_retrieve` | Plan 04-02 |
| `assembler.py` | `truncate_to_budget`, `build_citations`, `format_answer`, `build_prompt`, `CONTEXT_TOKEN_BUDGET`, `CITATION_HIGH_CONFIDENCE_THRESHOLD` | Plan 04-03 |
| `pipeline.py` | `answer_question`, `DEFAULT_LLM_MODEL`, `DEFAULT_EMBED_MODEL` | Plan 04-04 |

### Test stubs (`tests/`)

| File | Tests | Requirements |
|------|-------|-------------|
| `test_query_retriever.py` | 4 xfail stubs | QUERY-02, QUERY-03 |
| `test_query_assembler.py` | 4 xfail stubs | QUERY-04 |
| `test_query_pipeline.py` | 3 xfail stubs (incl. `lm_studio` integration) | QUERY-01, QUERY-05 |

Total: 11 xfail stubs across 3 test files.

## Verification Result

```
pytest tests/test_query_retriever.py tests/test_query_assembler.py tests/test_query_pipeline.py -x -q -k "not lm_studio"
# 1 deselected, 10 xfailed in 13.63s

pytest tests/ -x -q -k "not lm_studio" --tb=short
# 21 passed, 2 deselected, 10 xfailed, 37 xpassed in 36.36s
```

All 10 stubs (excluding lm_studio integration test) xfail cleanly. Full prior test suite remains green.

## Deviations from Plan

**1. [No-op] lm_studio marker already registered**
- The plan specified adding `lm_studio` marker to `conftest.py`, but it was already present from a prior phase.
- No change was made to `conftest.py`.
- Impact: None — marker works correctly as-is.

## Known Stubs

All stubs are intentional scaffolding — the entire purpose of this plan is to create xfail stubs before implementation. They will be resolved in plans 04-02, 04-03, and 04-04:

| File | Stub | Resolved by |
|------|------|------------|
| `src/query/retriever.py` | `vector_search`, `graph_expand`, `deduplicate_chunks`, `hybrid_retrieve` | Plan 04-02 |
| `src/query/assembler.py` | `truncate_to_budget`, `build_citations`, `format_answer`, `build_prompt` | Plan 04-03 |
| `src/query/pipeline.py` | `answer_question` | Plan 04-04 |

## Commit

`0a5771e` — `test(04-01): scaffold src/query package stubs and xfail test stubs for query engine`

## Self-Check: PASSED

- `src/query/__init__.py` — exists
- `src/query/retriever.py` — exists
- `src/query/assembler.py` — exists
- `src/query/pipeline.py` — exists
- `tests/test_query_retriever.py` — exists
- `tests/test_query_assembler.py` — exists
- `tests/test_query_pipeline.py` — exists
- Commit `0a5771e` — verified present
