# Automotive Consulting GraphRAG Agent — Project Roadmap

**Project:** Automotive Consulting GraphRAG Agent
**Created:** 2026-03-28
**Granularity:** Standard (5-8 phases)
**Status:** Ready for phase planning

---

## Phases

- [ ] **Phase 1: Document Ingestion Foundation** - Extract text from PDF and PPTX files into a chunk store
- [ ] **Phase 2: Embedding & Vector Search** - Generate and store embeddings for semantic retrieval
- [ ] **Phase 3: Knowledge Graph Construction** - Extract entities, relationships, and build knowledge graph
- [ ] **Phase 4: Query Engine & Answer Generation** - Retrieve, synthesize, and cite answers to user questions
- [ ] **Phase 5: Chat UI & Session Management** - Streamlit interface for consultants to interact with the system

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

**Plans:** TBD

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

**Plans:** TBD

**UI hint:** yes

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

**Plans:** TBD

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

**Plans:** TBD

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

**Plans:** TBD

**UI hint:** yes

---

## Progress Tracking

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Document Ingestion Foundation | 0/4 | Not started | - |
| 2. Embedding & Vector Search | 0/3 | Not started | - |
| 3. Knowledge Graph Construction | 0/4 | Not started | - |
| 4. Query Engine & Answer Generation | 0/4 | Not started | - |
| 5. Chat UI & Session Management | 0/3 | Not started | - |

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

**Status:** All requirements mapped. Coverage = 100%. Ready for planning.

