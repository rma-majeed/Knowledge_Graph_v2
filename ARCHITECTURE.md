# Automotive Consulting GraphRAG v2 — Architecture

## System Overview

A hybrid Retrieval-Augmented Generation (RAG) system that ingests automotive consulting
documents, builds a knowledge graph and vector store, then answers questions through a
10-step retrieval pipeline exposed via a Streamlit UI and a Google ADK multi-agent API.

---

## Tech Stack

| Layer | Technology | Version |
|---|---|---|
| Document extraction | PyMuPDF, python-pptx | 1.27+, 1.0+ |
| Chunking | tiktoken (cl100k_base, 512 tok / 100 overlap) | 0.12+ |
| Relational store | SQLite (WAL mode) | built-in |
| Vector store | ChromaDB (cosine HNSW) | 1.5.5 |
| Knowledge graph | KuzuDB | 0.11.3 |
| Embeddings | LM Studio → nomic-embed-text-v1.5 | — |
| LLM | LM Studio → Qwen2.5 / Gemma (OpenAI-compat.) | — |
| Multi-provider routing | LiteLLM | 1.83+ |
| Keyword search | rank-bm25 | 0.2.2 |
| Entity deduplication | RapidFuzz | 3.14+ |
| Cross-encoder reranker | BGE reranker-v2-m3 (sentence-transformers) | 5.0+ |
| Multi-agent framework | Google ADK | 1.28+ |
| Web UI | Streamlit | 1.55+ |

---

## Data Flow — Offline Pipelines

```
┌─────────────────────────────────────────────────────────┐
│                    Ingest_Documents/                     │
│                  (PDF / PPTX files)                      │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   1. INGEST PIPELINE   │
              │   src/ingest/          │
              │                        │
              │  pdf_extractor.py      │  PyMuPDF
              │  pptx_extractor.py     │  python-pptx
              │  chunker.py            │  tiktoken (512 tok)
              │  enricher.py           │  LLM context summary
              │  store.py              │  SQLite writer
              └────────────┬───────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   data/chunks.db       │  SQLite
              │                        │
              │   documents            │  filename, hash, pages
              │   chunks               │  chunk_text, enriched_text
              │   chunk_parents        │  3-chunk sliding window
              │   chunk_citations      │  entity ↔ chunk links
              └───────┬────────┬───────┘
                      │        │
          ┌───────────┘        └──────────────┐
          ▼                                   ▼
┌──────────────────────┐         ┌───────────────────────┐
│  2. EMBED PIPELINE   │         │  3. GRAPH PIPELINE    │
│  src/embed/          │         │  src/graph/           │
│                      │         │                       │
│  embedder.py         │         │  extractor.py         │
│  → nomic-embed-text  │         │  → LLM extracts       │
│  vector_store.py     │         │    entities +         │
│  → ChromaDB upsert   │         │    relationships      │
│                      │         │  deduplicator.py      │
│  Uses enriched_text  │         │  → RapidFuzz fuzzy    │
│  when enrichment     │         │    dedup              │
│  is enabled          │         │  db_manager.py        │
└──────────┬───────────┘         │  → KuzuDB writer      │
           │                     └──────────┬────────────┘
           ▼                                ▼
┌─────────────────────┐        ┌────────────────────────┐
│  data/chroma_db/    │        │   data/kuzu_db/        │
│                     │        │                        │
│  collection: chunks │        │  Nodes:                │
│  768-dim vectors    │        │    OEM, Supplier        │
│  cosine HNSW        │        │    Technology, Product  │
│  + metadata         │        │    Recommendation       │
│    filename         │        │                        │
│    page_num         │        │  Edges:                │
│    chunk_index      │        │    USES, PRODUCES       │
└─────────────────────┘        │    IS_A, RECOMMENDS    │
                               └────────────────────────┘
```

---

## Query Flow — 10-Step RAG Pipeline

