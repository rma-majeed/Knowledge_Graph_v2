---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 2
current_plan: Not started
status: unknown
stopped_at: Completed 02-01-test-infrastructure-PLAN.md
last_updated: "2026-03-30T05:09:49.536Z"
last_activity: 2026-03-30
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 4
  completed_plans: 7
  percent: 100
---

# Project State: Automotive Consulting GraphRAG Agent

**Project:** Automotive Consulting GraphRAG Agent (Local GraphRAG for automotive consulting document intelligence)
**Created:** 2026-03-28
**Current Phase:** 2

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

Phase: 02 (embedding-vector-search) — IN PROGRESS
Plan: 1 of 4 (02-01-test-infrastructure complete)
**Current Phase:** 02-embedding-vector-search
**Current Plan:** 02-02 (next)
**Progress:** [██████████] 100% (Phase 1 complete; Phase 2 Plan 1 done)

**Next Steps:**

1. Execute Phase 2 Plan 02: embedding implementation (embed_chunks, embed_query)
2. Execute Phase 2 Plan 03: VectorStore implementation
3. Execute Phase 2 Plan 04: embed pipeline (embed_all_chunks)

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
| chromadb EphemeralClient in unit tests | Avoids filesystem side effects; tests are self-contained and fast | 02-01 |
| integration mark registered in conftest.py | Suppresses PytestUnknownMarkWarning; keeps test output clean for all phases | 02-01 |
| extract_pdf() try/finally with doc.close() | Prevents fitz file handle leaks on all code paths including exceptions | 01-02 |
| Table cell text appended after plain text | Simpler than interleaving — avoids position tracking complexity | 01-02 |
| tiktoken cl100k_base encoder singleton | Caches vocab after first load (~100ms) to avoid reload per call during batch indexing of 500+ docs | 01-05 |
| Token-level sliding window (step=chunk_size-overlap) | Guarantees exact overlap count (100 tokens) between adjacent chunks for retrieval quality | 01-05 |
| sys.path bootstrap in src/main.py | Enables `python src/main.py` execution without PYTHONPATH — avoids env configuration burden | 01-06 |
| ingest_document() opens/closes its own SQLite connection | Connection-per-call isolation prevents state leaks between files in batch ingestion | 01-06 |
| PPTX slide_num normalized to page_num in pipeline layer | Uniform DB schema — downstream queries use page_num regardless of source doc type | 01-06 |

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

**Last Activity:** 2026-03-30
**Stopped At:** Completed 02-01-test-infrastructure-PLAN.md
**Files Written:** src/embed/__init__.py (created), src/embed/embedder.py (created), src/embed/vector_store.py (created), data/chroma_db/.gitkeep (created), .gitignore (created), tests/test_embedding.py (created), tests/conftest.py (modified), requirements.txt (modified)
**Git Status:** Clean (task commits 3acb895, 9c5f4b4 made)

**Phase 2 Plan 01 Complete — TDD Contract Established:**

chromadb 1.5.5 installed. src/embed/ package stubs created. 12 xfail Wave-0 test stubs in tests/test_embedding.py. pytest exits 0.

Ready for Plan 02: implement embed_chunks and embed_query.

---

**Plan 02-01 complete. chromadb installed. 12 xfail stubs. pytest tests/test_embedding.py -m "not integration" exits 0 (10 xfailed, 1 xpassed).**
