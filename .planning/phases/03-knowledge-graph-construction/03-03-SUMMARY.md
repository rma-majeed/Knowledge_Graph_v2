---
phase: 03-knowledge-graph-construction
plan: "03"
subsystem: graph
tags: [deduplication, rapidfuzz, kuzu, graph-storage, entity-normalization]
dependency_graph:
  requires: ["03-01"]
  provides: [normalize_entity_name, deduplicate_entities, create_graph_schema, upsert_entity, insert_relationships, query_entity]
  affects: ["03-02", "03-04", "03-05"]
tech_stack:
  added: [rapidfuzz.fuzz.token_set_ratio, kuzu.Database, kuzu.Connection]
  patterns: [fuzzy-deduplication, legal-suffix-normalization, kuzu-merge-upsert, type-scoped-entity-grouping]
key_files:
  created: []
  modified:
    - src/graph/deduplicator.py
    - src/graph/db_manager.py
    - tests/test_kuzu_db.py
decisions:
  - "Strip legal abbreviations (Corp, Inc, LLC, GmbH, AG, SA etc.) but NOT full words (Corporation, Limited) — preserves Toyota Motor Corporation as-is"
  - "Deduplicate within entity type only — EV/Technology and EV/Product never merge"
  - "kuzu 0.11+ uses get_all() not fetchall(); returns list-of-lists not list-of-dicts"
  - "MERGE pattern for idempotent upsert — ON CREATE SET confidence, no update on match"
metrics:
  duration: "11 minutes"
  completed_date: "2026-03-30"
  tasks_completed: 2
  files_modified: 3
requirements: [GRAPH-02, GRAPH-03]
---

# Phase 03 Plan 03: Dedup and DB Summary

Entity deduplication via RapidFuzz token_set_ratio (threshold 85) with legal suffix normalization, and KuzuDB graph storage with idempotent schema creation and MERGE-based entity upsert.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | normalize_entity_name and deduplicate_entities | ca38bc8 | src/graph/deduplicator.py |
| 2 | KuzuDB schema, upsert, query, relationships | 81535cd | src/graph/db_manager.py, tests/test_kuzu_db.py |

## What Was Built

### Task 1 — deduplicator.py (ca38bc8)

`normalize_entity_name()` applies in order:
1. Title case
2. Legal suffix removal via `_LEGAL_SUFFIX_RE` regex (Corp/Inc/LLC/GmbH/AG/SA/SARL/SAS/BV/NV/Pty/Plc + longer forms Incorporated, Limited Liability Company)
3. Strip punctuation except hyphens (`[^\w\s-]`)
4. Collapse whitespace

`deduplicate_entities()` groups by entity type, then within each type applies pairwise `fuzz.token_set_ratio()` comparison. Entities scoring >= 85 are merged; the highest-confidence occurrence is kept as canonical.

### Task 2 — db_manager.py (81535cd)

`create_graph_schema()` creates 5 node tables (OEM, Supplier, Technology, Product, Recommendation) and 10 relationship tables using `IF NOT EXISTS` DDL — fully idempotent.

`upsert_entity()` uses MERGE semantics: `MERGE (n:Type {canonical_name: '...'}) ON CREATE SET n.confidence = X` — no duplicate nodes on repeated calls.

`query_entity()` returns `{canonical_name, confidence}` dict or `None`, using `get_all()` (kuzu 0.11+ API returns list-of-lists).

`insert_relationships()` maps `(source_type, target_type, rel_type)` tuples via `_REL_TYPE_MAP` to typed relationship table names, skipping unsupported combinations silently.

## Test Results

- `tests/test_deduplicator.py`: 7 XPASS (all pass)
- `tests/test_kuzu_db.py`: 7 XPASS (all pass)
- Full suite: 21 passed, 11 xfailed, 25 xpassed — no regressions

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed kuzu QueryResult API incompatibility**
- **Found during:** Task 2 verification
- **Issue:** Plan specified `.fetchall()` for KuzuDB query results but kuzu 0.11.3 uses `.get_all()` returning list-of-lists (not list-of-dicts). Test `test_upsert_entity_no_duplicate` used `result[0]["cnt"]` which would fail with `get_all()`.
- **Fix:** Used `.get_all()` in `query_entity()` with positional row indexing. Fixed `test_kuzu_db.py` line 104 to use `get_all()` and `result[0][0]` instead of `fetchall()` and `result[0]["cnt"]`.
- **Files modified:** src/graph/db_manager.py, tests/test_kuzu_db.py
- **Commit:** 81535cd

**2. [Rule 1 - Bug] Legal suffix regex stripped "Corporation" full word**
- **Found during:** Task 1 test run (test_normalize_name_title_case XFAIL)
- **Issue:** Initial regex included "Corporation" causing `normalize_entity_name("toyota motor corporation")` to return `"Toyota Motor"` instead of `"Toyota Motor Corporation"`.
- **Fix:** Removed "Corporation" and "Limited" standalone words from the suffix regex, keeping only abbreviations (Corp, Ltd) and the compound forms (Incorporated, Limited Liability Company).
- **Files modified:** src/graph/deduplicator.py
- **Commit:** ca38bc8 (fixed inline before commit)

## Known Stubs

None. Both modules are fully implemented.

## Self-Check: PASSED
