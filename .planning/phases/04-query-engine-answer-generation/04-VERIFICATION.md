---
phase: 04-query-engine-answer-generation
verified: 2026-03-31T00:00:00Z
status: human_needed
score: 4/5 must-haves verified
re_verification: false
human_verification:
  - test: "Live end-to-end query test with LM Studio running"
    expected: "Answer returned in < 15 seconds with inline [N] citations and citation table; latency printed to stdout"
    why_human: "SC-5 (query latency < 15s) and SC-3 (real LLM generation) require LM Studio running with Qwen2.5-7B-Instruct loaded — cannot verify without live service"
---

# Phase 4: Query Engine & Answer Generation — Verification Report

**Phase Goal:** Consultant submits a natural language question and receives a synthesized answer drawn from the knowledge graph and vector store, with source citations.
**Verified:** 2026-03-31
**Status:** HUMAN_NEEDED (4/5 automated checks pass; SC-5 latency requires live LM Studio)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | System accepts natural language questions and retrieves relevant chunks via vector similarity | VERIFIED | `vector_search()` in `retriever.py` calls `embed_query()` then `collection.query()` with cosine distance; test `test_vector_search_returns_chunks` passes |
| 2 | System augments vector retrieval with entity-based graph traversal (1-hop expansion) | VERIFIED | `graph_expand()` in `retriever.py` calls `_get_entities_for_chunks()` -> `_get_neighbors()` (1-hop KuzuDB MATCH) -> `_hydrate_graph_chunks()`; `hybrid_retrieve()` combines both; test `test_graph_expansion_finds_neighbors` and `test_hybrid_retrieve_combines_sources` pass |
| 3 | System synthesizes a coherent answer using LM Studio LLM (Qwen2.5-7B-Instruct or equivalent) | VERIFIED (mocked) | `answer_question()` in `pipeline.py` calls `openai_client.chat.completions.create(model=llm_model, ...)` with default `DEFAULT_LLM_MODEL = "Qwen2.5-7B-Instruct"`; live generation requires human test |
| 4 | Every answer includes source citations with HIGH/LOW confidence | VERIFIED | `build_citations()` counts (filename, page_num) appearances; threshold >= 3 = HIGH, 1-2 = LOW; `format_answer()` appends citation table; tests `test_citation_confidence_high`, `test_citation_confidence_low`, `test_format_answer_with_citations` all pass |
| 5 | Query latency < 15 seconds (retrieve + generate) | NEEDS HUMAN | `elapsed_s` is measured via `time.perf_counter()` and returned + printed; actual latency depends on live LM Studio + Qwen2.5-7B-Instruct — cannot measure without running service |

