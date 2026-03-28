# Research Synthesis: Automotive Consulting GraphRAG Agent

**Project:** Local GraphRAG agent for automotive consulting document intelligence
**Research Date:** 2026-03-28
**Hardware Context:** 32GB RAM + 4GB VRAM laptop; LM Studio as model server
**Scope:** 500–2000 documents (PDF + PPTX); single-user, air-gapped office laptop

---

## Executive Summary

This is a **local knowledge graph RAG system** for non-technical consultants to search and synthesize insights from a historical document archive. Unlike cloud-based RAG systems, it operates entirely offline with severe hardware constraints (4GB VRAM), making it fundamentally a **resource optimization** problem as much as a feature problem.

The recommended approach adopts **LightRAG patterns**—separating ingestion, indexing, and query into independent pipelines that decouple document processing from interactive querying. Core technology stack prioritizes simplicity and zero external dependencies: **LlamaIndex + PyMuPDF for ingestion, ChromaDB for vectors, SQLite + NetworkX for knowledge graphs, Qwen2.5 7B (quantized) for LLM inference via LM Studio, and Streamlit for the UI**. This stack is proven, well-supported, and designed for local-first operation.

**The critical success factor is preventing "graph explosion"** — uncontrolled entity/relationship growth that balloons indexing time from minutes to hours and crashes the system mid-indexing. Five major pitfalls dominate the risk landscape: (1) entity extraction too permissive, (2) chunking strategy misaligned with document semantics, (3) entity deduplication failures fragmenting the graph, (4) VRAM OOM during indexing, and (5) LM Studio API latency and context window limits. These must be addressed in Phase 1–2 or the system will not scale beyond 100–200 documents.

**Confidence is MEDIUM overall.** The stack is cohesive and well-documented, but recommendations lack empirical validation on the actual automotive consulting corpus and hardware configuration. Validation must happen during Phase 1 (indexing pipeline) on a 100-document sample before scaling to the full 500–2000 document set.

---

## Key Findings by Research Domain

### Recommended Technology Stack (STACK.md)

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| **RAG Framework** | LlamaIndex | 0.10.x | Superior abstractions for local-first RAG; better than LangChain for graph construction; lower token-counting overhead |
| **Text Extraction** | PyMuPDF (fitz) | 1.23.x–1.24.x | 3–5x faster than pdfplumber; zero external dependencies; precise text boundary detection; minimal memory overhead |
| **Embedding Model** | nomic-embed-text-1.5 | 2025 | 768-dim, 200M params, fits 4GB VRAM; 8.7k context; optimized for retrieval; <10ms per chunk inference |
| **LLM Model** | Qwen2.5 7B Instruct (q4_k_m) | Latest | Fast reasoning; excellent synthesis quality; 32k context; tight fit at 3.8GB but leaves headroom |
| **Vector Store** | ChromaDB | 0.4.x | Local persistent, built-in embeddings interface, sufficient for ≤1M vectors (2000 docs = ~500K chunks); upgrade to FAISS only if >50k docs shows latency issues |
| **Graph Store** | SQLite + NetworkX | 3.2.x | Zero external process; NetworkX has all needed algorithms (community detection, DFS, shortest path); no Docker/JVM; upgrade path to Neo4j if needed |
| **Model Server** | LM Studio | 0.2.x+ | OpenAI-compatible API for both embeddings and LLM; only external dependency for local inference |
| **Web UI** | Streamlit | 1.28.x | Best ease-of-use for non-technical consultants; rapid iteration; native chat components; lower effort than Chainlit |

**Supporting libraries:** openai (1.3.x–1.5.x), pydantic (2.x), requests (2.31.x+), numpy (1.24.x+), tqdm (4.66.x+), python-dotenv (1.0.x).

**DO NOT use:** e5-large-v2 (exceeds 4GB), ColQwen visual embeddings (5+ min/page from v1 failure), 13B+ LLM models (exceeds VRAM), Pinecone (requires cloud API), Neo4j Community (overkill for this scale, adds Docker complexity).

**Installation validation before Phase 1:**
- LM Studio running and reachable via `http://localhost:1234/v1/models`
- Embedding model fit confirmed on 4GB VRAM
- Embedding inference latency <10ms per chunk measured on target hardware
- Python 3.10+ environment with all dependencies installed

### Feature Landscape (FEATURES.md)

