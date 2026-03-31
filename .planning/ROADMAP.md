# Automotive Consulting GraphRAG Agent — Project Roadmap

**Project:** Automotive Consulting GraphRAG Agent
**Created:** 2026-03-28
**Granularity:** Standard (5-8 phases)
**Status:** Phase 6 complete — Phase 7 planned

---

## Phases

- [x] **Phase 1: Document Ingestion Foundation** - Extract text from PDF and PPTX files into a chunk store
- [x] **Phase 2: Embedding & Vector Search** - Generate and store embeddings for semantic retrieval (completed 2026-03-30)
- [x] **Phase 3: Knowledge Graph Construction** - Extract entities, relationships, and build knowledge graph (completed 2026-03-30)
- [x] **Phase 4: Query Engine & Answer Generation** - Retrieve, synthesize, and cite answers to user questions (completed 2026-03-31)
- [x] **Phase 5: Chat UI & Session Management** - Streamlit interface for consultants to interact with the system (completed 2026-03-31)
- [x] **Phase 6: Multi-Provider LLM & Embedding Configuration** - Make LLM and embedding providers configurable via .env file using LiteLLM adapter (LM Studio, Ollama, Gemini, OpenAI, Anthropic) (completed 2026-03-31)
- [ ] **Phase 7: RAG Retrieval Quality Improvements** - Improve retrieval precision and recall through BM25 hybrid search with RRF fusion, BGE cross-encoder reranking, contextual chunk enrichment, and parent-document retrieval

---

## Phase Details

### Phase 1: Document Ingestion Foundation

**Goal:** Consultant can upload PDF and PPTX documents; the system extracts text and stores chunks with metadata ready for embedding.

**Depends on:** Nothing (foundation phase)

**Requirements:** INGEST-01, INGEST-02, INGEST-03

**Success Criteria** (what must be TRUE):
1. User can upload a PDF file and the system extracts all text content (including tables and diagrams) with page numbers preserved
2. User can upload a PPTX file and the system extracts slide text, speaker notes, and table cells with slide numbers preserved
3. System chunks extracted text into segments suitable for embedding (validated via manual inspection of 10 documents)
4. Chunk metadata (source document, page/slide number, chunk offset) is stored alongside chunk text
5. System indexes 100-document sample in under 30 seconds (establishes performance baseline)

**Plans:** 6 plans

Plans:
- [x] 01-PLAN-01-test-infrastructure.md — pytest infrastructure, synthetic fixtures, dependency install, xfail stubs
- [x] 01-PLAN-02-pdf-extractor.md — PDF text extraction with PyMuPDF (Wave 1, parallel with Plan 03)
- [x] 01-PLAN-03-pptx-extractor.md — PPTX text + notes + tables extraction with python-pptx (Wave 1, parallel with Plan 02)
- [x] 01-PLAN-04-sqlite-chunk-store.md — SQLite schema, ChunkStore class, SHA-256 deduplication (Wave 2, parallel with Plan 05)
- [x] 01-PLAN-05-text-chunker.md — 512-token fixed-size chunking with 100-token overlap via tiktoken (Wave 2, parallel with Plan 04)
- [x] 01-PLAN-06-ingestion-pipeline.md — End-to-end pipeline wiring + CLI entry point (Wave 4) COMPLETE

### Phase 2: Embedding & Vector Search

**Goal:** System generates embeddings for all chunks and stores them in ChromaDB; consultant can retrieve relevant documents via semantic similarity.

**Depends on:** Phase 1

**Requirements:** EMBED-01, EMBED-02, EMBED-03

**Success Criteria** (what must be TRUE):
1. System generates embeddings for each chunk using LM Studio OpenAI-compatible API (nomic-embed-text-1.5 or equivalent)
2. Embeddings are stored in ChromaDB with chunk text and metadata (document name, page/slide number) indexed and queryable
3. System can retrieve top-10 semantically similar chunks for a test query in under 50ms
4. VRAM peak during embedding generation stays below 3.5GB (50% safety margin from 4GB ceiling)
5. Retrieval precision on 20 test queries exceeds 80% (correct documents ranked at top)

**Plans:** 4/4 plans complete

Plans:
- [x] 02-01-test-infrastructure-PLAN.md — chromadb install, src/embed/ stubs, 12 xfail test stubs (Wave 1)
- [x] 02-02-embedder-PLAN.md — embed_chunks() and embed_query() via LM Studio OpenAI API (Wave 2, parallel with Plan 03)
- [x] 02-03-vector-store-PLAN.md — VectorStore class wrapping ChromaDB with cosine similarity, upsert, query (Wave 2, parallel with Plan 02)
- [x] 02-04-embedding-pipeline-PLAN.md — embed_all_chunks() pipeline + embed CLI subcommand (Wave 3)

### Phase 3: Knowledge Graph Construction