**Score:** 4/5 truths fully verified (SC-5 needs live measurement)

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/query/retriever.py` | `hybrid_retrieve()`, `vector_search()`, `graph_expand()` | VERIFIED | 369 lines; all 4 public functions present and substantive; no stubs |
| `src/query/assembler.py` | `truncate_to_budget()`, `build_citations()`, `format_answer()`, `build_prompt()` | VERIFIED | 180 lines; all 4 functions present and substantive; tiktoken token budget enforced |
| `src/query/pipeline.py` | `answer_question()` wiring all components | VERIFIED | 128 lines; full orchestration: hybrid_retrieve -> truncate_to_budget -> build_prompt -> LLM -> build_citations -> format_answer |
| `src/main.py` | `query` subcommand with all 7 args | VERIFIED | `cmd_query()` present; query subparser registers `--question`, `--db`, `--chroma`, `--graph`, `--embed-model`, `--llm-model`, `--top-k` |
| `tests/test_query_retriever.py` | 4 tests covering QUERY-02, QUERY-03 | VERIFIED | 4 tests present and passing |
| `tests/test_query_assembler.py` | 4 tests covering QUERY-04 | VERIFIED | 4 tests present and passing |
| `tests/test_query_pipeline.py` | 2 non-lm_studio tests covering QUERY-01, QUERY-05 | VERIFIED | 2 unit tests pass; lm_studio integration test appropriately marked xfail |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `pipeline.answer_question` | `retriever.hybrid_retrieve` | direct import, called at line 87 | WIRED | Passes all 8 required args including `citation_store`, `kuzu_db`, `sqlite_conn` |
| `pipeline.answer_question` | `assembler.truncate_to_budget` | direct import, called at line 100 | WIRED | Receives `chunks` list from hybrid_retrieve |
| `pipeline.answer_question` | `assembler.build_prompt` | direct import, called at line 104 | WIRED | Receives `question` and `context_str` |
| `pipeline.answer_question` | `openai_client.chat.completions.create` | called at line 109 | WIRED | Uses `llm_model`, `messages`, `temperature=0.2`, `max_tokens=600` |
| `pipeline.answer_question` | `assembler.build_citations` | direct import, called at line 118 | WIRED | Receives `included_chunks` from truncate_to_budget |
| `pipeline.answer_question` | `assembler.format_answer` | direct import, called at line 119 | WIRED | Receives `llm_response` + `citations` |
| `retriever.hybrid_retrieve` | `embedder.embed_query` | import at module level, called in `vector_search()` | WIRED | Embedding call properly handled |
| `retriever.graph_expand` | `citations.CitationStore.get_chunks_for_entity` | called at line 295 | WIRED | Entity-to-chunk lookup in SQLite |
| `main.cmd_query` | `pipeline.answer_question` | import inside `cmd_query()`, called at line 228 | WIRED | Passes `args.question`, `conn`, `db`, all CLI args |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `pipeline.answer_question` | `chunks` | `hybrid_retrieve()` -> ChromaDB + KuzuDB | Yes — real DB queries against ChromaDB collection and KuzuDB graph | FLOWING |
| `pipeline.answer_question` | `llm_response` | `openai_client.chat.completions.create()` | Yes for live; mocked in tests | FLOWING (live requires LM Studio) |
| `pipeline.answer_question` | `citations` | `build_citations(included_chunks)` | Yes — derived from actual included chunks | FLOWING |
| `assembler.format_answer` | `citations` | `build_citations()` counter on real chunk data | Yes | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `query` subcommand is registered in CLI | `python src/main.py query --help` | Shows all 7 args: `--question`, `--db`, `--chroma`, `--graph`, `--embed-model`, `--llm-model`, `--top-k` | PASS |
| `pipeline` module imports cleanly | `python -c "from src.query.pipeline import answer_question; print('pipeline import OK')"` | `pipeline import OK` | PASS |
| Full test suite (excluding lm_studio) | `python -m pytest tests/ -x -q -k "not lm_studio" --tb=short` | `31 passed, 2 deselected, 37 xpassed in 17.96s` | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| QUERY-01 | 04-04 | User can submit a natural language question and receive a synthesized answer | SATISFIED | `answer_question()` in `pipeline.py`; `cmd_query()` in `main.py`; `test_query_pipeline_end_to_end` passes |
| QUERY-02 | 04-02 | System retrieves relevant chunks via vector similarity | SATISFIED | `vector_search()` in `retriever.py` uses ChromaDB cosine search; `test_vector_search_returns_chunks` passes |
| QUERY-03 | 04-02 | System augments retrieval with graph-traversal context | SATISFIED | `graph_expand()` performs 1-hop KuzuDB traversal; `test_graph_expansion_finds_neighbors` and `test_hybrid_retrieve_combines_sources` pass |
| QUERY-04 | 04-03 | Every answer includes source citations with HIGH/LOW confidence | SATISFIED | `build_citations()` + `format_answer()` in `assembler.py`; 3 citation tests pass; citation table always appended |
| QUERY-05 | 04-04 | LLM answer generation uses local model via LM Studio | SATISFIED (mocked) | `openai_client.chat.completions.create(model="Qwen2.5-7B-Instruct")` called in `pipeline.py`; live test requires human verification |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/test_query_pipeline.py:175` | 175 | `raise NotImplementedError` in `test_lm_studio_integration` | Info | Intentional — test is `@pytest.mark.lm_studio` + `@pytest.mark.xfail`; excluded from CI with `-k "not lm_studio"`; not a blocker |

No blocker or warning anti-patterns found. The `NotImplementedError` in the lm_studio test is a deliberate placeholder for a live integration test, properly marked for exclusion.

---

## Human Verification Required

### 1. Live LM Studio End-to-End Query Test (SC-3, SC-5)

**Test:** With LM Studio running at `localhost:1234` and `Qwen2.5-7B-Instruct` loaded as the LLM (plus `nomic-embed-text-v1.5` as the embedding model), run:

```bash
python src/main.py query --question "What EV proposals have we written?" --db data/chunks.db --chroma data/chroma_db --graph data/kuzu_db
```

**Expected:**
- Answer is returned (non-empty text with inline `[N]` citation references)
- A `Citations:` section appears after the answer listing each source with `(HIGH)` or `(LOW)` confidence
- The final line prints `Query completed in X.Xs` where X.X < 15.0
- No stack traces or error messages

**Why human:** SC-5 (latency < 15 seconds) requires a live LM Studio instance with a loaded model. The pipeline code measures and returns `elapsed_s` but the measurement is only meaningful against the real LLM. The `test_lm_studio_integration` test is intentionally marked `@pytest.mark.lm_studio @pytest.mark.xfail` for this purpose.

**To also verify SC-3 specifically:** Confirm the model named in the answer footer or output matches `Qwen2.5-7B-Instruct` (or your loaded equivalent). The default is hardcoded as `DEFAULT_LLM_MODEL = "Qwen2.5-7B-Instruct"` in `pipeline.py`.

---

## Gaps Summary

No implementation gaps found. All five Phase 4 source files exist, are substantive, and are fully wired. The automated test suite passes with 31 tests (10 of which are Phase 4 query tests). The only open item is the latency requirement (SC-5) which is structurally implemented — `elapsed_s` is measured with `time.perf_counter()` and printed by the CLI — but cannot be validated to be under 15 seconds without running LM Studio.

The `test_lm_studio_integration` test exists in `tests/test_query_pipeline.py` and will serve as the formal verification vehicle once LM Studio is available. Currently it raises `NotImplementedError` as a deliberate stub.

---

_Verified: 2026-03-31_
_Verifier: Claude (gsd-verifier)_
