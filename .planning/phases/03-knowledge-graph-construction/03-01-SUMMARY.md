---
phase: 03-knowledge-graph-construction
plan: 01
subsystem: testing
tags: [kuzu, rapidfuzz, pytest, xfail, tdd, knowledge-graph, graph-db]

# Dependency graph
requires:
  - phase: 02-embedding-vector-search
    provides: ChromaDB vector store and embedding pipeline (Phase 2)
provides:
  - src/graph package with 5 NotImplementedError stub modules (extractor, deduplicator, db_manager, citations, monitor)
  - 4 test files with 25 xfail stubs covering GRAPH-01 through GRAPH-04
  - kuzu>=0.11.3 and rapidfuzz>=3.14.0 installed and in requirements.txt
  - data/kuzu_db/ directory placeholder (gitignored, .gitkeep tracked)
  - lm_studio pytest marker registered in conftest.py
affects: [03-02-entity-extraction, 03-03-graph-deduplication-storage, 03-04-citation-pipeline, 03-05-graph-pipeline-integration]

# Tech tracking
tech-stack:
  added: [kuzu>=0.11.3, rapidfuzz>=3.14.0]
  patterns: [xfail stubs with imports inside test body (ImportError -> xfail not collection error), NotImplementedError source stubs]

key-files:
  created:
    - src/graph/__init__.py
    - src/graph/extractor.py
    - src/graph/deduplicator.py
    - src/graph/db_manager.py
    - src/graph/citations.py
    - src/graph/monitor.py
    - tests/test_graph_extraction.py
    - tests/test_deduplicator.py
    - tests/test_kuzu_db.py
    - tests/test_citations.py
    - data/kuzu_db/.gitkeep
  modified:
    - requirements.txt
    - .gitignore
    - tests/conftest.py

key-decisions:
  - "Imports inside test bodies (not module level) so ImportError triggers xfail, not collection error — matches plan specification"
  - "!data/kuzu_db/.gitkeep exception added to .gitignore to track directory placeholder (mirrors chroma_db pattern)"
  - "lm_studio marker registered in conftest.py alongside existing integration marker for test filtering"

patterns-established:
  - "src/graph stubs: NotImplementedError on all functions/methods, public API in module docstring"
  - "xfail pattern: @pytest.mark.xfail(strict=False, reason='not implemented yet') with imports inside test body"
  - "lm_studio integration tests: @pytest.mark.lm_studio + @pytest.mark.xfail double-decorated"

requirements-completed: [GRAPH-01, GRAPH-02, GRAPH-03, GRAPH-04]

# Metrics
duration: 12min
completed: 2026-03-30
---

# Phase 3 Plan 01: Test Infrastructure Summary

**Wave 0 test scaffold for Phase 3: src/graph package with 5 NotImplementedError stubs, 25 xfail test stubs across 4 files, kuzu + rapidfuzz installed**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-03-30T07:04:25Z
- **Completed:** 2026-03-30T07:15:41Z
- **Tasks:** 2
- **Files modified:** 13

## Accomplishments

- Installed kuzu 0.11.3 and rapidfuzz 3.14.3; added both to requirements.txt
- Created src/graph package with 5 stub modules (extractor, deduplicator, db_manager, citations, monitor) — all raise NotImplementedError
- Created 4 test files with 25 xfail stubs covering GRAPH-01 (extraction), GRAPH-02 (deduplication), GRAPH-03 (KuzuDB), GRAPH-04 (citations)
- All 25 stubs report XFAIL, 0 errors; 21 prior Phase 1+2 tests still pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Install kuzu+rapidfuzz and create src/graph package stubs** - `78e2936` (feat)
2. **Task 2: Create xfail test stubs for all graph test files** - `bafbf4e` (test)

## Files Created/Modified

- `requirements.txt` - Added kuzu>=0.11.3 and rapidfuzz>=3.14.0
- `.gitignore` - Added data/kuzu_db/ with !data/kuzu_db/.gitkeep exception
- `tests/conftest.py` - Added lm_studio pytest marker registration
- `src/graph/__init__.py` - Package marker for knowledge graph construction package
- `src/graph/extractor.py` - NotImplementedError stub with ENTITY_TYPES, CONFIDENCE_THRESHOLD, BATCH_SIZE constants
- `src/graph/deduplicator.py` - NotImplementedError stub with SIMILARITY_THRESHOLD constant
- `src/graph/db_manager.py` - NotImplementedError stub with 4 function signatures
- `src/graph/citations.py` - NotImplementedError stub with CitationStore class (3 methods)
- `src/graph/monitor.py` - NotImplementedError stub with MAX_ENTITIES_PER_DOC, MAX_TOTAL_ENTITIES constants
- `data/kuzu_db/.gitkeep` - Directory placeholder (gitignored, .gitkeep exception)
- `tests/test_graph_extraction.py` - 7 xfail stubs for GRAPH-01 (6 unit + 1 lm_studio integration)
- `tests/test_deduplicator.py` - 7 xfail stubs for GRAPH-02 (all unit)
- `tests/test_kuzu_db.py` - 7 xfail stubs for GRAPH-03 (all unit using tmp_path KuzuDB)
- `tests/test_citations.py` - 5 xfail stubs for GRAPH-04 (all unit using tmp_db_conn SQLite)

## Decisions Made

- Imports placed inside test bodies (not module level) so ImportError from NotImplementedError stubs triggers xfail, not collection error
- Added `!data/kuzu_db/.gitkeep` exception in .gitignore to track directory placeholder, mirroring the chroma_db pattern already in use
- lm_studio marker registered in conftest.py alongside existing `integration` marker for clean test filtering

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Git refused to add `data/kuzu_db/.gitkeep` because the directory was listed in .gitignore without a negation rule. Fixed by adding `!data/kuzu_db/.gitkeep` exception to .gitignore (same pattern as chroma_db), then using `git add -f`. This was anticipated by the chroma_db precedent.

## Known Stubs

All stubs are intentional Wave 0 placeholders:

| File | Stub | Implementing Plan |
|------|------|-------------------|
| src/graph/extractor.py | extract_entities_relationships() | 03-02 |
| src/graph/deduplicator.py | normalize_entity_name(), deduplicate_entities() | 03-03 |
| src/graph/db_manager.py | create_graph_schema(), upsert_entity(), insert_relationships(), query_entity() | 03-03 |
| src/graph/citations.py | CitationStore.init_schema(), .insert_citations(), .get_chunks_for_entity() | 03-04 |
| src/graph/monitor.py | check_entity_density() | 03-04 |

These stubs are intentional scaffolding — their corresponding tests will auto-pass once implementations land in plans 03-02 through 03-04.

## Next Phase Readiness

- Phase 3 Wave 0 scaffold complete — ready for plan 03-02 (entity extraction implementation)
- All xfail stubs will auto-pass once implementations land (strict=False)
- src/graph package importable from all test files
- KuzuDB data directory created and gitignored

---
*Phase: 03-knowledge-graph-construction*
*Completed: 2026-03-30*