```
User Question
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│               src/query/pipeline.py                      │
│                                                         │
│  Step 1 │ Query Rewrite      conversation history       │
│         │ → self-contained question for multi-turn      │
│         │                                               │
│  Step 2 │ Query Expansion    LLM generates 3 variants   │
│         │ → broader retrieval coverage                  │
│         │                                               │
│  Step 3a│ Vector Search      ChromaDB cosine HNSW       │
│         │ → semantic similarity per query variant       │
│         │                                               │
│  Step 3b│ BM25 Search        rank-bm25 in-memory index  │
│  (opt)  │ → exact keyword matching per query variant    │
│         │                                               │
│  Step 3c│ RRF Fusion         Reciprocal Rank Fusion     │
│         │ → merge BM25 + vector ranked lists            │
│         │                                               │
│  Step 4 │ Graph Expansion    KuzuDB traversal           │
│         │ → find entity neighbours, fetch their chunks  │
│         │                                               │
│  Step 4b│ BGE Reranker       cross-encoder scoring      │
│  (opt)  │ → re-score (query, chunk) pairs               │
│         │                                               │
│  Step 4c│ Parent-Doc         3-chunk sliding window     │
│  (opt)  │ → expand chunks to wider context passages     │
│         │                                               │
│  Step 5 │ Context Assembly   token budget truncation    │
│         │ → fit within 3000 token LLM context           │
│         │                                               │
│  Step 6 │ LLM Generation     OpenAI-compat. API         │
│         │ → answer with inline [N] citations            │
│         │                                               │
│  Step 7 │ Citation Builder   filename + page_num table  │
│         │ → HIGH/LOW confidence + source counts         │
└─────────────────────────────────────────────────────────┘
      │
      ▼
  Answer + Citations
```

**RAG Feature Flags** (`src/config/retrieval_config.py`):

| Flag | Default | Effect |
|---|---|---|
| `RAG_ENABLE_BM25` | `true` | BM25 + RRF fusion (Step 3b/3c) |
| `RAG_ENABLE_RERANKER` | `true` | BGE cross-encoder (Step 4b) — requires model download |
| `RAG_ENABLE_PARENT_DOC` | `true` | 3-chunk parent expansion (Step 4c) |
| `RAG_ENABLE_ENRICHMENT` | `true` | LLM context summary at ingest (requires re-ingest) |

---

## Google ADK Multi-Agent Architecture

```
                    adk web  (port 8000)
                         │
                         ▼
        ┌────────────────────────────────────┐
        │      graphrag_master_agent          │
        │      GraphRAG_Factory/agent.py      │
        │                                    │
        │  Model: LiteLLM → LM Studio        │
        │  Tools: passthrough_citations()     │
        │                                    │
        │  ROUTING:                          │
        │  single topic / general Q&A        │
        │    → pipeline_rag_agent            │
        │  multi-part / compare / entities   │
        │    → search_rag_agent              │
        └────────────┬───────────────────────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
┌─────────────────┐    ┌──────────────────────┐
│ pipeline_rag    │    │  search_rag_agent     │
│ _agent          │    │  (Phase 2)            │
│                 │    │                       │
│ 1 tool:         │    │  5 tools:             │
│ full_rag_query()│    │  vector_search()      │
│ append_         │    │  bm25_search()        │
│   citations()   │    │  graph_search()       │
│                 │    │  rerank()             │
│ Runs the full   │    │  format_citations()   │
│ 10-step pipeline│    │                       │
│ via             │    │  Agent picks tools    │
│ answer_question │    │  based on query type  │
│ ()              │    │                       │
└────────┬────────┘    └──────────┬────────────┘
         │                        │
         └──────────┬─────────────┘
                    ▼
        ┌───────────────────────┐
        │   db_singletons.py    │
        │ (shared process-wide) │
        │                       │
        │  KuzuDB  — 1 handle   │
        │  SQLite  — 1 handle   │
        │  ChromaDB— 1 handle   │
        └───────────────────────┘
```

> **Note:** Both sub-agents share DB handles via `GraphRAG_Factory/db_singletons.py`.
> KuzuDB only permits one `Database` instance per process — the singleton prevents
> file lock conflicts when both agents are loaded under `adk web`.

---

## User Interfaces

