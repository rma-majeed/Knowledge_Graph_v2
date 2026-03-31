---
phase: 07-rag-retrieval-quality-improvements
plan: 04
subsystem: ingest/query
tags: [rag, enrichment, parent-doc, sqlite, assembler]
requirements: [RAG-03, RAG-04]

dependency_graph:
  requires:
    - 07-01 (xfail stub scaffolding)
    - 07-02 (BM25+RRF, retrieval_config.py created)
    - 07-03 (BGE reranker)
  provides:
    - src/ingest/enricher.py (enrich_chunk_context)
    - src/ingest/store.py (add_enriched_text_column, upsert_chunk_enrichment, insert_chunk_parents, get_parent_texts)
    - src/db/schema.sql (chunk_parents table)
    - src/query/assembler.py (expand_to_parent, enriched_text in truncate_to_budget)
  affects:
    - src/ingest/pipeline.py (enrichment + parent-doc hooks)
    - 07-05 (integration + feature flag tests)

tech_stack:
  added: []
  patterns:
    - ALTER TABLE idempotent column addition (add_enriched_text_column)
    - Identity parent mapping (v1: child==parent, upgradeable to true parent chunks)
    - Graceful LLM fallback (enrich_chunk_context returns original text on any exception)
    - Feature-flag-gated ingest hooks (RAG_ENABLE_ENRICHMENT, RAG_ENABLE_PARENT_DOC)

key_files:
  created:
    - src/ingest/enricher.py
  modified:
    - src/db/schema.sql
    - src/ingest/store.py
    - src/query/assembler.py
    - src/ingest/pipeline.py

decisions:
  - enriched_text added via ALTER TABLE (not in CREATE TABLE) for backward-compat with existing DBs
  - v1 parent mapping is identity (child_chunk_id == parent_chunk_id); schema supports future true-parent upgrade
  - enrich_chunk_context dispatches to LiteLLM or OpenAI client via hasattr(provider) check
  - pipeline enrichment errors are silently caught — ingest never fails due to enrichment

metrics:
  duration: "616 seconds (10m 16s)"
  completed_date: "2026-03-31"
  tasks_completed: 3
  files_modified: 5
---

# Phase 07 Plan 04: Contextual Enrichment and Parent-Document Retrieval Summary

**One-liner:** Contextual chunk enrichment (RAG-03) via LLM-generated 2-3 sentence summaries stored in enriched_text column, plus parent-document retrieval (RAG-04) via identity-mapped chunk_parents SQLite table with expand_to_parent() assembler function.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Schema additions and ChunkStore methods | 8012bdf | src/db/schema.sql, src/ingest/store.py |
| 2 | Implement enrich_chunk_context | 720aab3 | src/ingest/enricher.py |
| 3 | expand_to_parent + pipeline hooks | fda1c41 | src/query/assembler.py, src/ingest/pipeline.py |

---

## What Was Built

### RAG-03: Contextual Chunk Enrichment

**src/ingest/enricher.py** — New module with `enrich_chunk_context(chunk_text, llm_client, llm_model)`:
- Calls LLM with a system prompt requesting a 2-3 sentence context summary for the chunk
- Returns `"Context: {summary} {chunk_text}"` so both summary and original text are embedded together
- Dispatches to LiteLLM (via `_LiteLLMConfig`) or raw OpenAI client based on `hasattr(client, 'provider')`
- Graceful fallback: any LLM exception returns original `chunk_text` unchanged
- Empty/blank input returns input unchanged

**src/ingest/store.py** — Two new ChunkStore methods:
- `add_enriched_text_column()`: idempotent ALTER TABLE to add `enriched_text TEXT` to chunks (silently swallows duplicate-column errors)
- `upsert_chunk_enrichment(chunk_id, enriched_text)`: UPDATE chunks SET enriched_text for a single row

**src/db/schema.sql** — No new column in CREATE TABLE (backward-compat), chunk_parents DDL only.

**src/query/assembler.py** — `truncate_to_budget()` now uses `chunk.get("enriched_text") or chunk.get("text", "")` so enriched text is used for both passage body and token counting when set.

### RAG-04: Parent-Document Retrieval

**src/db/schema.sql** — New `chunk_parents` table:
```sql
CREATE TABLE IF NOT EXISTS chunk_parents (
    child_chunk_id  INTEGER PRIMARY KEY,
    parent_chunk_id INTEGER NOT NULL,
    parent_text     TEXT NOT NULL,
    parent_token_count INTEGER,
    FOREIGN KEY (child_chunk_id)  REFERENCES chunks(chunk_id),
    FOREIGN KEY (parent_chunk_id) REFERENCES chunks(chunk_id)
);
```

**src/ingest/store.py** — Two new ChunkStore methods:
- `insert_chunk_parents(doc_id, chunk_rows)`: inserts identity-mapping rows (v1: child==parent); skips rows with null chunk_id
- `get_parent_texts(chunk_ids)`: returns `{str(chunk_id): parent_text}` dict; handles both sqlite3.Row and tuple row formats

**src/query/assembler.py** — New `expand_to_parent(chunk, parent_texts)` function:
- Returns copy of chunk with `text` replaced by parent_text when `str(chunk_id)` found in mapping
- Returns original chunk dict unchanged when mapping is empty or key missing (no-op)

**src/ingest/pipeline.py** — Two feature-flag-gated hooks in `ingest_document()`:
- `RAG_ENABLE_ENRICHMENT=true`: calls `enrich_chunk_context()` per chunk before insert; wrapped in try/except to never block ingest
- `RAG_ENABLE_PARENT_DOC=true`: calls `store.insert_chunk_parents()` after `insert_chunks()`; fetches inserted chunk_ids from DB
- `_ingest_llm_model()` module helper reads `LLM_MODEL` env var (default: `"Qwen2.5-7B-Instruct"`)

---

## Test Results

All RAG-03 and RAG-04 stubs XPASS:

```
tests/test_retrieval_quality.py::test_enrich_chunk_context_returns_string XPASS
tests/test_retrieval_quality.py::test_enrich_chunk_context_fallback_on_error XPASS
tests/test_retrieval_quality.py::test_expand_to_parent_uses_parent_text XPASS
tests/test_retrieval_quality.py::test_expand_to_parent_no_op_when_missing XPASS
```

Full suite (no regressions): **39 passed, 8 xfailed, 48 xpassed**

---

## Deviations from Plan

None — plan executed exactly as written.

---

## Known Stubs

None. All RAG-03/RAG-04 implementations are complete and wired. Enrichment and parent-doc features are opt-in behind feature flags (default disabled), which is intentional per the plan spec — not a stub.

---

## Self-Check: PASSED

- src/ingest/enricher.py: FOUND
- src/db/schema.sql (chunk_parents): FOUND (verified via grep)
- src/ingest/store.py (add_enriched_text_column): FOUND
- src/query/assembler.py (expand_to_parent): FOUND
- src/ingest/pipeline.py (enrichment hook): FOUND
- Commits 8012bdf, 720aab3, fda1c41: FOUND (git log verified)
- Tests: 39 passed, 8 xfailed, 48 xpassed (zero regressions)
