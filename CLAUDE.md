# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automotive Consulting GraphRAG v2 — a hybrid retrieval-augmented generation system that ingests PDF/PPTX documents, builds a knowledge graph (KuzuDB), embeds chunks into ChromaDB, then answers questions via a 10-step hybrid pipeline (BM25 + vector + graph + reranker).

## Common Commands

```bash
# Run the Streamlit web UI
streamlit run app.py

# CLI: ingest documents
python src/main.py ingest --path Ingest_Documents/

# CLI: embed chunks
python src/main.py embed

# CLI: build knowledge graph
python src/main.py graph

# CLI: query
python src/main.py query --question "Who are the key OEM suppliers?"

# Run all tests
pytest tests/

# Run only fast (non-integration) tests
pytest tests/ -m "not integration and not lm_studio"

# Run a single test file
pytest tests/test_query_pipeline.py -v

# Generate test fixtures (sample PDF/PPTX)
python tests/fixtures/make_fixtures.py
```

## Architecture

Data flows through four sequential pipelines, each persisting to disk:

```
PDF/PPTX → [Ingest] → SQLite (chunks.db)
                   → [Embed] → ChromaDB (chroma_db/)
                   → [Graph] → KuzuDB (kuzu_db/)
                   → [Query] → answer + citations
```

### Pipeline Modules (`src/`)

| Module | Responsibility |
|--------|---------------|
| `ingest/` | Extract text from PDF (PyMuPDF) / PPTX (python-pptx), chunk with tiktoken (512 tokens, 100 overlap), optionally enrich chunks via LLM, persist to SQLite |
| `embed/` | Load unembed chunks from SQLite, batch-embed via configured provider, store in ChromaDB |
| `graph/` | Extract entities/relationships from chunks via LLM, deduplicate with RapidFuzz, persist to KuzuDB, track chunk-entity citations |
| `query/` | `answer_question()` — full 10-step RAG: query expansion → BM25 → vector → RRF → graph expansion → BGE reranker → parent-doc expansion → context assembly → LLM generation → citation building |
| `config/` | Multi-provider factory (`providers.py`) and feature flags (`retrieval_config.py`) |

### Key Files

- `src/query/pipeline.py` — `answer_question()` and `stream_answer_question()` — the main query entrypoint
- `src/config/retrieval_config.py` — feature flags: `USE_BM25`, `USE_RERANKER`, `USE_GRAPH_EXPANSION`, `USE_PARENT_DOC_EXPANSION`
- `src/config/providers.py` — LLM/embedding provider dispatch (lm-studio, ollama, gemini, openai, anthropic)
- `app.py` — Streamlit UI; caches DB connections via `@st.cache_resource`

### Data Stores

- `data/chunks.db` — SQLite: `documents`, `chunks`, `chunk_citations` tables
- `data/chroma_db/` — ChromaDB: one collection `documents` with 768-dim or 1536-dim vectors
- `data/kuzu_db/` — KuzuDB: nodes (`OEM`, `Supplier`, `Technology`, `Product`, `Regulation`), directed edges with chunk citation links
- `data/extraction_state.json` — checkpoint for incremental graph extraction

## Configuration

Copy `.env.example` to `.env`. Defaults run against LM Studio on `localhost:1234`:

```env
LLM_PROVIDER=lm-studio        # lm-studio | ollama | gemini | openai | anthropic
LLM_MODEL=Qwen2.5-7B-Instruct
EMBED_PROVIDER=lm-studio
EMBED_MODEL=nomic-embed-text-v1.5
```

## Testing Notes

- `conftest.py` resets ChromaDB `EphemeralClient` between tests; never share a real ChromaDB instance across test cases
- Mark slow/network tests with `@pytest.mark.integration` or `@pytest.mark.lm_studio` — CI runs with `-m "not integration and not lm_studio"`
- `tests/fixtures/` contains pre-generated sample files; regenerate with `make_fixtures.py` if fixture format changes

## Next Phase: Agentic RAG

`AGENTIC_RAG_ARCHITECTURE.md` specifies the planned Google ADK multi-agent upgrade. The existing 10-step pipeline becomes tools called by ADK agents (Orchestrator, QueryRewriter, Retrieval, QualityEvaluator, Reasoning). Follow `.claude/rules/adk-agent-patterns.md` and `.claude/rules/adk-folder-structure.md` when implementing.
