# Requirements: Automotive Consulting GraphRAG Agent

**Defined:** 2026-03-28
**Core Value:** A consultant types a question and gets a cited, synthesized answer drawn from 15 years of institutional knowledge — fast, locally, without leaving their laptop.

## v1 Requirements

### Ingestion

- [x] **INGEST-01**: System extracts full text content from PDF files using PyMuPDF
- [x] **INGEST-02**: System extracts text from PPTX files including slide text, speaker notes, and table cells via python-pptx
- [x] **INGEST-03**: System chunks extracted text into segments suitable for embedding and graph extraction

### Embedding & Vector Store

- [x] **EMBED-01**: System generates embeddings for each chunk using a local model served via LM Studio OpenAI-compatible API
- [x] **EMBED-02**: System stores chunk embeddings in ChromaDB for semantic retrieval
- [x] **EMBED-03**: System stores raw chunk text and document metadata (filename, page/slide number) alongside vectors

### Knowledge Graph

- [x] **GRAPH-01**: System extracts named entities and typed relationships from chunks using LLM via LM Studio
- [x] **GRAPH-02**: System deduplicates entities using fuzzy matching (same entity, different surface forms)
- [x] **GRAPH-03**: System stores the knowledge graph in KuzuDB (pip-installable embedded graph database)
- [x] **GRAPH-04**: System links graph entities back to source chunks for citation retrieval

### Query & Answer

- [x] **QUERY-01**: User can submit a natural language question and receive a synthesized answer
- [x] **QUERY-02**: System retrieves relevant chunks via vector similarity (local search)
- [x] **QUERY-03**: System augments retrieval with graph-traversal context (entity neighborhood expansion)
- [x] **QUERY-04**: Every answer includes source citations (document name, page/slide reference)
- [x] **QUERY-05**: LLM answer generation uses local model via LM Studio (Qwen2.5 7B q4 or equivalent)

### Chat UI

- [x] **UI-01**: User can interact with the system via a browser-based Streamlit chat interface
- [x] **UI-02**: Chat history is maintained within a session (user sees previous Q&A pairs)

### Multi-Provider LLM & Embedding Configuration

- [x] **PROVIDER-01**: System reads LLM provider, model, and API key from `.env` file; defaults to LM Studio if `.env` absent or keys unset
- [x] **PROVIDER-02**: System supports LM Studio, Ollama, Gemini, OpenAI, and Anthropic as LLM providers via LiteLLM adapter
- [x] **PROVIDER-03**: System reads embedding provider, model, and API key from `.env` file; defaults to LM Studio if `.env` absent or keys unset
- [x] **PROVIDER-04**: System supports LM Studio, Ollama, Gemini, and OpenAI as embedding providers via LiteLLM adapter
- [x] **PROVIDER-05**: Changing LLM provider requires no code changes — only `.env` update
- [x] **PROVIDER-06**: Embedding provider switch warns user that re-running the embed step is required; existing corpus built with a different model is not silently re-used

## v2 Requirements

### Ingestion

- **INGEST-V2-01**: System skips already-indexed documents on re-run (incremental indexing)
- **INGEST-V2-02**: System flags content containing tables or diagrams for manual review in query output

### Knowledge Graph

- **GRAPH-V2-01**: Community detection clusters entities into themes for global synthesis queries
- **GRAPH-V2-02**: Graph explosion guard enforces entity type whitelist, confidence threshold, and per-document caps

### Chat UI

- **UI-V2-01**: User can filter query results by document type, date range, or keyword
- **UI-V2-02**: User can give thumbs up/down feedback on answers for quality tracking

### Performance

- **PERF-V2-01**: System profiles and optimizes indexing throughput to handle 2000+ documents
- **PERF-V2-02**: VRAM monitoring alerts user if model combination approaches 4GB ceiling

## Out of Scope

| Feature | Reason |
|---------|--------|
| Image/visual embeddings (colqwen2.5 etc.) | v1 failure — 5 min/page made full corpus indexing infeasible |
| Cloud or external API calls | Firewall-restricted corporate laptop; air-gap friendly required |
| Multi-user authentication | Single-user tool; no shared infrastructure |
| Structured parsing of tables/charts as data | Too brittle on diverse consulting formats; manual review instead |
| Real-time document sync / file watching | Batch ingestion sufficient for consulting workflow |
| Fine-tuning or training models | Out of scope for this phase; local inference only |
| Any package requiring non-pip installation | Corporate firewall blocks conda, Docker, system packages |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INGEST-01 | Phase 1 | Complete |
| INGEST-02 | Phase 1 | Complete |
| INGEST-03 | Phase 1 | Complete |
| EMBED-01 | Phase 2 | Complete |
| EMBED-02 | Phase 2 | Complete |
| EMBED-03 | Phase 2 | Complete |
| GRAPH-01 | Phase 3 | Complete |
| GRAPH-02 | Phase 3 | Complete |
| GRAPH-03 | Phase 3 | Complete |
| GRAPH-04 | Phase 3 | Complete |
| QUERY-01 | Phase 4 | Complete |
| QUERY-02 | Phase 4 | Complete |
| QUERY-03 | Phase 4 | Complete |
| QUERY-04 | Phase 4 | Complete |
| QUERY-05 | Phase 4 | Complete |
| UI-01 | Phase 5 | Complete |
| UI-02 | Phase 5 | Complete |
| PROVIDER-01 | Phase 6 | Planned |
| PROVIDER-02 | Phase 6 | Planned |
| PROVIDER-03 | Phase 6 | Planned |
| PROVIDER-04 | Phase 6 | Planned |
| PROVIDER-05 | Phase 6 | Planned |
| PROVIDER-06 | Phase 6 | Planned |
