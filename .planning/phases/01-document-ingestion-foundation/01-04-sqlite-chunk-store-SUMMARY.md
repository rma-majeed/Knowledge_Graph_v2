---
phase: 01-document-ingestion-foundation
plan: "04"
subsystem: database
tags: [sqlite, sha256, deduplication, chunk-store, ingestion]

requires:
  - phase: 01-document-ingestion-foundation
    provides: test infrastructure (conftest.py, fixtures, xfail stubs)

provides:
  - ChunkStore class wrapping sqlite3.Connection for document/chunk CRUD
  - compute_file_hash() SHA-256 file hashing for deduplication
  - src/db/schema.sql authoritative SQLite schema (documents + chunks tables)
  - Deduplication via file_hash UNIQUE constraint

affects:
  - 01-05-text-chunker (writes chunks via insert_chunks)
  - 01-06-ingestion-pipeline (uses ChunkStore as persistence layer)
  - Phase 2 embedding (reads chunks via get_chunks_for_embedding)

tech-stack:
  added: []
  patterns:
    - "ChunkStore wraps sqlite3.Connection (caller manages lifecycle)"
    - "executemany for bulk chunk insert (batch efficiency)"
    - "schema.sql as authoritative DDL with inline fallback in store.py"
    - "SHA-256 hashing in 8KB blocks (memory-safe for large files)"

key-files:
  created:
    - src/db/__init__.py
    - src/db/schema.sql
    - src/ingest/store.py
  modified:
    - tests/test_dedup.py

key-decisions:
  - "ChunkStore also exposes compute_file_hash() as instance method to support test_dedup.py calling store.compute_file_hash()"
  - "schema.sql loaded via Path(__file__) relative path with inline fallback for robustness"
  - "All write operations commit immediately (no transaction batching at store level)"

patterns-established:
  - "compute_file_hash: module-level function + instance method alias on ChunkStore"
  - "init_schema: reads schema.sql from src/db/, falls back to _INLINE_SCHEMA constant"
  - "insert_document returns lastrowid (integer doc_id) for immediate use in insert_chunks"

requirements-completed:
  - INGEST-01
  - INGEST-02
  - INGEST-03

duration: 8min
completed: 2026-03-28
---

# Phase 01 Plan 04: SQLite Chunk Store Summary

**ChunkStore class with SHA-256 deduplication, executemany bulk insert, and authoritative schema.sql using only Python stdlib (sqlite3 + hashlib)**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-28T03:52:19Z
- **Completed:** 2026-03-28T04:00:00Z
- **Tasks:** 1
- **Files modified:** 4

## Accomplishments

- Implemented `src/ingest/store.py` with ChunkStore class (init_schema, insert_document, insert_chunks, is_document_indexed, get_chunks_for_embedding, mark_chunks_embedded)
- Created `src/db/schema.sql` as authoritative DDL: documents + chunks tables with 4 indexes
- Added `compute_file_hash()` as both module-level function and ChunkStore instance method (required by test_dedup.py)
- Removed xfail markers from all 3 test_dedup.py tests — all 3 now pass; full suite: 9 passed, 9 xfailed

## Task Commits

1. **Task 1: Write schema.sql and implement ChunkStore in store.py** - `0f60fef` (feat)

## Files Created/Modified

- `src/db/__init__.py` - Package marker for db module
- `src/db/schema.sql` - Authoritative SQLite schema: documents table (doc_id, filename UNIQUE, file_hash UNIQUE, doc_type, total_pages, created_at, indexed_at), chunks table (chunk_id, doc_id FK, page_num, chunk_index, chunk_text, token_count, embedding_flag DEFAULT 0, created_at), plus 4 indexes
- `src/ingest/store.py` - ChunkStore class + compute_file_hash module function; 8KB block hashing; executemany for batch chunk insert; _INLINE_SCHEMA fallback constant
- `tests/test_dedup.py` - Removed xfail decorators from all 3 dedup tests

## Decisions Made

- Added `compute_file_hash` as both a module-level function (imported directly) and a `ChunkStore` instance method (required by test_dedup.py line 33: `store.compute_file_hash(sample_pdf_path)`). The instance method delegates to the module function.
- `init_schema()` loads `src/db/schema.sql` via `Path(__file__).parent.parent / "db" / "schema.sql"` with an `_INLINE_SCHEMA` constant fallback to ensure robustness if the file path changes.
- All write operations call `conn.commit()` immediately after each write — no transaction batching at the store level (simpler, correct for the expected insert volumes).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added compute_file_hash as ChunkStore instance method**
- **Found during:** Task 1 (reading test_dedup.py before implementation)
- **Issue:** test_dedup.py line 33 calls `store.compute_file_hash(sample_pdf_path)` as an instance method, but plan's code template only defined it as a module-level function
- **Fix:** Added `compute_file_hash(self, filepath)` instance method to ChunkStore that delegates to the module-level function
- **Files modified:** src/ingest/store.py
- **Verification:** test_file_hash_dedup passes (which calls store.compute_file_hash)
- **Committed in:** 0f60fef (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (missing method alias required by test contract)
**Impact on plan:** Essential fix — without it test_file_hash_dedup would fail with AttributeError. No scope creep.

## Issues Encountered

None. All stdlib dependencies (sqlite3, hashlib, pathlib) are available without installation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- ChunkStore ready for use in Plan 01-05 (text chunker) and Plan 01-06 (ingestion pipeline)
- Plans 01-05 and 01-06 can call `store.insert_document()` + `store.insert_chunks()` immediately
- Phase 2 embedding can read via `store.get_chunks_for_embedding()` and mark via `store.mark_chunks_embedded()`
- No blockers

---
*Phase: 01-document-ingestion-foundation*
*Completed: 2026-03-28*
