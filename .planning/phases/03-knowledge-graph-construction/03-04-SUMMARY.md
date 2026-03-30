---
phase: 03-knowledge-graph-construction
plan: 04
subsystem: database
tags: [sqlite, citations, kuzu, graph-monitoring, entity-density]

# Dependency graph
requires:
  - phase: 03-02
    provides: extract_entities_relationships() — entity extraction from chunks
  - phase: 03-03
    provides: KuzuDB schema, upsert_entity() — entity persistence layer
provides:
  - CitationStore: SQLite bridge from KuzuDB canonical entities to source chunks
  - check_entity_density(): graph explosion detection with threshold alerts

affects: [03-05, 04-query-engine, phase-4-retrieval]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CitationStore mirrors ChunkStore pattern: wraps sqlite3.Connection, init_schema()/insert()/query()"
    - "INSERT OR IGNORE for idempotent citation writes"
    - "3-table JOIN (chunk_citations + chunks + documents) for full citation context"
    - "kuzu QueryResult.get_all() returns list-of-lists; index [0][0] for scalar COUNT"

key-files:
  created: []
  modified:
    - src/graph/citations.py
    - src/graph/monitor.py

key-decisions:
  - "Used executescript() for DDL with multiple statements (CREATE TABLE + CREATE INDEX) — matches ChunkStore pattern"
  - "monitor.py uses kuzu.Connection per call (no connection reuse) — consistent with db_manager.py pattern"
  - "Fixed kuzu API: QueryResult uses get_all() not fetchall(); returns list-of-lists not dicts"

patterns-established:
  - "Pattern: CitationStore.insert_citations() uses executemany with INSERT OR IGNORE for batch duplicate-safe writes"
  - "Pattern: monitor iterates all 5 entity tables individually — handles missing tables via try/except"

requirements-completed: [GRAPH-04]

# Metrics
duration: 50min
completed: 2026-03-30
---

# Phase 03 Plan 04: Citations and Monitor Summary

**CitationStore bridges KuzuDB entities to SQLite source chunks via 3-table JOIN; check_entity_density() guards against graph explosion (>50 entities/doc or >10K total) using kuzu get_all() API.**

## Performance

- **Duration:** ~50 min
- **Started:** 2026-03-30T07:49:33Z
- **Completed:** 2026-03-30T08:39:04Z
- **Tasks:** 2/2
- **Files modified:** 2

## Accomplishments

### Task 1: CitationStore in citations.py

Implemented `CitationStore` class in `src/graph/citations.py` replacing the NotImplementedError stub:

- `init_schema()`: Creates `chunk_citations` table with `UNIQUE(entity_canonical_name, entity_type, chunk_id)` constraint plus two indexes. Uses `executescript()` for multi-statement DDL.
- `insert_citations()`: Batch insert via `executemany` with `INSERT OR IGNORE` — duplicate citations silently skipped.
- `get_chunks_for_entity()`: 3-table JOIN (`chunk_citations JOIN chunks JOIN documents`) returns `{chunk_id, doc_id, filename, page_num}` dicts ordered by doc_id/page_num.

All 5 citation tests upgraded from XFAIL to XPASS.

### Task 2: check_entity_density() in monitor.py

Implemented `check_entity_density()` in `src/graph/monitor.py` replacing the NotImplementedError stub:

- Queries all 5 KuzuDB node tables (OEM, Supplier, Technology, Product, Recommendation) for node count
- Computes `density_per_doc` and `density_per_chunk`
- Sets `alert=True` with human-readable `reason` when `entity_count > 10000` or `density_per_doc > 50`
- Smoke test confirmed: single entity yields `entity_count=1, alert=False`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed kuzu QueryResult API mismatch**
- **Found during:** Task 2 smoke test
- **Issue:** Plan template used `.fetchall()` on kuzu QueryResult, but kuzu uses `.get_all()` which returns `list[list]` not `list[dict]`. COUNT result accessed as `result[0][0]` not `result[0]["cnt"]`.
- **Fix:** Replaced `.fetchall()` with `.get_all()` and changed index from `result[0]["cnt"]` to `result[0][0]`.
- **Files modified:** `src/graph/monitor.py`
- **Commit:** cf763bc

## Test Results

```
tests/test_citations.py::test_init_schema_creates_table    XPASS
tests/test_citations.py::test_insert_chunk_citation        XPASS
tests/test_citations.py::test_insert_duplicate_citation_ignored XPASS
tests/test_citations.py::test_get_chunks_for_entity        XPASS
tests/test_citations.py::test_get_chunks_for_entity_empty  XPASS

Full suite: 21 passed, 2 deselected, 36 xpassed in 12.17s
```

## Known Stubs

None — all methods fully implemented and tested.

## Commits

| Task | Commit | Message |
|------|--------|---------|
| Task 1: CitationStore | 43a9350 | feat(03-04): implement CitationStore in citations.py |
| Task 2: monitor | cf763bc | feat(03-04): implement check_entity_density() in monitor.py |
