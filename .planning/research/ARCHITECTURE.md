# Architecture Patterns: Local GraphRAG Document Intelligence

**Project:** Automotive Consulting GraphRAG Agent
**Researched:** 2026-03-28
**Scope:** Local-only, single-user GraphRAG system (no cloud APIs, no multi-user scaling)
**Reference Systems:** LightRAG, Microsoft GraphRAG (adapted for local use)

---

## Executive Summary

A local GraphRAG system splits into **5 independent pipelines** that share common storage:

1. **Ingestion Pipeline** — Files → Text Extraction → Document Storage
2. **Indexing Pipeline** — Text Chunks → Embeddings + Entity/Relationship Extraction → Graph Construction
3. **Query Pipeline** — Natural Language → Graph Traversal → Context Assembly → LLM Response
4. **Storage Layer** — Local persistent databases (vectors, graphs, metadata)
5. **API Layer** — FastAPI server exposing REST endpoints for UI

**Key architectural principle:** Decouple ingestion from indexing from querying. A consultant can ask questions while a new batch indexes in the background.

---

## Recommended Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER: Web Chat UI (React/Vue)              │
└──────────────────────────┬──────────────────────────────────────┘
                          │ HTTP/WebSocket
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│              API Layer: FastAPI REST + WebSocket Server         │
│  /chat (query endpoint)  /ingest (file upload)  /status (pipeline)
└──────┬──────────────────────────┬──────────────────────────────┘
       │                          │
       ↓                          ↓
┌──────────────────┐   ┌──────────────────────────────────┐
│  QUERY PIPELINE  │   │  INGESTION + INDEXING PIPELINES  │
├──────────────────┤   ├──────────────────────────────────┤
│ 1. Parse query   │   │ 1. File watcher / Manual upload  │
│ 2. Generate QE   │   │ 2. Text extraction (pypdf/pdf2x) │
│ 3. Graph search  │   │ 3. Chunk splitting               │
│ 4. Context pool  │   │ 4. Embed chunks (LM Studio)      │
│ 5. LLM generate  │   │ 5. Extract entities (LLM)        │
│ 6. Format output │   │ 6. Build relationships (LLM)     │
│    + citations   │   │ 7. Dedup + Link entities        │
└────────┬─────────┘   │ 8. Detect communities (algo)     │
         │             │ 9. Store in graph DB             │
         │             └──────────────────┬────────────────┘
         │                                │
         └────────────┬───────────────────┘
                      ↓
         ┌────────────────────────────────────────┐
         │      STORAGE LAYER (All Local)         │
         ├────────────────────────────────────────┤
         │ • Vector DB (FAISS, ChromaDB, Qdrant)  │
         │ • Graph DB (Neo4j, NetworkX + SQLite)  │
         │ • Chunk store (SQLite, JSON files)     │
         │ • Doc metadata (SQLite)                │
         │ • Embeddings cache                     │
         └────────────────────────────────────────┘
```

---

## Component Boundaries

### 1. **Ingestion Pipeline**

**Responsibility:** Detect, extract, and persist raw document content

**Inputs:**
- PDF files (from watched directory or manual upload via UI)
- PPTX files (from watched directory or manual upload via UI)

**Outputs:**
- Raw text chunks (persisted to Chunk Store)
- Document metadata (persisted to Metadata DB)

**Components:**
```
File Watcher / Upload Handler
    ↓
PDF Extractor (pypdf, pdfplumber, or PyPDF2)
    ↓
PPTX Extractor (python-pptx)
    ↓
Text Normalizer (clean up OCR artifacts, normalize whitespace)
    ↓
Chunk Splitter (sliding window: 1024 tokens, overlap 200)
    ↓
