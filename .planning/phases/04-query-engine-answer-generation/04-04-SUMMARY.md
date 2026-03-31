---
phase: 04-query-engine-answer-generation
plan: "04"
subsystem: query
tags: [pipeline, cli, orchestration, answer-generation, hybrid-retrieval]
dependency_graph:
  requires: [04-02, 04-03]
  provides: [answer_question, cmd_query]
  affects: [src/main.py]
tech_stack:
  added: []
  patterns: [openai-client-injection, chroma-client-injection, stateless-pipeline]
key_files:
  created: [src/query/pipeline.py]
  modified: [src/main.py, tests/test_query_pipeline.py]
decisions:
  - "Accept chroma_client as optional injection parameter so tests can pass EphemeralClient without touching disk"
  - "Set included_chunks empty guard before LLM call to return informative no-results message without hitting LM Studio"
metrics:
  duration_minutes: 15
  tasks_completed: 2
  files_changed: 3
  completed_date: "2026-03-31"
---

# Phase 4 Plan 04: Pipeline and CLI Summary

**One-liner:** Query pipeline orchestrating hybrid_retrieve -> truncate_to_budget -> build_prompt -> LM Studio LLM -> format_answer, exposed via `python src/main.py query --question "..."`.

## What Was Implemented

### src/query/pipeline.py
- `answer_question(question, conn, kuzu_db, chroma_path, embed_model, llm_model, n_results, openai_client, chroma_client)` — full orchestration function
- Opens `chromadb.PersistentClient` from `chroma_path` if `chroma_client` is not injected (supports test injection of `EphemeralClient`)
- Creates `CitationStore(conn)` and calls `hybrid_retrieve()` with all required parameters
- Calls `truncate_to_budget()` -> `build_prompt()` -> LM Studio chat completion -> `build_citations()` -> `format_answer()`
- Guards empty corpus: skips LLM call when `included_chunks` is empty, returns informative message directly
- Returns `{answer: str, citations: list[dict], elapsed_s: float}`
- Stateless: fresh OpenAI client and fresh messages list per call, no history accumulation
- Exports `DEFAULT_LLM_MODEL = "Qwen2.5-7B-Instruct"` and `DEFAULT_EMBED_MODEL = "nomic-embed-text-v1.5"`

### src/main.py
- `cmd_query()` function added after `cmd_graph()`, following same pattern: path validation, `check_lm_studio()` health check, `sqlite3.connect()`, `kuzu.Database()`, `try/finally conn.close()`
- `query` subparser registered with 7 arguments: `--question`, `--db`, `--chroma`, `--graph`, `--embed-model`, `--llm-model`, `--top-k`
- `python src/main.py --help` shows all 5 subcommands: ingest, stats, embed, graph, query

### tests/test_query_pipeline.py
- `test_query_pipeline_end_to_end`: xfail removed; uses `chromadb.EphemeralClient()`, temporary KuzuDB, mocked `openai_client` returning fake embedding and fake LLM response; asserts result has `answer`, `citations`, `elapsed_s` keys with correct types
- `test_query_pipeline_no_results`: xfail removed; empty ChromaDB corpus; asserts `citations == []` and answer contains "not contain sufficient information"
- `test_lm_studio_integration`: remains `@pytest.mark.lm_studio` + `@pytest.mark.xfail` until live LM Studio session

## Test Results

```
tests/test_query_retriever.py::test_vector_search_returns_chunks PASSED
tests/test_query_retriever.py::test_graph_expansion_finds_neighbors PASSED
tests/test_query_retriever.py::test_dedup_merged_chunks PASSED
tests/test_query_retriever.py::test_hybrid_retrieve_combines_sources PASSED
tests/test_query_assembler.py::test_assemble_context_respects_token_budget PASSED
tests/test_query_assembler.py::test_citation_confidence_high PASSED
tests/test_query_assembler.py::test_citation_confidence_low PASSED
tests/test_query_assembler.py::test_format_answer_with_citations PASSED
tests/test_query_pipeline.py::test_query_pipeline_end_to_end PASSED
tests/test_query_pipeline.py::test_query_pipeline_no_results PASSED

10 passed, 1 deselected (lm_studio xfail skipped as expected)

Full suite: 31 passed, 2 deselected, 37 xpassed, 0 failures
```

## Commits

- `57c8949` — feat(04-04): implement answer_question() pipeline and enable pipeline tests
- `22fa60b` — feat(04-04): add query subcommand to CLI with 7 arguments

## Human Verification Required

Start LM Studio with your LLM model (e.g., qwen2.5-vl-7b-instruct), then run:

```bash
# Verify CLI help works
python src/main.py query --help

# Test query with your real data (LM Studio must be running)
python src/main.py query --question "What EV proposals have we written?" --model qwen2.5-vl-7b-instruct

# If LM Studio not available, verify pipeline loads correctly
python -c "from src.query.pipeline import answer_question; print('pipeline import OK')"
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ChromaDB client injection for testability**
- **Found during:** Task 1 (test implementation)
- **Issue:** `hybrid_retrieve()` requires a `chroma_client` object, but the plan's `answer_question()` signature only accepted `chroma_path: str`. Tests need `EphemeralClient` to avoid disk I/O.
- **Fix:** Added optional `chroma_client=None` parameter to `answer_question()`. Creates `chromadb.PersistentClient(path=chroma_path)` when not injected; uses provided client in tests.
- **Files modified:** `src/query/pipeline.py`
- **Commit:** `57c8949`

**2. [Rule 1 - Bug] KuzuDB Windows temp directory handling**
- **Found during:** Task 1 test run
- **Issue:** KuzuDB on Windows raises `RuntimeError: Database path cannot be a directory` when given a pre-created empty directory. Tests used `os.makedirs(kuzu_dir)` before `kuzu.Database(kuzu_dir)`.
- **Fix:** Removed `os.makedirs()` call; pass non-existent path directly to `kuzu.Database()` (it creates its own directory). Added `del kuzu_db` before temp dir cleanup to release file handles on Windows.
- **Files modified:** `tests/test_query_pipeline.py`
- **Commit:** `57c8949`

## Known Stubs

None — `answer_question()` is fully wired. The `test_lm_studio_integration` test remains xfail intentionally, pending a live LM Studio smoke test by the user.