**Table Stakes for v1** (must-have to avoid product feeling incomplete):
1. **Document ingestion** (PDF + PPTX text extraction) — Medium complexity, 1–2 weeks
2. **Semantic search** (embeddings via LM Studio) — Medium complexity, 1–2 weeks
3. **Query answering with citations** (retrieve + synthesize via LLM) — High complexity, 2–3 weeks
4. **Chat UI** (query input, answer display, source citations) — Low complexity, 1 week
5. **Basic entity extraction + graph** (enables future differentiators) — Medium complexity, 2 weeks
6. **Document metadata extraction** (title, date, format) — Medium complexity, 3–5 days
7. **Incremental indexing** (add new docs without re-indexing corpus) — Medium complexity, 1 week

**Differentiators for future phases** (Phase 3+, valuable but not v1-critical):
- Knowledge graph visualization (medium-high complexity)
- Community/cluster detection (high complexity, requires tuning)
- Cross-document synthesis queries (high complexity, multi-hop reasoning)
- Entity-scoped search (medium complexity, NER quality dependent)
- Temporal analysis (medium complexity, date filtering + trend detection)
- Manual verification workflow (low complexity, simple UI flag)
- Query feedback loop (low complexity, rating UI)

**Explicitly skip in v1:** Visual/image embeddings, OCR for scanned documents, multi-user auth, real-time sync, structured table extraction, LLM fine-tuning, conversational clarification loops.

### Architecture Patterns (ARCHITECTURE.md)

**Five independent pipelines** sharing common storage:

1. **Ingestion Pipeline** → Files → Text Extraction → Chunking → SQLite Chunk Store
2. **Indexing Pipeline** → Chunks → Embeddings (ChromaDB) + Entity/Relationship Extraction (LLM) → Graph Construction (SQLite + NetworkX)
3. **Query Pipeline** → Natural Language → Graph Traversal + Vector Search → Context Assembly → LLM Response
4. **Storage Layer** → SQLite (chunks + metadata + graph), ChromaDB (vectors), NetworkX (in-memory graph cache)
5. **API Layer** → FastAPI server with `/chat` and `/ingest` endpoints; simple threading for background indexing

**Key architectural decisions:**
- **Batch processing (not streaming):** Upload files → trigger indexing job → wait for completion. Simpler resource management, matches office workflow.
- **Manual upload (not file watcher):** Explicit user control via UI, no false positives, easier debugging.
- **Decouple ingestion from querying:** Consultant can ask questions while background indexing runs (requires persistent snapshots).
- **Chunking strategy:** 1024 tokens with 200-token overlap (domain-specific; validate on actual documents).
- **Graph persistence:** Checkpoint every 50–100 documents, enable resume on crash.

**Build order is critical:**
- **Phase 1:** Chunk Store (SQLite) + Text Extraction + Upload API
- **Phase 2:** Vector DB + Embedding Gen + Entity Extraction + Graph DB
- **Phase 3:** Graph Search + LLM Answer Gen + Chat API
- **Phase 4:** Web UI
- **Phase 5+:** Community Detection, Entity Disambiguation

### Critical Pitfalls (PITFALLS.md)