```
┌──────────────────────────┐    ┌───────────────────────────┐
│   Streamlit UI           │    │   Google ADK Web UI       │
│   app.py                 │    │   adk web                 │
│                          │    │                           │
│  streamlit run app.py    │    │  cd GraphRAG_Factory      │
│  → localhost:8501        │    │  adk web                  │
│                          │    │  → localhost:8000         │
│  Direct pipeline access  │    │                           │
│  Multi-turn chat         │    │  Multi-agent routing      │
│  Streaming responses     │    │  Tool call visibility     │
│  Citation table display  │    │  ADK session management   │
└──────────────────────────┘    └───────────────────────────┘
         │                                   │
         └──────────────┬────────────────────┘
                        ▼
             src/query/pipeline.py
             answer_question() / stream_answer_question()
```

---

## File Structure

```
Knowledge_Graph_v2/
│
├── app.py                          # Streamlit chat UI
├── requirements.txt
├── .env                            # Provider config + feature flags
├── .env.example                    # Template
├── CLAUDE.md                       # Dev guidance
│
├── src/
│   ├── main.py                     # CLI: ingest / embed / graph / query
│   ├── config/
│   │   ├── providers.py            # LLM + embed provider factory
│   │   └── retrieval_config.py     # RAG feature flags
│   ├── ingest/
│   │   ├── pdf_extractor.py        # PyMuPDF page extraction
│   │   ├── pptx_extractor.py       # python-pptx slide extraction
│   │   ├── chunker.py              # tiktoken chunking (512/100)
│   │   ├── enricher.py             # LLM context summary generation
│   │   ├── store.py                # SQLite CRUD + parent window builder
│   │   └── pipeline.py             # End-to-end ingest orchestration
│   ├── embed/
│   │   ├── embedder.py             # Batch embed via OpenAI-compat. API
│   │   ├── vector_store.py         # ChromaDB upsert wrapper
│   │   └── pipeline.py             # Embed loop (enriched_text aware)
│   ├── graph/
│   │   ├── extractor.py            # LLM entity/relationship extraction
│   │   ├── deduplicator.py         # RapidFuzz entity dedup
│   │   ├── db_manager.py           # KuzuDB schema + node/edge writer
│   │   └── citations.py            # chunk ↔ entity citation store
│   ├── query/
│   │   ├── pipeline.py             # answer_question() — 10-step RAG
│   │   ├── retriever.py            # vector_search + graph_expand
│   │   ├── bm25_index.py           # BM25Indexer (rank-bm25 wrapper)
│   │   ├── rrf.py                  # Reciprocal Rank Fusion
│   │   ├── reranker.py             # BGE cross-encoder singleton
│   │   └── assembler.py            # Context truncation + citation builder
│   └── db/
│       └── schema.sql              # SQLite schema (authoritative)
│
├── GraphRAG_Factory/               # Google ADK multi-agent system
│   ├── agent.py                    # Master orchestrator
│   ├── db_singletons.py            # Shared KuzuDB/SQLite/ChromaDB handles
│   └── sub_agents/
│       ├── pipeline_rag_agent/
│       │   ├── agent.py            # Full pipeline sub-agent
│       │   └── tools/
│       │       └── pipeline_tools.py  # full_rag_query + append_citations
│       └── search_rag_agent/
│           ├── agent.py            # Targeted search sub-agent
│           └── tools/
│               └── search_tools.py   # 5 individual search tools
│
├── data/                           # Runtime data (git-ignored)
│   ├── chunks.db                   # SQLite
│   ├── chroma_db/                  # ChromaDB vectors
│   └── kuzu_db/                    # KuzuDB knowledge graph
│
├── tests/                          # pytest test suite
└── download_reranker_clean.py      # BGE model download helper
```

---

## Setup & Run Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env   # then edit .env

# --- Offline pipelines (run once, in order) ---
python src/main.py ingest --path Ingest_Documents/   # extract + chunk + enrich
python src/main.py embed                              # embed chunks → ChromaDB
python src/main.py graph                             # extract entities → KuzuDB

# --- User interfaces ---
streamlit run app.py                    # Streamlit UI  → localhost:8501

cd GraphRAG_Factory && adk web          # ADK agent UI  → localhost:8000

# --- Tests ---
pytest tests/                                         # all tests
pytest tests/ -m "not integration and not lm_studio"  # fast tests only
```
