---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 01
current_plan: 3 (01-03-pptx-extractor)
status: unknown
stopped_at: Completed 01-04-sqlite-chunk-store-PLAN.md
last_updated: "2026-03-28T03:56:35.676Z"
last_activity: 2026-03-28
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 6
  completed_plans: 4
  percent: 67
---

# Project State: Automotive Consulting GraphRAG Agent

**Project:** Automotive Consulting GraphRAG Agent (Local GraphRAG for automotive consulting document intelligence)
**Created:** 2026-03-28
**Current Phase:** 01

---

## Project Reference

**Core Value:** A consultant types a question and gets a cited, synthesized answer drawn from 15 years of institutional knowledge — fast, locally, without leaving their laptop.

**Key Constraint:** 32GB RAM + 4GB VRAM (VRAM is the binding constraint — cannot run embedding + LLM simultaneously; must serialize models or use smaller weights).

**Hardware Boundary:** LM Studio serves both embedding and LLM inference via OpenAI-compatible API. Sequential model execution required to stay within 4GB VRAM.

**Users:** Non-technical automotive consultants; single-user tool for institutional knowledge discovery.

**Scope Lock (v1):**

- Text extraction only (no visual embeddings; v1 failure at 5+ min/page)
- PDF + PPTX only (no Word, Excel, email)
- pip install only (no Docker, conda, system packages)
- KuzuDB for graph storage (corporate firewall blocks Neo4j)
- LM Studio as model server (already running on office laptop)

---

## Current Position

Phase: 01 (document-ingestion-foundation) — EXECUTING
Plan: 5 of 6 (01-03-pptx-extractor next)
**Milestone:** Phase 1 In Progress
**Current Phase:** 01-document-ingestion-foundation
**Current Plan:** 3 (01-03-pptx-extractor)
**Progress:** [███████░░░] 67%

**Next Steps:**

1. Execute Plan 01-03 (PPTX extractor — src/ingest/pptx_extractor.py)
2. Execute Plan 01-04 (SQLite chunk store — src/ingest/store.py)
3. Execute Plans 01-05 and 01-06 (chunker and pipeline)

---

## Performance Targets (from research)

**Per-document indexing:** < 1 minute average (target: <200ms once embedded, with graph ops)
**Corpus indexing (500 docs):** < 100 seconds total
**Vector retrieval (top-10):** < 50ms
**LLM inference (2k token generation):** 5–10 seconds
**Full query (retrieve + generate):** 10–15 seconds

**VRAM constraints:**

- nomic-embed-text-1.5: ~1.5GB
- Qwen2.5 7B q4_k_m: ~3.8GB
- Sequential execution required (models must not overlap in memory)

---

## Phase Dependencies

```
Phase 1: Ingestion (foundation)
    ↓
Phase 2: Embedding (requires chunks)
    ↓
Phase 3: Knowledge Graph (requires embeddings, enables retrieval)
    ↓
Phase 4: Query Engine (requires graph + vectors + LM Studio)
    ↓
Phase 5: Chat UI (requires query engine)
```

All phases depend on LM Studio being available and functional.

---

## Critical Risks & Mitigation

| Risk | Mitigation | Phase |
|------|-----------|-------|
| **Graph explosion** — entity extraction too permissive | Entity type whitelist (OEM, supplier, tech only), confidence threshold >0.7, caps on entities/doc | Phase 1–2 |
| **Chunking strategy mismatch** — natural boundaries not preserved | Domain analysis on 20–30 sample docs, validate retrieval on test queries | Phase 1 |
| **Entity deduplication failure** — fragmented graph | Fuzzy matching (Levenshtein < 2), normalization, alias tracking | Phase 1–2 |
| **VRAM OOM during indexing** — system crashes | Conservative batch sizes (4–8 chunks), memory monitoring, checkpointing every 100 docs | Phase 1 |
| **LM Studio timeouts** — API calls fail at scale | Explicit timeout config (10s embedding, 30s LLM), max 1–2 concurrent requests, health checks | Phase 1–3 |

**Most critical:** Pitfalls 1–5 from research must be addressed in Phase 1 or system will not scale beyond 100–200 documents.

---

## Decisions Log

| Decision | Rationale | Status |
|----------|-----------|--------|
| Text extraction over visual embeddings | v1 failure: colqwen2.5 was 5+ min/page; text extraction is the pivot | Locked |
| LM Studio as model server | Already running; provides OpenAI-compatible API for both embedding + LLM | Locked |
| KuzuDB for graph storage | pip-installable embedded graph DB; corporate firewall blocks Neo4j | Locked |
| ChromaDB for vectors | Local persistent, sufficient for ≤1M vectors (2000 docs = ~500K chunks) | Locked |
| SQLite for chunks + metadata | Zero external process, native Python support, proven for this scale | Locked |
| Streamlit for UI | Best ease-of-use for non-technical consultants; rapid iteration | Locked |
| xfail(strict=False) stubs for TDD wave-0 | Keeps test intent visible and stubs automatically pass once implementation lands | 01-01 |
| extract_pdf() try/finally with doc.close() | Prevents fitz file handle leaks on all code paths including exceptions | 01-02 |
| Table cell text appended after plain text | Simpler than interleaving — avoids position tracking complexity | 01-02 |

---

## Accumulated Context

### Architecture Summary

Five independent pipelines sharing SQLite + ChromaDB + KuzuDB:

1. **Ingestion:** PDF/PPTX → Text Extraction → Chunking → SQLite Chunk Store
2. **Embedding:** Chunks → Embeddings (LM Studio) → ChromaDB
3. **Graph Construction:** Chunks → Entity Extraction (LM Studio) → Deduplication → KuzuDB
4. **Query:** Natural Language → Vector Search + Graph Traversal → Context Assembly → LLM Response
5. **UI:** Streamlit Chat Interface → API Integration

### Known Unknowns (Phase 1 Validation Required)

1. **Chunking:** Natural semantic units in automotive consulting documents (section headers? proposal boundaries?)
2. **Entity Types:** Which entities matter? (OEM, supplier, technology, regulatory, recommendation — is this whitelist complete?)
3. **Entity Density:** Baseline entities per document (estimate: 5–100; actual may vary 2x)
4. **VRAM Profile:** Actual embedding + LLM + graph overhead during indexing (conservative batch sizing may be overkill)
5. **LM Studio Stability:** Extended indexing sessions at high throughput (any crashes, timeouts, model hangs?)

### Blockers

None. All prerequisites met:

- LM Studio running with nomic-embed-text and Qwen2.5 7B loaded
- 32GB RAM + 4GB VRAM available
- Sample documents available for validation
- Python 3.10+ environment ready

---

## Session Continuity

**Last Activity:** 2026-03-28
**Stopped At:** Completed 01-04-sqlite-chunk-store-PLAN.md
**Files Written:** src/__init__.py, src/ingest/__init__.py, src/ingest/pdf_extractor.py, tests/test_extraction.py (xfail removed from 3 PDF tests)
**Git Status:** Clean (task commit e164dd3 made)

**To Resume:**

1. `cd c:/Users/2171176/Documents/Python/Knowledge_Graph_v2`
2. Execute Plan 01-03: `src/ingest/pptx_extractor.py`
3. Run `pytest tests/test_extraction.py -v` to verify PPTX tests pass

---

**Plan 01-02 complete. PDF extraction ready. 3 PDF tests pass (3 passed, 15 xfailed).**