| Pitfall | Risk Level | Prevention Strategy | Phase |
|---------|-----------|-------------------|-------|
| **1. Graph Explosion** — uncontrolled entity/relationship growth | CRITICAL | Entity type whitelist (OEM, supplier, tech, client only; no dates/quantities), relationship confidence threshold >0.7, caps on entities per doc (50–100), relationship count limits (20 per entity), monitoring for entity/doc ratio > 20 | 1–2 |
| **2. Chunking Strategy Mismatch** | CRITICAL | Domain analysis on 20–30 sample documents, identify natural boundaries (section headers), target 300–600 tokens per chunk (12–24 token overlap), document-specific rules (PDF at sections, PPTX per slide), validation: test retrieval on 20–30 sample queries; >80% precision required | 1 |
| **3. Entity Deduplication Failure** — same entity, different names → fragmented graph | CRITICAL | Post-extraction normalization (remove legal suffixes, expand acronyms, title case standardization), fuzzy matching (Levenshtein < 2), coreference resolution (at minimum within-chunk), canonical form storage with alias tracking | 1–2 |
| **4. VRAM OOM** — model doesn't fit, system crashes mid-indexing | CRITICAL | Model fit validation on 4GB machine BEFORE Phase 1 (non-negotiable), conservative batch sizes (4–8 chunks max, not 32), memory monitoring during indexing, checkpointing every 100 docs with resume capability, quantization standards (GGUF Q4_K_M) | 0–1 |
| **5. LM Studio API Timeouts & Limits** | CRITICAL | Explicit timeout config (embedding 10s, LLM 30s), max 1–2 concurrent requests (sequential better than parallel for single-process LM Studio), context window validation (use 6K of claimed 8K), error handling + graceful degradation, heartbeat health check | 1–3 |
| **6. PPTX Extraction Gaps** — bullets, tables, speaker notes missed | HIGH | Robust PPTX parsing (title, body, bullets with hierarchy, tables, speaker notes, shape text), structured output preserving formatting, validation on 10–20 PPTX decks (manual spot check) | 1 |
| **7. Incremental Indexing Not Implemented** — re-index entire corpus per new doc | HIGH | Graph persistence after each doc, incremental entity deduplication (O(n) not O(corpus)), deferred community detection (lazy recomputation on first query), batch optimization if multiple docs added at once | 2 |
| **8. Community Detection Misconfiguration** — too many or too few communities | MEDIUM | Understand graph structure first (measure node count, edge density, degree distribution), tune resolution parameter (target 20–50 communities for 500 docs, ~10K entities), stability validation (run 5 times, compare results) | 2–3 |
| **9. LLM Hallucination in Graph Synthesis** — LLM invents connections not in graph | MEDIUM | Strict grounding in prompts (enforce graph-based answers only), chain-of-thought verification (force LLM to show reasoning), citation enforcement (every factual claim must cite source), confidence scoring (HIGH/LOW based on source count + independence) | 3 |

**Most critical to address in Phase 1:** Pitfalls 1, 2, 3, 4, 5. If these fail, system will not scale beyond 100–200 documents. Pitfalls 6, 7 are high-priority for Phase 2. Pitfalls 8, 9 can be deferred to Phase 3+.

---

## Performance Targets

Based on hardware constraints and estimated corpus size:

| Operation | Target | Notes |
|-----------|--------|-------|
| Embed 1 chunk (512 tokens) | <10ms | nomic-embed-text-1.5 typical; if >20ms, investigate model size or batch efficiency |
| Index 1 document (~10 chunks avg) | <200ms | Extraction + embedding + graph ops combined |
| Index corpus (500 docs) | <100 seconds | ~200ms/doc average; if exceeds this, check entity explosion |
| Vector retrieval (top-10) | <50ms | ChromaDB, <10k vectors; if >100ms, consider FAISS |
| LLM inference (2k token generation) | 5–10 seconds | Qwen2.5 7B q4_k_m typical |
| Full query (retrieve + generate) | 10–15 seconds | User-acceptable latency for chat interface |

If Phase 1 doesn't meet targets, investigate root causes: chunking size too large (slows embedding), entity extraction too permissive (slows graph ops), batch size too large (VRAM pressure), or model quantization issues.

---

## Implications for Roadmap

### Suggested Phase Structure

**Phase 1: Ingestion & Indexing Foundation (Weeks 1–4)**

Components:
- Chunk Store (SQLite schema: documents, chunks tables)
- Text Extraction (PyMuPDF for PDF, python-pptx for PPTX)
- Document Upload API (`POST /ingest`)
- Vector DB (ChromaDB initialization + persistence)
- Embedding Generation (LM Studio OpenAI API integration)
- Entity Extraction (LLM-based, with prompt engineering)
- Graph DB (SQLite schema: entities, relationships, communities)

Success criteria:
- Index 100-document sample in <30 seconds
- Entity count <10K (ratio <100 entities/doc)
- VRAM peak <3.5GB (leave 500MB margin)
- Chunking quality validated on 20 test queries (>80% retrieval precision)
- Entity extraction accuracy acceptable to team (>70% quality threshold)

Validation:
- Measure chunking quality (natural boundaries preserved?)
- Detect entity explosion warning signs (entity count growth, entity/doc ratio)
- Monitor VRAM during indexing (if spike at any point, investigate)
- Manual spot-check: 10 documents, verify entities make sense

Research needed:
- Empirical chunking analysis on automotive consulting PDFs (what are natural boundaries?)
- Entity extraction prompt effectiveness (does generic prompt work, or need domain examples?)
- Baseline entity density estimate (how many unique entities per document?)

---

**Phase 2: Query System & Chat (Weeks 5–6)**