**Goal:** System extracts named entities and relationships from chunks, deduplicates them, and builds a knowledge graph in KuzuDB; entities are linked back to source chunks for citation.

**Depends on:** Phase 2

**Requirements:** GRAPH-01, GRAPH-02, GRAPH-03, GRAPH-04

**Success Criteria** (what must be TRUE):
1. System extracts named entities (OEMs, suppliers, technologies, products, recommendations) and typed relationships from chunks using LM Studio LLM
2. System deduplicates entities using fuzzy matching (Levenshtein distance < 2, title case normalization, legal suffix removal)
3. Knowledge graph is stored in KuzuDB with entities and relationships queryable; entity count stays below 10K for 500-document corpus (ratio < 20 entities/doc average)
4. Each graph entity is linked to source chunks; user can trace any entity back to the documents that mention it
5. System detects and prevents graph explosion (entity extraction too permissive) via monitoring entity count growth rate relative to document count

**Plans:** 5/5 plans complete

Plans:
- [x] 03-01-test-infrastructure-PLAN.md — kuzu/rapidfuzz install, src/graph/ stubs, 23 xfail stubs across 4 test files (Wave 1)
- [x] 03-02-extractor-PLAN.md — extract_entities_relationships() via LM Studio LLM with entity type whitelist + confidence filter (Wave 2, parallel with Plan 03)
- [x] 03-03-dedup-and-db-PLAN.md — normalize_entity_name(), deduplicate_entities() with RapidFuzz; KuzuDB schema + upsert + query (Wave 2, parallel with Plan 02)
- [x] 03-04-citations-and-monitor-PLAN.md — CitationStore SQLite bridge table; check_entity_density() graph explosion guard (Wave 3)
- [x] 03-05-pipeline-and-cli-PLAN.md — build_knowledge_graph() pipeline wiring + graph CLI subcommand (Wave 4)

### Phase 4: Query Engine & Answer Generation

**Goal:** Consultant submits a question and receives a synthesized answer drawn from the knowledge graph and vector store, with source citations.

**Depends on:** Phase 3

**Requirements:** QUERY-01, QUERY-02, QUERY-03, QUERY-04, QUERY-05

**Success Criteria** (what must be TRUE):
1. System accepts natural language questions from user input and retrieves relevant chunks via vector similarity (local semantic search)
2. System augments vector retrieval with entity-based graph traversal to expand context (neighboring entities and their related chunks)
3. System synthesizes a coherent answer using LM Studio LLM (Qwen2.5 7B or equivalent) with context from retrieved chunks and graph traversal
4. Every answer includes source citations (document name, page/slide number, confidence level HIGH/LOW based on citation count)
5. Query latency (retrieve + generate) is under 15 seconds for typical consultant questions

**Plans:** 4/4 plans complete

Plans:
- [x] 04-01-test-infrastructure-PLAN.md — src/query/ stubs, 11 xfail test stubs across 3 test files (Wave 1)
- [x] 04-02-hybrid-retriever-PLAN.md — vector_search() + graph_expand() + hybrid_retrieve() (Wave 2, parallel with Plan 03)
- [x] 04-03-assembler-and-citations-PLAN.md — truncate_to_budget() + build_citations() HIGH/LOW + format_answer() (Wave 2, parallel with Plan 02)
- [x] 04-04-pipeline-and-cli-PLAN.md — answer_question() pipeline wiring + query CLI subcommand (Wave 3)

### Phase 5: Chat UI & Session Management

**Goal:** Non-technical consultant can interact with the system via a browser-based Streamlit interface; conversation history is preserved within a session.

**Depends on:** Phase 4

**Requirements:** UI-01, UI-02

**Success Criteria** (what must be TRUE):
1. Consultant can access the system via a browser-based Streamlit chat interface at a simple URL (no CLI/terminal knowledge required)
2. Consultant can type a question, submit it, and see a synthesized answer with citations displayed in an easy-to-read format
3. Chat history shows all previous Q&A pairs in the current session; user can scroll back to review earlier questions and answers
4. Source citations are clickable or formatted to help consultant quickly find the referenced document
5. System does not crash or require restart when processing queries; error messages are user-friendly and do not expose technical jargon

**Plans:** 3/3 plans complete

Plans:
- [x] 05-01-test-infrastructure-PLAN.md — app.py stub + 4 AppTest xfail stubs (Wave 1)
- [x] 05-02-chat-app-PLAN.md — full Streamlit chat interface with session state + error handling (Wave 2)
- [x] 05-03-citations-and-polish-PLAN.md — citations expander, HIGH/LOW badges, polish (Wave 3)

**UI hint:** yes

### Phase 6: Multi-Provider LLM & Embedding Configuration

**Goal:** Any LLM or embedding model provider (LM Studio, Ollama, Gemini, OpenAI, Anthropic) can be used by setting environment variables in a `.env` file — no code changes required; LM Studio remains the default.

**Depends on:** Phase 5

