---
phase: 02-embedding-vector-search
plan: 03
subsystem: database
tags: [chromadb, vector-store, embeddings, cosine-similarity, hnsw]

requires:
  - phase: 02-01
    provides: embed_chunks() and embed_query() functions from embedder.py

provides:
  - VectorStore class wrapping ChromaDB PersistentClient with cosine HNSW index
  - upsert() for idempotent embedding storage with 5-field metadata co-location
  - query() for top-N semantic search with count guard against NotEnoughElementsException
  - count() for collection size inspection

affects:
  - 02-04-embedding-pipeline (consumes VectorStore for batch indexing)
  - 04-query-engine (uses VectorStore.query() for retrieval with citation metadata)

tech-stack:
  added: []
  patterns:
    - "ChromaDB EphemeralClient shared-state reset via SharedSystemClient.clear_system_cache() in conftest for test isolation"
    - "VectorStore.__new__() + _collection injection pattern for unit tests without disk I/O"
    - "min(n_results, collection.count()) guard to prevent NotEnoughElementsException"
    - "try/except around get_or_create_collection to handle persisted configuration edge case"

key-files:
  created: []
  modified:
    - src/embed/vector_store.py
    - tests/conftest.py

key-decisions:
  - "Use _collection (underscore prefix) attribute name — required by test _collection bypass pattern"
  - "Add reset_chromadb_state autouse fixture to conftest.py using SharedSystemClient.clear_system_cache() to fix EphemeralClient in-process state sharing"
  - "try/except on get_or_create_collection to handle ChromaDB 1.5.5+ configuration persistence"

patterns-established:
  - "VectorStore._collection: attribute name locked by test bypass pattern — do not rename"
  - "Count guard: always use min(n_results, self._collection.count()) before query"

requirements-completed:
  - EMBED-02
  - EMBED-03

duration: 12min
completed: 2026-03-30
---

# Phase 02 Plan 03: Vector Store Summary

**ChromaDB PersistentClient wrapper with cosine HNSW index, idempotent upsert, and count-guarded top-N query for citation-ready metadata retrieval**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-30T05:13:36Z
- **Completed:** 2026-03-30T05:25:00Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- VectorStore class implemented in src/embed/vector_store.py replacing NotImplementedError stubs
- All 6 previously-xfail VectorStore unit tests now XPASS (upsert, query N results, small collection guard, metadata fields, metadata retrievable, latency under 50ms)
- ChromaDB EphemeralClient test isolation fixed in conftest.py — prevents state bleed between tests sharing collection name "test"

## Task Commits

1. **Task 1: Implement VectorStore class** - `4cc7ca8` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/embed/vector_store.py` - VectorStore class with __init__, upsert(), query(), count() methods
- `tests/conftest.py` - Added reset_chromadb_state autouse fixture using SharedSystemClient.clear_system_cache()

## Decisions Made

- Used `_collection` (underscore prefix) as the ChromaDB collection attribute name — the test suite uses `VectorStore.__new__(VectorStore)` + `vs._collection = ...` injection pattern, so the attribute name is part of the contract
- Added `try/except` around `get_or_create_collection` with configuration to handle ChromaDB 1.5.5+ behavior where re-passing configuration on an existing collection raises an error
- Fixed EphemeralClient state sharing in conftest.py via `SharedSystemClient.clear_system_cache()` — ChromaDB's EphemeralClient is a shared singleton within a process; multiple tests using collection name "test" bleed data without this reset

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ChromaDB EphemeralClient in-process state sharing between tests**
- **Found during:** Task 1 (VectorStore implementation)
- **Issue:** `chromadb.EphemeralClient()` shares module-level singleton state within a Python process. Tests that all use collection name "test" accumulated data across test runs, causing `test_vector_store_query_small_collection` and `test_vector_store_metadata_retrievable` to receive stale data from prior tests and fail assertions.
- **Fix:** Added `reset_chromadb_state` autouse fixture to `tests/conftest.py` that calls `SharedSystemClient.clear_system_cache()` before each test, forcing a fresh ephemeral backend.
- **Files modified:** tests/conftest.py
- **Verification:** All 6 VectorStore tests show as XPASS when run in sequence; full test suite shows 18 passed, 7 xpassed, 4 xfailed, no regressions.
- **Committed in:** 4cc7ca8 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** The fix was necessary to make all 6 acceptance criteria tests pass. The conftest change is additive and non-breaking — all 18 previously passing Phase 1 tests continue to pass.

## Issues Encountered

- ChromaDB `reset()` method requires `allow_reset=True` in Settings, and passing different settings to `EphemeralClient` raises `ValueError` if a system already exists. Resolved by using `SharedSystemClient.clear_system_cache()` instead, which clears the module-level singleton dictionary without requiring configuration changes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- VectorStore is fully implemented and tested — Plan 04 (embedding pipeline) can use `VectorStore` with `PersistentClient` for production and `EphemeralClient` injection for tests
- Metadata fields (doc_id, filename, page_num, chunk_index, token_count) are co-located with vectors — Phase 4 query engine can build citations without a second SQLite lookup
- No blockers

---
*Phase: 02-embedding-vector-search*
*Completed: 2026-03-30*

## Self-Check: PASSED

- FOUND: src/embed/vector_store.py
- FOUND: tests/conftest.py
- FOUND: .planning/phases/02-embedding-vector-search/02-03-SUMMARY.md
- FOUND commit 4cc7ca8: feat(02-03): implement VectorStore class wrapping ChromaDB PersistentClient