Components:
- Graph Search (vector similarity + entity-based hybrid traversal)
- Context Assembly (rank and combine top-K chunks + related entities)
- LLM Answer Generation (prompt with context, enforce grounding)
- Citation Extraction (map retrieved chunks back to source documents + pages)
- Chat API (`POST /chat`)
- Streamlit UI (query input, answer display, source citations)

Success criteria:
- Query latency <15 seconds for typical consultant questions
- Retrieval precision >80% on 20 test queries (correct document retrieved)
- Answer accuracy acceptable (citations match content, no hallucinations)
- No VRAM spikes during query execution

Validation:
- User testing with realistic consultant queries
- Citation verification (spot-check: do cited sources actually contain the answer?)
- Hallucination detection (does LLM stay grounded in graph context?)

Research needed:
- Graph traversal depth optimization (how many hops to capture needed context?)
- Context assembly ranking (how to weight vector similarity vs entity relationships?)
- LLM prompt engineering (what grounding constraints prevent hallucination?)

---

**Phase 3: Graph Quality & Robustness (Weeks 7–8)**

Components:
- Incremental indexing (checkpoints, resume, delta processing)
- Advanced entity deduplication (fuzzy matching, coreference resolution)
- Community Detection (Louvain algorithm, resolution tuning)
- LM Studio monitoring (latency tracking, timeout handling)
- Graph statistics monitoring (entity growth, relationship counts)

Success criteria:
- Add new document in <30 seconds (without re-indexing entire corpus)
- System stable on 2000 documents (no crashes, latency acceptable)
- Community detection produces 20–50 meaningful clusters
- Graph operations (shortest path, traversal) <500ms even at 10K+ entities

Validation:
- Stress test on full 500–2000 document corpus
- Monitor query performance at scale (does latency increase linearly?)
- Graph structure validation (community modularity >0.4, stable across runs)

Research needed:
- Graph scaling behavior (does entity count grow as O(n)? Graph operations complexity?)
- Community detection tuning (how to set resolution for automotive documents?)
- LM Studio stability at high load (any crashes, timeouts, or model hangs?)

---

**Phase 4: UI Polish & User Feedback (Weeks 9–10)**

Components:
- Streamlit chat history and session management
- Document filtering UI (by date, type, metadata)
- Source citation UX (clickable links, snippet highlighting)
- Query feedback loop (user ratings, low-confidence answer flagging)
- Status dashboard (indexing progress, document count, health metrics)

Success criteria:
- Non-technical consultant can use system without training
- Positive user feedback on citation format and UI layout
- System adopted in pilot (usage metrics indicate actual use)