Chunk Store Writer (SQLite table: chunk_id, doc_id, text, page)
```

**Key Decision: Batch vs Streaming**
- **Batch processing (RECOMMENDED for local):** Upload files → trigger indexing job → wait for completion
- Rationale: Simpler resource management, easier to restart, matches office workflow (batch uploads at shift start)
- Streaming would require background workers and complex state management; overkill for single-user

**Key Decision: File Watcher vs Manual Upload**
- **Manual upload via UI (RECOMMENDED initially):** User drags PDFs into chat UI, system processes
- Rationale: More explicit user control, fewer false positives, doesn't require monitoring filesystem
- File watcher can be added in a future phase for power users

**Communicates With:**
- Indexing Pipeline (queues processed documents)
- Storage Layer (writes chunks + metadata)
- API Layer (receives upload requests)

---

### 2. **Indexing Pipeline**

**Responsibility:** Convert text chunks into embeddings, extract entities/relationships, build knowledge graph

**Inputs:**
- Document chunks (from Ingestion Pipeline or Chunk Store)
- Document metadata

**Outputs:**
- Embeddings (stored in Vector DB)
- Entities with embeddings (stored in Graph DB)
- Relationships (stored in Graph DB)
- Community assignments (stored in Graph DB)

**Components:**

```
Chunk Reader (from Chunk Store)
    ↓
Embedding Generator (LM Studio OpenAI-compatible API)
    → Output: vector per chunk, stored in Vector DB
    ↓
Entity Extractor (LLM prompt: "Extract named entities and their types")
    → Output: entities per chunk
    ↓
Entity Deduplication (fuzzy matching, context pooling)
    → Output: canonical entities with IDs
    ↓
Relationship Builder (LLM prompt: "What relationships exist between these entities?")
    → Output: typed edges (e.g., "MENTIONS", "RELATED_TO", "COLLABORATES_WITH")
    ↓
Relationship Deduplication (merge duplicate edges, aggregate weights)
    ↓
Community Detector (optional: Louvain or Leiden algorithm)
    → Output: community assignments for each entity
    ↓
Graph Store Writer (persist entities, relationships, communities to Graph DB)
```

**Key Architecture Decision: LightRAG Approach**

LightRAG (state-of-the-art for local graph construction) uses this strategy:

1. **Two-stage entity extraction:**
   - First pass: Extract dense entities (people, companies, products)
   - Second pass: Extract relationships between them
   - Rationale: Sequential passes are cheaper than joint extraction and more accurate

2. **Adaptive entity description:**
   - Maintains entity embeddings AND text descriptions
   - When querying, uses semantic similarity (embedding distance) + keyword matching
   - Rationale: Avoids pure keyword-based retrieval failures

3. **Hierarchical community detection:**
   - Detects fine-grained (local) and coarse-grained (global) communities
   - Queries can traverse at different scales
   - Rationale: Matches how consultants think ("what themes?" vs "what specific projects?")

4. **Incremental graph updates:**
   - New documents add entities/relationships to existing graph
   - Deduplication merges them with existing nodes
   - Rationale: Supports batch indexing without full graph rebuilds

**Communicates With:**
- Ingestion Pipeline (reads chunks)
- Storage Layer (reads/writes embeddings, graph data)
- LM Studio (for embeddings and entity/relationship extraction)
- Query Pipeline (graph serves queries)

---

### 3. **Query Pipeline**

**Responsibility:** Answer natural language questions using the graph and document chunks

**Inputs:**
- User question (natural language string)
- Query parameters (max context tokens, answer length, etc.)

**Outputs:**
- Synthesized answer (text)
- Source citations (document references with page numbers)
- Evidence snippets (quoted text from source chunks)

**Components:**

```
Query Parser (optional: classify as factual/synthesized/search)
    ↓
Query Embedding (generate embedding for user question)
    ↓
Graph Search (Hybrid search strategy):

    A. Entity-based path: Find entities mentioned in question → traverse edges → collect related entities

    B. Vector-based search: Find semantically similar entities/chunks → expand to neighbors

    ↓
