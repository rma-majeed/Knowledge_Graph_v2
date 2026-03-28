# Features Research Summary

**Project:** Local GraphRAG Document Intelligence for Automotive Consulting
**Research date:** 2026-03-28
**Research scope:** Features dimension (table stakes, differentiators, anti-features)
**Confidence:** MEDIUM overall (training knowledge; web tools unavailable; assume Feb 2025 cutoff)

---

## Executive Summary

GraphRAG document intelligence systems for enterprise use typically implement a core workflow: ingest documents → extract entities & relationships → build knowledge graph → retrieve context → synthesize answers. For automotive consulting specifically, the key is enabling consultants to surface patterns across 15 years of institutional knowledge without leaving a browser.

**Table stakes** (must-have or users abandon): document ingestion, semantic search, answer generation with citations, chat UI, local-only inference, and incremental indexing to avoid re-indexing the entire 500–2000 document corpus.

**Differentiators** (competitive advantage in this niche): knowledge graph visualization, community detection to auto-cluster thematic work, cross-document synthesis to answer "what patterns emerge?", temporal analysis to track how approaches evolved, and entity-scoped search ("show all Tesla work").

**Anti-features** (explicitly skip): visual/image embeddings (v1 failure: 5+ min/page), OCR for scanned docs, multi-user auth, table parsing as data, LLM fine-tuning, and conversational clarification loops.

**MVP recommendation**: Prioritize ingestion + semantic search + query synthesis + chat UI + basic graph. Defer visualization, advanced community detection, and temporal analysis to Phase 3.

---

## Roadmap Implications

### Phase 1: Core Indexing & Retrieval (6–8 weeks)

**Objectives:**
- Index 500–2000 documents without crashing on 32GB RAM + 4GB VRAM
- Enable "find similar work" queries via semantic search
- Return cited answers from LLM synthesis

**Features:**
1. Document ingestion (PDF + PPTX text extraction)
2. Chunking and embedding pipeline (via LM Studio)
3. Vector search (FAISS or Qdrant)
4. Basic entity extraction + graph (NER)
5. Query → LLM synthesis + citations
6. Web chat UI (query input, answer display, sources)

**Avoids:** Visual embeddings, OCR, multi-user auth, graph visualization, community detection

**Key decision:** Text-only extraction per PROJECT.md pivot; commit to this early.

**Dependencies:** LM Studio already installed; verify OpenAI-compatible API works.

---

### Phase 2: Graph Intelligence & Metadata (4–6 weeks)

**Objectives:**
- Enable entity-scoped search ("show Tesla work")
- Surface document relationships (proposal → case study links)
- Support multi-turn chat with conversation context

**Features:**
1. Entity deduplication & linking in graph
2. Relationship types (client→project, technology→mention, date→timeline)
3. Document metadata filtering (date, format, client, type)
4. Multi-turn chat history
5. Manual verification workflow (flag tables/diagrams)
6. Query feedback loop (rate answers)

**Avoids:** Knowledge graph visualization, community detection

**Key decision:** How to deduplicate entities (string matching vs embedding similarity vs manual review)? Test on 100 documents first.

---

### Phase 3: Cross-Document Synthesis & Patterns (6–8 weeks)

**Objectives:**
- Enable "what patterns emerge?" queries across the entire corpus
- Visualize knowledge graph for consultant discovery
- Auto-cluster documents by theme

**Features:**
1. Community detection (Louvain/Leiden) to auto-cluster thematic work
2. Multi-hop graph reasoning ("show all recommendations about battery supply chains")
3. Knowledge graph visualization (interactive UI showing entities, relationships, clusters)
4. Temporal trend analysis (how approaches evolved over time)
5. Document similarity search ("find docs like this one")

**Avoids:** LLM fine-tuning, structured table extraction

**Key decision:** Which graph visualization library? (Cytoscape, Graphology, Force-Graph)

---

### Phase 4+: Polish & Integration (variable)

**Low-priority but nice-to-have:**
- Structured export (synthesis → markdown/PDF reports)
- Expert-in-the-room mode (deeper conversation context)
- Query caching and performance tuning
- Integration with enterprise document management (if needed)

---

## Why This Ordering

**Phase 1 → 2 → 3** follows dependency graph:

1. **Phase 1** unblocks everything; without working ingestion + search + answer generation, phases 2–3 have no data to operate on.
2. **Phase 2** is relatively low-risk; metadata + entity deduplication improve Phase 1's foundation without architectural changes.
3. **Phase 3** depends on Phase 2's clean graph; can't do reliable community detection or multi-hop reasoning on noisy entity data.

**Why not all-at-once?** Features have hard dependencies:
- Cross-document synthesis (Phase 3) requires entity deduplication (Phase 2)
- Graph visualization (Phase 3) requires community detection (Phase 3)
- Temporal analysis (Phase 3) requires date metadata (Phase 2)

Shipping Phase 1 early = get feedback from real consultant usage → iterate on Phases 2–3 based on actual patterns.

---

## Feature Complexity by Phase

| Phase | Hardest Problem | Estimated Effort | Risk |
|-------|-----------------|------------------|------|
| **Phase 1** | Context window management for synthesis; staying under 32GB RAM | High | Performance; may need aggressive optimization or smaller models |
| **Phase 2** | Entity deduplication (fuzzy matching is brittle); date parsing from unstructured text | Medium | Entity quality directly impacts Phase 3 reasoning |
| **Phase 3** | Multi-hop graph reasoning (LLM hallucination); community detection tuning | High | Graph reasoning can generate plausible-sounding false answers; needs validation layer |

---

## Assumptions to Validate in Phase 1

1. **LM Studio can serve both embeddings and LLM on 4GB VRAM**
   - Blocker if false → need smaller models or SSD swap (slow but functional)

2. **Consultants will interact via browser chat (not CLI/notebooks)**
   - Confirmed by PROJECT.md; build web UI first

3. **Generic NER is good enough for entity extraction**
   - Test on first 100 documents; if accuracy < 70%, invest in fine-tuning or domain-specific patterns

4. **Text-only extraction is sufficient (no OCR needed)**
   - Confirmed by PROJECT.md; trust this assumption but flag visuals in output

5. **Chunking strategy (semantic vs fixed-size) will need empirical tuning**
   - Deferred to Phase 1 implementation; test both

---

## Gaps Requiring Phase-Specific Research

- **Graph database technology choice** (Neo4j vs in-memory NetworkX vs embedded Qdrant): Defer to architecture research
- **NER model selection** (spaCy vs transformer-based): Implement both, benchmark on actual corpus
- **LLM prompt engineering for consulting queries**: Iterate post-MVP with user feedback
- **Performance profiling on actual office hardware**: Build and measure; may need 4–6 week optimization cycle in Phase 1

---

## Files Created

- `.planning/research/FEATURES.md` — Full feature analysis (table stakes, differentiators, anti-features, complexity, dependencies)