**Requirements:** PROVIDER-01, PROVIDER-02, PROVIDER-03, PROVIDER-04, PROVIDER-05, PROVIDER-06

**Success Criteria** (what must be TRUE):
1. User can set `LLM_PROVIDER=gemini` and `GEMINI_API_KEY=...` in `.env` and the query/graph steps use the Gemini LLM without any code change
2. User can set `EMBED_PROVIDER=openai` and `OPENAI_API_KEY=...` in `.env` and the embed/query steps use the OpenAI embedding model without any code change
3. When `.env` is absent or provider keys are unset, system behaves identically to current LM Studio behaviour (backward compatible)
4. Switching embedding provider warns user that a full re-embed is required; the warning is surfaced at CLI and UI level before proceeding
5. All pipeline tests pass for the default LM Studio config; provider switching is covered by unit tests with mocked LiteLLM calls

**Plans:** 4/4 plans complete

Plans:
- [x] 06-01-PLAN.md — test stubs: test_config_providers.py (9 xfail), conftest fixtures, src/config/__init__.py (Wave 1)
- [x] 06-02-PLAN.md — src/config/providers.py factory functions, .env.example, requirements.txt update (Wave 2, parallel with Plan 03)
- [x] 06-03-PLAN.md — metadata table schema, embed mismatch detection in embed_all_chunks() (Wave 2, parallel with Plan 02)
- [x] 06-04-PLAN.md — call site refactoring: graph/pipeline.py, query/pipeline.py, app.py (Wave 3)

### Phase 7: RAG Retrieval Quality Improvements

**Goal:** Improve retrieval precision and recall for consultant queries by layering BM25 hybrid search (with Reciprocal Rank Fusion), BGE cross-encoder reranking, contextual chunk enrichment at ingest time, and parent-document retrieval — without requiring re-ingestion of all documents.

**Depends on:** Phase 6

**Requirements:** RAG-01, RAG-02, RAG-03, RAG-04, RAG-05

**Success Criteria** (what must be TRUE):
1. Queries that previously returned poor results due to vocabulary mismatch (e.g. "warranty" vs "warranty claims management") now retrieve correct chunks via BM25 keyword fallback
2. Cross-encoder reranker (BGE) re-orders retrieved candidates so that the most relevant chunk is ranked #1 more often than with pure vector similarity
3. Hybrid BM25+vector retrieval with RRF fusion outperforms pure vector retrieval on a set of 10 representative consultant queries
4. Parent-document context retrieval returns larger surrounding passage to LLM when child chunk matches, improving answer completeness
5. All improvements are additive — existing retrieval path remains functional and all prior tests continue to pass

**Plans:** 1/5 plans executed

Plans:
- [x] 07-01-PLAN.md — Test infrastructure: xfail stubs for RAG-01 through RAG-05, conftest fixtures (Wave 1)
- [ ] 07-02-PLAN.md — BM25 hybrid search + RRF: bm25_index.py, rrf.py, pipeline integration (Wave 2, parallel with Plan 03)
- [ ] 07-03-PLAN.md — BGE cross-encoder reranker: reranker.py, pipeline integration (Wave 2, parallel with Plan 02)
- [ ] 07-04-PLAN.md — Contextual enrichment + parent-document retrieval: enricher.py, store.py schema, assembler expand_to_parent (Wave 3)
- [ ] 07-05-PLAN.md — Integration + feature flag config: retrieval_config.py, pipeline wire-up, requirements.txt (Wave 4)

---

## Progress Tracking

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Document Ingestion Foundation | 6/6 | Complete | 2026-03-28 |
| 2. Embedding & Vector Search | 4/4 | Complete   | 2026-03-30 |
| 3. Knowledge Graph Construction | 5/5 | Complete   | 2026-03-30 |
| 4. Query Engine & Answer Generation | 4/4 | Complete    | 2026-03-31 |
| 5. Chat UI & Session Management | 3/3 | Complete   | 2026-03-31 |
| 6. Multi-Provider LLM & Embedding Configuration | 4/4 | Complete   | 2026-03-31 |
| 7. RAG Retrieval Quality Improvements | 1/5 | In Progress|  |

---

## Coverage Summary

**Total v1 Requirements:** 17
**Requirements Mapped:** 17
**Orphaned Requirements:** 0

| Category | Count | Phase |
|----------|-------|-------|
| Ingestion (INGEST) | 3 | Phase 1 |
| Embedding (EMBED) | 3 | Phase 2 |
| Knowledge Graph (GRAPH) | 4 | Phase 3 |
| Query (QUERY) | 5 | Phase 4 |
| Chat UI (UI) | 2 | Phase 5 |
| Provider Config (PROVIDER) | 6 | Phase 6 |
| RAG Quality (RAG) | 5 | Phase 7 |

**Status:** Phase 7 added — RAG retrieval quality improvements. Phase 6 complete.
