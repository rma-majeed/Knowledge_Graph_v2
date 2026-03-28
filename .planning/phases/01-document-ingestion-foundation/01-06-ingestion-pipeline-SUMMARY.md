---
phase: 01-document-ingestion-foundation
plan: 06
subsystem: ingestion
tags: [pipeline, sqlite, pdf, pptx, tiktoken, tqdm, cli, deduplication]

# Dependency graph
requires:
  - phase: 01-document-ingestion-foundation
    provides: extract_pdf() and extract_pptx() extractors, chunk_text() chunker, ChunkStore SQLite store
provides:
  - ingest_document() end-to-end function wiring extraction + chunking + storage
  - ingest_directory() batch ingestion with tqdm progress bar
  - CLI entry point: python src/main.py ingest --path <dir> --db <db>
  - Full Phase 1 pipeline: PDF/PPTX -> text -> chunks -> SQLite
affects: [embedding, query-engine, graph-construction]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pipeline wiring: each layer (extract, chunk, store) is a pure function composed in ingest_document()"
    - "PPTX slide_num normalized to page_num before storage for uniform DB schema"
    - "CLI sys.path bootstrap via __file__.parent.parent for script-mode execution without PYTHONPATH"
    - "SHA-256 deduplication: is_document_indexed() called before any extraction work"
    - "WAL mode enabled on SQLite connection for Phase 2+ concurrent reads"

key-files:
  created:
    - src/ingest/pipeline.py
    - src/main.py
  modified:
    - tests/test_ingest_e2e.py

key-decisions:
  - "sys.path bootstrap in main.py so CLI works as 'python src/main.py' without PYTHONPATH"
  - "ingest_document opens and closes its own SQLite connection per call for simplicity and correctness"
  - "Empty page/slide text skipped before chunking to avoid zero-length chunk records"
  - "tqdm progress bar disabled when only 1 file to avoid clutter in single-file ingest"

patterns-established:
  - "Pipeline composition: extract -> normalize -> insert_document -> chunk -> insert_chunks"
  - "Return shape from ingest_document: {doc_id, chunks_inserted, skipped, filename}"

requirements-completed: [INGEST-01, INGEST-02, INGEST-03]

# Metrics
duration: 8min
completed: 2026-03-28
---

# Phase 1 Plan 06: Ingestion Pipeline Summary

**End-to-end PDF/PPTX ingestion pipeline wiring extract_pdf/extract_pptx + chunk_text + ChunkStore into ingest_document() with SHA-256 dedup, plus a CLI entry point in src/main.py**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-28T07:19:41Z
- **Completed:** 2026-03-28T07:27:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Implemented ingest_document() that routes PDF to extract_pdf() and PPTX to extract_pptx(), normalizes slide_num to page_num, and stores all chunks in SQLite with full deduplication
- Implemented ingest_directory() for batch ingestion with tqdm progress bar
- Created CLI entry point (src/main.py) with ingest and stats subcommands; works as `python src/main.py` without PYTHONPATH
- Removed all 4 xfail decorators from test_ingest_e2e.py — all 4 tests now PASS; full suite 18 passed

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement pipeline.py** - `17a0562` (feat)
2. **Task 2: Create CLI entry point src/main.py** - `ce23ded` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `src/ingest/pipeline.py` - End-to-end ingestion pipeline: ingest_document() and ingest_directory()
- `src/main.py` - CLI entry point with ingest and stats subcommands
- `tests/test_ingest_e2e.py` - Removed xfail decorators from all 4 e2e tests

## Decisions Made

- Used `sys.path.insert(0, project_root)` in main.py so CLI runs without PYTHONPATH
- Each ingest_document() call opens and closes its own SQLite connection (simpler; avoids connection state issues between files)
- Empty page/slide text (after strip) skipped to avoid zero-token chunks in DB
- tqdm progress bar disabled for single-file ingestion (disable=len(files) == 1)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added sys.path bootstrap to src/main.py**
- **Found during:** Task 2 (CLI validation)
- **Issue:** `python src/main.py` failed with ModuleNotFoundError for `src` package because project root was not on sys.path
- **Fix:** Added `sys.path.insert(0, Path(__file__).parent.parent)` at top of main.py before any src imports
- **Files modified:** src/main.py
- **Verification:** `python src/main.py ingest --path tests/fixtures/ --db /tmp/cli_test.db` exits 0 and prints "Documents ingested: 2"
- **Committed in:** ce23ded (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Required for CLI to function without environment configuration. No scope creep.

## Issues Encountered

None — implementation matched the plan contracts exactly. All 4 e2e tests passed on first run.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 1 is complete. All components are implemented and tested:
- PDF extraction (extract_pdf)
- PPTX extraction (extract_pptx)
- Text chunking (chunk_text, tiktoken cl100k_base)
- SQLite chunk store with SHA-256 deduplication (ChunkStore)
- End-to-end ingestion pipeline (ingest_document, ingest_directory)
- CLI entry point (python src/main.py ingest)

Phase 2 (Embedding) can begin. Prerequisites: SQLite DB with chunks at data/chunks.db, LM Studio serving nomic-embed-text-1.5, ChunkStore.get_chunks_for_embedding() and mark_chunks_embedded() ready.

---
*Phase: 01-document-ingestion-foundation*
*Completed: 2026-03-28*

## Self-Check: PASSED

- FOUND: src/ingest/pipeline.py
- FOUND: src/main.py
- FOUND: .planning/phases/01-document-ingestion-foundation/01-06-ingestion-pipeline-SUMMARY.md
- FOUND: commit 17a0562 (feat(01-06): implement ingest_document() and ingest_directory() pipeline)
- FOUND: commit ce23ded (feat(01-06): create CLI entry point src/main.py with ingest and stats subcommands)
