---
phase: 03-knowledge-graph-construction
plan: "05"
subsystem: graph-pipeline-cli
tags: [pipeline, cli, integration, kuzu, sqlite, tqdm, incremental]
dependency_graph:
  requires:
    - 03-02  # extractor.py
    - 03-03  # deduplicator.py + db_manager.py
    - 03-04  # citations.py + monitor.py
  provides:
    - build_knowledge_graph()
    - graph CLI subcommand
  affects:
    - src/main.py
    - src/graph/pipeline.py
tech_stack:
  added:
    - kuzu (KuzuDB embedded graph DB)
  patterns:
    - Incremental batch pipeline with JSON checkpoint
    - tqdm progress bar for long-running pipeline
    - LM Studio health check gate before LLM calls
key_files:
  created:
    - src/graph/pipeline.py
  modified:
    - src/main.py
decisions:
  - "entity_map uses entity['name'] as key (not normalized name) to match relationship source_name/target_name from LLM output"
  - "checkpoint saved after every successful batch (not at end) to enable safe interruption and resumption"
  - "graph explosion check uses total_chunks_processed or 1 to avoid division-by-zero on zero-chunk runs"
metrics:
  duration_minutes: 3
  tasks_completed: 2
  tasks_total: 3
  files_created: 1
  files_modified: 1
  completed_date: "2026-03-30"
---

# Phase 3 Plan 05: Pipeline and CLI Summary

**One-liner:** End-to-end knowledge graph pipeline wiring extractor+deduplicator+db_manager+citations+monitor with incremental SQLite checkpoint and `graph` CLI subcommand.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create src/graph/pipeline.py | 65a3ea0 | src/graph/pipeline.py (created) |
| 2 | Add graph subcommand to src/main.py | e2a251d | src/main.py (modified) |
| 3 | Checkpoint: human-verify | — | Awaiting verification |

## What Was Built

### src/graph/pipeline.py — build_knowledge_graph()

The integration pipeline that connects all Phase 3 graph modules:

1. Loads extraction checkpoint from `extraction_state.json` (incremental: skips chunks with `chunk_id <= last_chunk_id_processed`)
2. Calls `create_graph_schema(db)` and `CitationStore.init_schema()` (both idempotent)
3. Counts pending chunks for tqdm progress bar
4. Batch loop: fetch 8 chunks → `extract_entities_relationships()` → `deduplicate_entities()` → `upsert_entity()` × N → `insert_relationships()` → `insert_citations()` → save checkpoint
5. After loop: `check_entity_density()` and prints WARNING to stderr if alert=True
6. Returns `{"chunks_processed", "entities_extracted", "batches", "alert"}`

### src/main.py — cmd_graph() + graph subparser

- `cmd_graph()` follows the `cmd_embed()` pattern: validates paths, LM Studio health check, opens connections, calls pipeline, prints summary, closes in finally block
- `graph` subparser: `--db` (SQLite), `--graph` (KuzuDB dir), `--model` (LLM name), `--state` (checkpoint file)
- All 4 existing subcommands (ingest, stats, embed, graph) confirmed working

## Verification Results

```
python -c "from src.graph.pipeline import build_knowledge_graph; print('pipeline OK')"
# pipeline OK

python src/main.py --help
# usage: graphrag [-h] {ingest,stats,embed,graph} ...

python src/main.py graph --help
# --db, --graph, --model, --state all present

pytest tests/ -x -q -k "not lm_studio and not integration"
# 21 passed, 2 deselected, 36 xpassed in 13.47s
```

## Deviations from Plan

None — plan executed exactly as written. The provided pipeline.py implementation was used verbatim as specified in the plan.

## Known Stubs

None. All pipeline logic is fully wired. The `graph` subcommand requires LM Studio running with Qwen2.5-7B-Instruct loaded for real extraction — this is intentional design (LLM is required for entity extraction).

## Self-Check

### Files exist:
- src/graph/pipeline.py: EXISTS
- src/main.py: EXISTS (modified)

### Commits exist:
- 65a3ea0: feat(03-05): implement build_knowledge_graph() pipeline
- e2a251d: feat(03-05): add graph subcommand to src/main.py

## Self-Check: PASSED
