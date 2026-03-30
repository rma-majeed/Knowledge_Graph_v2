---
phase: 02-embedding-vector-search
plan: "04"
subsystem: embedding-pipeline
tags: [embedding, pipeline, sqlite, chromadb, tdd, cli]
dependency_graph:
  requires:
    - "02-02"  # embedder.py (embed_chunks)
    - "02-03"  # vector_store.py (VectorStore)
  provides:
    - "src/embed/pipeline.py"
    - "src/ingest/store.py:get_chunks_with_metadata_for_embedding"
    - "src/main.py:embed subcommand"
  affects:
    - "Phase 3: Knowledge Graph (reads from same SQLite)"
tech_stack:
  added: []
  patterns:
    - "TDD with xfail stubs in test_embedding.py"
    - "VectorStore bypass via __new__ for testability (vs._collection = collection)"
    - "tqdm progress bar with pre-counted pending_count for accurate total"
    - "Lazy openai.OpenAI import inside embed_all_chunks for fast test mocking"
key_files:
  created:
    - src/embed/pipeline.py
  modified:
    - src/ingest/store.py
    - src/main.py
    - tests/test_dedup.py
decisions:
  - "VectorStore bypassed via __new__ to accept externally-provided chroma_client, avoiding double-init"
  - "pending_count checked before loop to return early with zero API calls when corpus is fully embedded"
  - "embed_all_chunks returns dict{chunks_embedded, batches} for CLI reporting"
metrics:
  duration: "7m 31s"
  completed_date: "2026-03-30"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 3
requirements_satisfied:
  - EMBED-01
  - EMBED-02
  - EMBED-03
---

# Phase 02 Plan 04: Embedding Pipeline Summary

Full embedding pipeline wired end-to-end: SQLite incremental reader + LM Studio embedder + ChromaDB upsert + SQLite flag update, with embed CLI subcommand.

## What Was Built

### Task 1: get_chunks_with_metadata_for_embedding() (ChunkStore)

Added `get_chunks_with_metadata_for_embedding(batch_size=8)` method to `ChunkStore` in `src/ingest/store.py`. JOINs `chunks` with `documents` to return 7 columns needed by the embedding pipeline: `chunk_id`, `chunk_text`, `doc_id`, `filename`, `page_num`, `chunk_index`, `token_count`. Filters `WHERE embedding_flag = 0` and respects `batch_size` limit. Added 3 unit tests to `tests/test_dedup.py`.

### Task 2: src/embed/pipeline.py + embed CLI subcommand

Created `src/embed/pipeline.py` with:
- `check_lm_studio(host, port)` — httpx GET /v1/models health check, returns bool
- `embed_all_chunks(conn, chroma_client, model, openai_client, batch_size)` — full loop: reads pending chunks in batches, calls `embed_chunks()`, upserts via `VectorStore`, marks `embedding_flag=1`. Returns `{chunks_embedded, batches}`.

Added `cmd_embed()` function and `embed` subparser to `src/main.py`:
- `python src/main.py embed --db data/chunks.db --chroma data/chroma_db --model nomic-embed-text-v1.5`
- Exits 1 with clear error message when LM Studio is unreachable (no hang)

## Verification Results

```
pytest tests/test_embedding.py -q -m "not integration"
11 xpassed, 1 deselected
```

```
pytest tests/ -q -m "not integration"
21 passed, 11 xpassed, 1 deselected
```

```
python src/main.py embed --help
usage: graphrag embed [-h] [--db DB] [--chroma CHROMA] [--model MODEL]
```

## Deviations from Plan

None — plan executed exactly as written.

The xfail stubs in `test_embedding.py` now show `xpassed` (tests pass). The xfail markers remain in place (strict=False) to preserve test intent documentation without breaking the suite.

## Known Stubs

None. All pipeline components are wired to real data sources.

## Self-Check: PASSED

Files verified:
- src/embed/pipeline.py: FOUND
- src/ingest/store.py (get_chunks_with_metadata_for_embedding): FOUND
- src/main.py (cmd_embed, p_embed): FOUND

Commits verified:
- d339227: feat(02-04): add get_chunks_with_metadata_for_embedding() to ChunkStore — FOUND
- 467bacf: feat(02-04): implement embed pipeline and CLI subcommand — FOUND