Context Assembly (combine retrieved entities, relationships, and raw chunks)
    → Output: ranked context window (top K chunks, top M entities, relationships between them)
    ↓
LLM Generation (LM Studio: generate answer given question + context)
    → Prompt template: "Question: {question}. Context: {context}. Answer concisely with citations."
    ↓
Citation Extractor (parse response, map back to source documents + chunks)
    ↓
Response Formatter (return {answer, sources: [{doc, page, snippet}, ...]}
```

**Graph Traversal Strategy:**

For the query "What proposals did we write for EV manufacturers?":

1. Find entity "EV manufacturers" in graph (or fuzzy match)
2. Traverse MENTIONS edges → documents that mention EV manufacturing
3. Traverse RELATED_TO edges → related entities (battery, powertrain, supply chain)
4. Collect all connected documents
5. Rank by relevance (edge weights, community overlap)
6. Assemble top-K chunks as context for LLM

**Communicates With:**
- Storage Layer (reads embeddings, graph, chunks)
- LM Studio (for query embedding + answer generation)
- API Layer (receives queries, sends responses)

---

### 4. **Storage Layer**

**Responsibility:** Persistent local storage for all graph, vector, and document data

**Components:**

#### **Vector Database**
- **Technology:** FAISS (Facebook AI Similarity Search) or ChromaDB
  - FAISS: Simple, fast, in-memory for ≤1M vectors (sufficient for 500–2000 docs)
  - ChromaDB: Built-in persistence, easier to manage, also local
  - Recommendation: **ChromaDB** for simpler API and built-in SQLite persistence
- **What it stores:** Chunk embeddings (one embedding per chunk)
- **Key-value:** `chunk_id → embedding (768 or 1024 dims)`
- **Index type:** Flat (small corpus) or IVF (future scaling)

#### **Graph Database**
- **Technology:** One of:
  1. **Neo4j Community Edition** (powerful queries, full ACID, overkill for single-user but handles growth well)
  2. **SQLite + NetworkX** (simpler, fully local, sufficient for ≤10K entities)
  3. **DuckDB** (fast analytics, good for aggregations over graph structure)
- **Recommendation for v1:** **SQLite + NetworkX in-memory cache**
  - Why SQLite: Zero external deps, embedded, no server to run
  - Why NetworkX cache: Graph algorithms (community detection, shortest path) are trivial in NetworkX
  - Upgrade path: Swap for Neo4j in Phase 2 if needed
- **Schema:**
  ```
  entities:
    - id (primary key)
    - text (entity name)
    - type (person, company, concept, etc.)
    - embedding (vector)
    - description (text summary from LLM)
    - community_id (for hierarchical clustering)
    - doc_count (# of documents mentioning this entity)
    - first_seen, last_seen (timestamps)

  relationships:
    - id (primary key)
    - source_entity_id (foreign key)
    - target_entity_id (foreign key)
    - relation_type (MENTIONS, COLLABORATES_WITH, RELATED_TO, etc.)
    - weight (float: how often co-occurs)
    - evidence_chunks ([chunk_ids] that support this relationship)

  communities:
    - id (primary key)
    - entities ([entity_ids])
    - level (0=fine-grained, 1=medium, 2=coarse)
    - description (text summary of community theme)
  ```

#### **Chunk Store**
- **Technology:** SQLite table
- **Schema:**
  ```
  chunks:
    - id (primary key)
    - document_id (foreign key)
    - text (the actual chunk text, up to 1024 tokens)
    - embedding (redundant with vector DB for quick lookup)
    - page_number (for citations)
    - token_count
    - created_at
  ```

#### **Document Metadata**
- **Technology:** SQLite table
- **Schema:**
  ```
  documents:
    - id (primary key)
    - filename (original filename)
    - file_type (pdf, pptx)
    - upload_timestamp
    - text_length
    - chunk_count
    - status (pending, indexed, failed)
    - error_message (if failed)
  ```

#### **Storage Organization**
```
~/.graphrag/  (or configurable)
├── data/
│   ├── graph.db (SQLite: entities, relationships, communities)
│   ├── chunks.db (SQLite: raw text chunks, doc metadata)
│   ├── embeddings.db (ChromaDB: vectors)
│   └── index/ (FAISS index files if using FAISS)
└── logs/
    └── indexing.log
```

**Communicates With:**
- All pipelines (read/write)
- No external network calls

---

### 5. **API Layer**

**Responsibility:** Expose REST endpoints for the UI and handle async task management

**Technology:** FastAPI + Uvicorn

**Endpoints:**

```
POST /chat
  Request: { "query": "What proposals for EVs?" }
  Response: {
    "answer": "We completed 3 EV proposals in 2022-2023...",
    "sources": [
      { "doc": "EV Strategy Proposal.pdf", "page": 5, "snippet": "..." },
      ...
    ]
  }
  → Calls Query Pipeline

POST /ingest
  Request: file upload (PDF or PPTX)
  Response: { "job_id": "abc123", "status": "queued" }
  → Queues to Ingestion + Indexing Pipeline

GET /ingest/status/{job_id}
  Response: { "status": "processing", "progress": "45%", "documents": 123 }
  → Polls pipeline status

GET /health
  Response: { "status": "ok", "indexed_docs": 150, "entities": 2400 }
  → Quick system healthcheck

WS /ws/query
  WebSocket: enable real-time streaming LLM responses (optional, v2+)
```

**Task Queue:**
- **Technology:** Simple in-memory queue with threading (for v1)
- **Upgrade path:** Celery + Redis (for v2, if multi-tasking becomes needed)
- Single background thread processes indexing jobs sequentially
- User can still query while background indexing runs

**Communicates With:**
- Web UI (HTTP/WebSocket)
- All pipelines (orchestrates, receives status updates)

---

## Data Flow

### Ingestion Flow
```
User uploads PDF/PPTX via UI
    ↓ [POST /ingest]
API Layer receives file
    ↓
Ingestion Pipeline
    ├─→ Extract text (pypdf/python-pptx)
    ├─→ Split into chunks (1024 tokens, overlap 200)
    └─→ Write to Chunk Store (SQLite)
    ↓
Return job_id to user
    ↓
[Background] Indexing Pipeline begins
    ├─→ Read chunks from Chunk Store
    ├─→ Generate embeddings (LM Studio)
    │   └─→ Store in Vector DB (ChromaDB)
    ├─→ Extract entities (LLM prompts)
    │   └─→ Deduplicate, generate descriptions
    ├─→ Extract relationships (LLM prompts)
    │   └─→ Deduplicate, weight by frequency
    ├─→ Detect communities (Louvain algorithm)
    └─→ Write all to Graph DB (SQLite)
    ↓
User polls /ingest/status/{job_id}
    ↓
When complete, documents are queryable
```

### Query Flow
```
User types "What proposals for EVs?" in chat UI
    ↓ [POST /chat]
API Layer receives query
    ↓
Query Pipeline
    ├─→ Embed query (LM Studio)
    ├─→ Search graph:
    │   ├─ Vector search: find similar chunks
    │   └─ Entity search: find relevant entities + traverse edges
    ├─→ Assemble context (top K chunks + related entities + relationships)
    │   └─ Rank by relevance score
    ├─→ Generate answer (LM Studio, with prompt including context)
    └─→ Extract citations (map entities/chunks back to source docs)
    ↓
Return { answer, sources } to API Layer
    ↓
Format response, send to UI
    ↓
Display in chat with citations
```

---

## Component Dependencies & Build Order

**Build order matters.** Each phase depends on previous phases.

### Phase 1: Core Infrastructure (Weeks 1-2)
**Goal:** Get ingestion and basic storage working. Can't do anything without extracting text.

Components to build:
1. **Chunk Store (SQLite schema + CRUD)**
   - Start here: all other components depend on having text
   - Define tables: documents, chunks
   - Implement: write_chunks(), read_chunks_for_doc()

2. **Document Metadata Storage**
   - Extend Chunk Store with documents table
   - Track filename, upload timestamp, status

3. **File Upload API Endpoint** (`POST /ingest`)
   - FastAPI server skeleton
   - Handle PDF/PPTX upload, queue to ingestion

4. **Text Extraction** (pypdf for PDF, python-pptx for PPTX)
   - Extract text to chunks
   - Validate text quality

**Dependency:** None (greenfield)

**Why this order:**
- Everything downstream needs text in the database
- Fail early if text extraction doesn't work for your documents
- Validate document quality before spending compute on indexing

---

### Phase 2: Indexing Pipeline (Weeks 3-4)
**Goal:** Build the graph. Start simple (embeddings only), then add entity extraction.

Components to build:
1. **Vector Database (ChromaDB)**
   - Initialize, persist to disk
   - Implement: store_embeddings(), search_by_vector()

2. **Embedding Generation**
   - Call LM Studio embedding endpoint
   - Cache results to avoid re-embedding
   - Handle batch requests

3. **Entity Extraction (LLM-based)**
   - Prompt template: "Extract entities and their types from this text"
   - Parse LLM response (handle JSON or structured output)
   - Store entities with their original chunk mentions

4. **Graph Database (SQLite)**
   - Schema: entities table, relationships table
   - Implement: add_entity(), add_relationship(), deduplicate_entity()

5. **Relationship Builder (LLM-based)**
   - Prompt template: "What relationships exist between these entities?"
   - Connect entities found in same/adjacent chunks
   - Weight edges by co-occurrence frequency

**Dependency:** Phase 1 (needs chunks)

**Why this order:**
- Start with embeddings (simpler) before entity extraction (more complex)
- Validate LM Studio integration early
- Graph schema is independent of detection algorithm

---

### Phase 3: Query System (Weeks 5-6)
**Goal:** Answer questions using the graph

Components to build:
1. **Query Embedding**
   - Reuse embedding endpoint from Phase 2

2. **Graph Search**
   - Vector search: FAISS/ChromaDB similarity to query embedding
   - Keyword search: parse entities from question, traverse graph
   - Combine and rank results

3. **Context Assembly**
   - Retrieve top-K chunks, top-M entities, relationships between them
   - Assemble into context string for LLM

4. **LLM Answer Generation**
   - Prompt template: "Question: {q}. Context: {context}. Answer:"
   - Call LM Studio LLM endpoint
   - Parse response

5. **Citation Extraction**
   - Map retrieved chunks → source documents
   - Format with page numbers and snippets

6. **Chat API Endpoint** (`POST /chat`)
   - Orchestrate query pipeline
   - Return answer + sources to UI

**Dependency:** Phase 1, 2 (needs chunks, graph, embeddings)

---

### Phase 4: User Interface (Weeks 7-8)
**Goal:** Web chat UI for consultants

Components to build:
1. **Frontend (React/Vue)**
   - Chat interface (message history, send box)
   - Display answers with source cards
   - Link to original documents

2. **Status Dashboard** (optional)
   - Show indexing progress
   - Document upload history
   - Health metrics

3. **WebSocket/Streaming** (optional, v2+)
   - Real-time LLM response streaming
   - Progress updates during indexing

**Dependency:** Phase 3 (needs API endpoints)

---

### Phase 5 (Future): Advanced Indexing
**Goal:** Improve graph quality

Components to build (if needed):
1. **Community Detection (Louvain algorithm)**
   - Detect clusters of related entities
   - Enable hierarchical querying

2. **Entity Disambiguation**
   - Handle same entity with multiple names
   - Merge "Tesla Motors", "Tesla Inc.", "Elon's company"

3. **Cross-document Relationship Synthesis**
   - When same relationship appears in multiple docs, merge with higher weight

**Dependency:** Phase 2 (needs existing graph structure)

---

## Build Order Summary

```
Phase 1: Ingestion
  ├─ Chunk Store (SQLite)
  ├─ File Upload API
  └─ Text Extraction

Phase 2: Indexing (parallel possible)
  ├─ Embeddings (Vector DB + LM Studio)
  ├─ Entity Extraction
  ├─ Graph DB (SQLite)
  └─ Relationship Builder

Phase 3: Query
  ├─ Graph Search
  ├─ LLM Answer Generation
  └─ Chat API

Phase 4: UI
  └─ Web Interface

Phase 5: Polish (optional)
  ├─ Community Detection
  └─ Entity Disambiguation
```

---

## Storage Architecture Decision: Why SQLite + ChromaDB?

For a local, single-user system with 500–2000 documents:

| Component | Option A | Option B (RECOMMENDED) | Why |
|-----------|----------|------------------------|-----|
| Graph DB | Neo4j | SQLite + NetworkX | Zero external process; NetworkX has all needed algorithms (DFS, community detection); upgrade path if needed |
| Vector DB | FAISS | ChromaDB | Better API, built-in persistence, Python-first; FAISS is overkill for ≤1M vectors |
| Chunk Store | MongoDB | SQLite | Embedded, zero dependencies; 500–2000 docs fit comfortably |
| Metadata | PostgreSQL | SQLite | All data is local; no ACID multi-table transactions needed; SQLite is reliable enough |

**Total storage estimate:**
- 500 documents, avg 50 pages, ~100 tokens per chunk
  - Chunks: 500 × 50 × 10 chunks/page × 4 bytes/token = ~100 MB
  - Embeddings (768 dims, float32): 500 × 500 chunks × 768 × 4 bytes = ~1 GB
  - Entities: ~5K–10K entities × 100 bytes + embeddings = ~500 MB
  - Relationships: ~10K–50K edges × 50 bytes = ~1 MB
  - **Total: ~2 GB** (fits on modern laptops)

---

## API Design Summary

### FastAPI Server
```python
# Pseudo-code structure
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

# Task queue (simple threading for v1)
indexing_queue = Queue()
indexing_thread = Thread(target=process_indexing_queue, daemon=True)
indexing_thread.start()

@app.post("/ingest")
async def upload_document(file: UploadFile):
    """Queue document for ingestion + indexing"""
    job_id = str(uuid.uuid4())
    indexing_queue.put({"job_id": job_id, "file": file})
    return {"job_id": job_id, "status": "queued"}

@app.post("/chat")
async def query(request: QueryRequest):
    """Answer question using graph + LLM"""
    # Query pipeline orchestration
    answer, sources = query_pipeline.run(request.query)
    return {"answer": answer, "sources": sources}

@app.get("/ingest/status/{job_id}")
async def check_status(job_id: str):
    """Poll indexing progress"""
    return indexing_queue.status(job_id)
```

---

## Key Architectural Constraints

1. **LM Studio Integration**
   - All LLM calls go through LM Studio OpenAI API (embedding + generation)
   - No fallback to cloud APIs
   - Must handle model context limits (likely 4K or 8K for quantized models)

2. **Memory Constraints (32GB RAM, 4GB VRAM)**
   - Graph must fit in RAM or be efficiently cached (SQLite helps)
   - Embeddings must fit in Vector DB (ChromaDB on disk is OK)
   - Batch embedding to avoid GPU OOM
   - Quantized models only (GGUF format for LM Studio)

3. **Local-Only Design**
   - No external API calls
   - No cloud storage
   - All databases are file-based

4. **Single-User Model**
   - No concurrent indexing jobs (simple queue)
   - No multi-user auth
   - No query result caching strategy needed

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Storing Raw Vectors in Graph DB
**What goes wrong:** Neo4j/similar tries to index 768-dim vectors; queries are slow
**Instead:** Use dedicated vector DB (ChromaDB) for vector operations, graph DB for relationships only

### Anti-Pattern 2: Re-extracting Entities on Every Query
**What goes wrong:** Slow queries if LLM entity extraction happens at query time
**Instead:** Pre-compute all entities during indexing, query only uses pre-built graph

### Anti-Pattern 3: Single Monolithic Embedding for Whole Document
**What goes wrong:** Doc has 200 pages; single embedding loses fine-grained detail
**Instead:** Chunk at 1024 tokens, embed per chunk, assemble context at query time

### Anti-Pattern 4: Naive Graph Traversal (No Depth Limit)
**What goes wrong:** Query 1 entity → traverse all edges → exponential explosion
**Instead:** Limit traversal depth (max 3 hops), use relevance ranking

### Anti-Pattern 5: Storing Embeddings in Both Vector DB and Graph DB
**What goes wrong:** Redundant storage, inconsistency, sync nightmares
**Instead:** Single source of truth in Vector DB, reference by chunk_id in graph DB

---

## Recommended Technology Stack

| Layer | Technology | Version | Why |
|-------|-----------|---------|-----|
| **API Server** | FastAPI | 0.100+ | Async, fast, simple; Pydantic validation |
| **Web Framework** | React or Vue | Latest | Non-technical UI; hosted locally via Uvicorn |
| **Chunk Store** | SQLite 3 | 3.40+ | Zero dependencies; full-text search capability |
| **Vector DB** | ChromaDB | 0.4+ | Local, persistent, Python API |
| **Graph DB** | SQLite + NetworkX | 3.0+ | Embedded; all graph algorithms available |
| **Text Extraction** | pypdf + python-pptx | Latest | Reliable, maintained, local |
| **Embeddings** | LM Studio (OpenAI API compat) | Via HTTP | Local model serving |
| **LLM** | LM Studio (OpenAI API compat) | Via HTTP | Local model serving |
| **Graph Algorithms** | NetworkX | 3.2+ | Community detection, shortest path, all needed algorithms |
| **Task Queue** | Python threading | stdlib | Simple for single-user; upgrade to Celery if needed |

---

## Scalability Roadmap

### Current Design (v1): Single-user, 500–2000 docs
- Simple threading, in-memory queues
- SQLite for all storage
- FAISS flat index or ChromaDB (no partitioning needed)

### Growth Phase (v2): Single-user, 5000–50K docs
- Add community detection for hierarchical traversal
- Migrate to Neo4j if SQLite queries become slow
- Add LRU cache for frequently accessed entities
- Batch embedding requests to maximize GPU utilization

### Multi-user Phase (v3+): NOT IN SCOPE NOW
- Would require: PostgreSQL, Celery, Redis, user auth, ACLs
- Skip this until product-market fit proven

---

## Sources & References

**Research basis:** Architecture patterns synthesized from:
- LightRAG architecture (local-first graph construction, adaptive entity descriptions)
- Microsoft GraphRAG (entity extraction → relationships → community detection pipeline)
- Llamaindex Graph Stores (entity/relationship schema design)
- Local RAG best practices (chunking, embedding, retrieval patterns)

**Implementation references:**
- ChromaDB: Python vector DB library (Apache 2.0)
- NetworkX: Graph algorithms library (BSD)
- FastAPI: Web framework (MIT)
- SQLite: SQL database (public domain)

---

## Next Steps for Phase-Specific Research

1. **Phase 1 (Ingestion):** Deep-dive on text extraction quality for PDFs with tables/figures
2. **Phase 2 (Indexing):** Empirical testing of entity extraction prompt effectiveness on consulting documents
3. **Phase 3 (Query):** Test graph traversal performance with 5K+ entities; benchmark context assembly ranking
4. **Phase 4 (UI):** Consultant UX research on citation format preferences

