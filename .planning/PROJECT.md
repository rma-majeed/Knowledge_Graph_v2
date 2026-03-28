# Automotive Consulting GraphRAG Agent

## What This Is

A locally-run GraphRAG agent that indexes 15 years of automotive consulting documents (POVs, proposals, pitch decks, case studies) using fast text embeddings, builds a knowledge graph of entities, relationships, and communities, and exposes natural language querying through a web chat UI. Built for the Automotive Consulting team to surface cross-document insights, find similar prior work, and synthesize themes from their document archive.

## Core Value

A consultant types a question and gets a cited, synthesized answer drawn from 15 years of institutional knowledge — fast, locally, without leaving their laptop.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Document ingestion pipeline extracts text from PDF and PPTX files (no image/OCR processing)
- [ ] Indexing pipeline handles 500–2000 documents without excessive runtime (target: < 1 min/doc average)
- [ ] Local embedding model served via LM Studio OpenAI-compatible API
- [ ] Knowledge graph captures named entities, relationships, and document communities across the corpus
- [ ] Natural language query returns synthesized answer with source document references
- [ ] Web chat UI accessible from a browser for consultant use
- [ ] Full pipeline runs on 32GB RAM + 4GB VRAM without crashing or swapping
- [ ] Local LLM for answer generation served via LM Studio (no external APIs required)
- [ ] Table and diagram content flagged for manual verification in query output

### Out of Scope

- Image/visual embeddings (colqwen2.5 or equivalent) — caused 5 min/page processing in v1; text extraction is the fix
- Cloud or paid API dependencies — office laptop may be restricted; air-gap friendly required
- Multi-user auth or user management — single-user tool for the consulting team
- Structured parsing of tables/charts as data — too brittle; manual verification workflow instead
- Real-time document sync — batch indexing is sufficient

## Context

- **v1 failure**: Used `vidore/colqwen2.5-v0.2` to convert pages to images and embed visually. One page took 5+ minutes; a 50-page document took ~4 hours. The pivot to pure text extraction is the core architectural change in v2.
- **Hardware**: Restricted office laptop — 32GB RAM, 4GB VRAM. All models must fit within these constraints.
- **LM Studio**: Already installed and running as a local OpenAI-compatible API server for both embedding and LLM inference.
- **Document archive**: 500–2000 files, mix of PDF (reports, proposals) and PPTX (pitch decks, slide-based POVs).
- **Users**: Automotive consultants — not necessarily technical. The UI must be conversational and require no code.
- **Query patterns**: Find prior similar work ("what proposals did we write for EV manufacturers?"), synthesize themes ("what patterns emerge in our OEM recommendations?"), and extract frameworks ("what supply chain analysis approaches do we use?").

## Constraints

- **Hardware**: 32GB RAM + 4GB VRAM — models must be quantized/small enough to fit; no GPU-heavy approaches
- **Stack**: 100% open source, locally installable — no SaaS, no cloud calls, no paid APIs
- **Model serving**: LM Studio as the inference backend — embedding and LLM models must be compatible
- **Document formats**: Only PDF and PPTX — no Word, Excel, or email formats in scope
- **Installation**: pip install only — corporate firewall blocks conda, Docker, and system-level packages; all dependencies must be pip-installable

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Text extraction over visual embeddings | v1 proved visual embeddings (colqwen2.5) are unusable at 5+ min/page on this hardware | — Pending |
| LM Studio as model server | Already installed; provides OpenAI-compatible API for both embedding and LLM | — Pending |
| Web chat UI | Consultants are non-technical; browser chat lowers friction vs CLI/notebooks | — Pending |
| KuzuDB for graph storage | pip-installable embedded graph DB; corporate firewall blocks Neo4j and other server-based graph DBs | — Pending |
| pip-only dependency constraint | Corporate laptop firewall blocks conda, Docker, system packages — all dependencies must install via pip | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-28 after initialization*
