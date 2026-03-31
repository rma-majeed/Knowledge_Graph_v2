---
phase: 04-query-engine-answer-generation
plan: "02"
subsystem: query
tags: [retrieval, vector-search, graph-expansion, chromadb, kuzudb, hybrid]
dependency_graph:
  requires:
    - "04-01"  # assembler + pipeline stubs
    - "03-xx"  # graph builder (KuzuDB schema + entities)
    - "02-xx"  # embedding pipeline (ChromaDB + SQLite)
  provides:
    - vector_search
    - graph_expand
    - deduplicate_chunks
    - hybrid_retrieve
  affects:
    - "04-03"  # answer generator consumes hybrid_retrieve() output
    - "04-04"  # pipeline wiring uses hybrid_retrieve()
tech_stack:
  added: []
  patterns:
    - "1-hop KuzuDB graph traversal via _OUTGOING rel-table map"
    - "ChromaDB EphemeralClient for test isolation"
    - "str/int chunk_id normalisation for cross-source dedup"
key_files:
  created: []
  modified:
    - src/query/retriever.py
    - tests/test_query_retriever.py
decisions:
  - "Pass chroma_client instance into vector_search() rather than a path string — avoids re-opening PersistentClient in tests and gives callers control over client lifecycle"
  - "Use _OUTGOING dict replicated from db_manager.py _REL_TABLE_DDL — avoids importing private symbol while staying in sync with schema"
  - "Normalise chunk_id to str in deduplicate_chunks() — ChromaDB IDs are str, SQLite chunk_ids are int; str() on both yields consistent comparison"
  - "KuzuDB tempfile path must include a filename suffix (e.g. test.db), not be a bare directory — kuzu.Database() rejects bare directories"
metrics:
  duration_minutes: 15
  completed_date: "2026-03-31"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 2
---

# Phase 4 Plan 02: Hybrid Retriever Summary

**One-liner:** ChromaDB vector similarity search + KuzuDB 1-hop graph expansion with SQLite chunk-text hydration, combined via chunk_id-normalised deduplication.

## What Was Built

`src/query/retriever.py` implements the full hybrid retrieval pipeline:

- **`vector_search()`** — embeds query via `embed_query()`, queries a caller-supplied ChromaDB client instance, returns chunk dicts tagged `source='vector'`.
- **`_get_entities_for_chunks()`** — private helper: queries `chunk_citations` for all entities cited in the given chunk_ids (single parameterised IN query).
- **`_get_neighbors()`** — private helper: for each `(rel_table, target_type)` in `_OUTGOING[entity_type]`, runs a KuzuDB MATCH using `kuzu.Connection(db).execute(...).get_all()` (list-of-lists); tolerates missing tables/nodes via try/except.
- **`_hydrate_graph_chunks()`** — private helper: fetches `chunk_text` from SQLite `chunks` table for all chunk_ids from CitationStore results in a single IN query, merges into chunk dicts with `source='graph'`.
- **`graph_expand()`** — orchestrates entity lookup → 1-hop neighbor traversal → citation fetch (capped at `n_per_entity`) → hydration; returns [] on empty input or missing citations.
- **`deduplicate_chunks()`** — normalises chunk_id to `str` (handles ChromaDB str IDs and SQLite int IDs uniformly), preserves insertion order, first occurrence wins.
- **`hybrid_retrieve()`** — composes vector_search → graph_expand → deduplicate_chunks; vector chunks appear before graph chunks so vector source is preserved on collision.

## Tests

All 4 tests in `tests/test_query_retriever.py` converted from xfail stubs to passing tests:

| Test | Description | Result |
|------|-------------|--------|
| `test_vector_search_returns_chunks` | EphemeralClient + mock openai; checks chunk dict keys and source='vector' | PASS |
| `test_graph_expansion_finds_neighbors` | KuzuDB with Toyota→LiDAR USES edge; verifies LiDAR chunk text returned | PASS |
| `test_dedup_merged_chunks` | Pure Python; verifies order preservation, vector preference, int/str normalisation | PASS |
| `test_hybrid_retrieve_combines_sources` | BMW→Battery graph + ChromaDB; verifies both sources present, no dup chunk_ids | PASS |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] KuzuDB tempfile path must be a file path, not a directory**
- **Found during:** Task 1 (test execution)
- **Issue:** `kuzu.Database(tempfile.mkdtemp())` raises `RuntimeError: Database path cannot be a directory`
- **Fix:** Changed to `os.path.join(tempfile.mkdtemp(), "test.db")` in both KuzuDB test fixtures
- **Files modified:** tests/test_query_retriever.py
- **Commit:** 4da8d7d (included in main task commit)

### Interface Adaptation

The plan's stub signature used `chroma_path` (string) but the test requirement called for `chromadb.EphemeralClient()`. Changed `vector_search()` signature to accept a `chroma_client` instance directly instead of a path string. This is a forward-compatible improvement: callers pass their already-open client rather than having retriever.py re-open a PersistentClient internally.

## Known Stubs

None — all functions are fully implemented and wired to real data sources.

## Self-Check: PASSED

- [x] `src/query/retriever.py` exists and imports cleanly
- [x] Commit 4da8d7d present in git log
- [x] 4 tests pass: `pytest tests/test_query_retriever.py -x -q` → `4 passed`
- [x] Full suite green: `pytest tests/ -x -q -k "not lm_studio"` → `29 passed, 2 deselected, 2 xfailed, 37 xpassed`