Validation:
- User interviews (what works? what's confusing?)
- Adoption metrics (how often are consultants using it?)
- Citation accuracy feedback (do users trust the sources?)

Research needed:
- Consultant workflow validation (how do they actually use the system?)
- Citation format preferences (inline, sidebar, link format?)
- Document summary depth (title only or more context?)

---

**Phase 5+ (Future Optimization)**

Optional features for v2+:
- Knowledge graph visualization (network diagram)
- Cross-document synthesis queries (multi-hop reasoning)
- Temporal trend analysis (how did approach evolve over time?)
- Structured export (markdown reports from answers)

---

### Research Flags

**Phases needing deeper research during planning:**
- **Phase 1:** Chunking strategy validation on automotive consulting PDFs (may need custom splitting logic for proposal sections)
- **Phase 1:** Entity extraction prompt effectiveness (baseline LLM performance on automotive domain)
- **Phase 2:** Entity extraction quality on automotive domain (accuracy threshold for adoption)
- **Phase 3:** Graph scaling behavior (does entity count grow exponentially? Community detection speed at 10K+ entities?)
- **Phase 4:** Consultant workflow and UX preferences (how do they want to interact with the system?)

**Standard patterns (skip deep research):**
- Vector DB selection (ChromaDB well-documented, mature)
- SQLite schema design (standard relational patterns)
- FastAPI endpoint design (well-known REST conventions)
- Streamlit UI (extensive public examples and documentation)
- LLamaIndex integration (official examples and tutorials available)

### Critical Questions Before Building

1. **Chunking:** What is the natural semantic unit in automotive consulting documents? Are there section headers, structured formats? Answer this on 20–30 sample docs before Phase 1.
2. **Entity Types:** Which entities matter for consultants? (e.g., OEM, supplier, technology, regulatory body, recommendation). Define a whitelist before Phase 1 entity extraction.
3. **Entity Quality:** At what accuracy threshold is entity extraction acceptable? Can you tolerate 10% noise? 50% noise? This drives Phase 1 validation success criteria.
4. **Incremental Use:** Will consultants batch-add documents weekly, or continuously add one at a time? If continuous, Phase 2 must prioritize incremental indexing.
5. **Graph Size:** Is the 5K–10K entity estimate reasonable? A 100-document pilot will validate; if actual is 2x or 0.5x estimate, Phase 2–3 timelines change.
6. **Consultant Adoption:** Are they willing to trust local LLM inference, or do they expect cloud-quality answers? This affects Phase 4 UI design and confidence scoring.

---

## Confidence Assessment

| Area | Confidence | Basis | Gaps |
|------|-----------|-------|------|
| **Stack** | MEDIUM-HIGH | Well-established technologies with production use cases; model fit on 4GB VRAM unvalidated until tested on target hardware | Hardware validation needed before Phase 1; embedding inference latency unconfirmed |
| **Features** | MEDIUM | Feature landscape clear and prioritized; effort estimates may underestimate (graph construction more complex than it appears) | Entity extraction quality on automotive domain not validated; actual feature complexity TBD in Phase 1 |
| **Architecture** | HIGH | LightRAG + GraphRAG patterns well-documented in research; component boundaries and dependencies clear | Incremental indexing complexity may exceed estimates; LM Studio stability during extended sessions unconfirmed |
| **Pitfalls** | MEDIUM-HIGH | Critical pitfalls (graph explosion, VRAM OOM) well-known in graph RAG literature; documented mitigation strategies exist | Implementation-specific risks unknown until Phase 1; severity of PPTX extraction gaps depends on actual corpus analysis |
| **Performance Targets** | MEDIUM | Targets based on hardware specs + literature; <15 sec query latency achievable but not guaranteed without tuning | Real-world VRAM pressure and latency require Phase 1 empirical validation; may need more aggressive optimization |

**Overall:** Confidence is MEDIUM. The research is thorough and the recommended path is sound, but success depends heavily on empirical validation during Phase 1. Key unknowns are (1) entity extraction quality on automotive consulting language, (2) graph scaling behavior with real data, (3) LM Studio stability during extended indexing, and (4) actual consultant workflows and adoption patterns.

---

## Dependencies & Prerequisites

Before starting Phase 1:

- **LM Studio 0.2.x+ installed and running** with nomic-embed-text-1.5 and Qwen2.5 7B Instruct loaded
- **32GB RAM, 4GB VRAM laptop** available for development and testing
- **Sample of 20–30 automotive consulting documents** (PDF + PPTX) for validation
- **Python 3.10+ environment** with pip/uv/pdm for package management
- **1–2 week contingency buffer** for model fitting validation and unexpected compatibility issues

---

## Sources & References

**Research documents synthesized:**
- STACK.md — Technology stack recommendations, tested configurations, version pinning
- FEATURES.md — Feature landscape, MVP prioritization, complexity estimates
- ARCHITECTURE.md — Pipeline design, component boundaries, data flow, build order
- PITFALLS.md — Critical risks, prevention strategies, detection methods, phase warnings

**Key reference systems:**
- LightRAG architecture (local-first graph construction, adaptive entity descriptions)
- Microsoft GraphRAG (entity extraction → relationships → community detection pipeline)
- LLamaIndex documentation (RAG framework abstractions, local LLM integration patterns)
- ChromaDB & NetworkX (vector and graph library best practices)
- Constrained inference research (4GB VRAM optimization, quantization strategies)

---

## Next Steps

Recommended validation sequence before Phase 1 coding starts:

1. **Validate chunking strategy** on 20–30 sample documents (manual analysis, identify natural boundaries)
2. **Profile LM Studio** on target hardware: embedding latency (<10ms?), VRAM usage peak (< 3.5GB?), stability under load
3. **Define entity type whitelist** for automotive consulting (OEM, supplier, technology, regulatory, financial metrics, etc.)
4. **Estimate entity explosion baseline** by manually analyzing 10 documents (expected entity density per document)
5. **Test entity extraction prompt** on sample documents (baseline accuracy before building Phase 1)

Once validation complete, roadmap creation can proceed with confidence. Plan for empirical validation throughout Phase 1–2; adjust Phases 3–4 based on findings.

---

**Roadmap ready for creation. All research complete. Critical assumptions documented. Risks mitigated through structured phase-by-phase validation.**
