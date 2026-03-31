# Phase 4 Validation Strategy: Query Engine & Answer Generation

**Phase:** 04-query-engine-answer-generation
**Requirements:** QUERY-01, QUERY-02, QUERY-03, QUERY-04, QUERY-05
**Created:** 2026-03-31

---

## Test Files

| File | Covers | Plans |
|------|--------|-------|
| `tests/test_query_retriever.py` | QUERY-02, QUERY-03 | 04-01 (stubs), 04-02 (implementation) |
| `tests/test_query_assembler.py` | QUERY-04 | 04-01 (stubs), 04-03 (implementation) |
| `tests/test_query_pipeline.py` | QUERY-01, QUERY-05 | 04-01 (stubs), 04-04 (implementation) |

---

## Run Commands

### Quick Run (exclude LM Studio integration test)
```bash
pytest tests/test_query_retriever.py tests/test_query_assembler.py tests/test_query_pipeline.py -x -q -k "not lm_studio"
```
Expected: 10 tests collected, all PASS after Wave 3 complete. 1 test deselected (lm_studio).

### Full Suite (all phases, exclude lm_studio)
```bash
pytest tests/ -x -q -k "not lm_studio"
```
Expected: All prior-phase tests still GREEN plus the 10 new query tests.

### LM Studio Integration (requires LM Studio running with Qwen2.5-7B-Instruct)
```bash
pytest tests/test_query_pipeline.py -x -q -k "lm_studio" -v
```
Expected: `test_lm_studio_integration` PASSES if LM Studio is running with correct model. XFAIL otherwise.

### Verbose Output (for debugging a specific test)
```bash
pytest tests/test_query_retriever.py::test_hybrid_retrieve_combines_sources -v --tb=long
```

---

## Per-Task Verification Map

### Plan 04-01 — Test Infrastructure (Wave 1)

| Task | Verification Command | Expected |
|------|---------------------|---------|
| Task 1: src/query stubs + lm_studio marker | `python -c "from src.query.pipeline import answer_question; print('OK')"` | exits 0 |
| Task 2: xfail test stubs | `pytest tests/test_query_retriever.py tests/test_query_assembler.py tests/test_query_pipeline.py -x -q -k "not lm_studio"` | 10 xfailed, 0 errors |

### Plan 04-02 — Hybrid Retriever (Wave 2)

| Task | Verification Command | Expected |
|------|---------------------|---------|
| Task 1: retriever.py implementation | `pytest tests/test_query_retriever.py -x -q --tb=short` | 4 PASSED |

Specific test-to-function mapping:
- `test_vector_search_returns_chunks` → `vector_search()` returns list with source='vector' key
- `test_graph_expansion_finds_neighbors` → `graph_expand()` 1-hop KuzuDB traversal + chunk hydration
- `test_dedup_merged_chunks` → `deduplicate_chunks()` removes by chunk_id, handles str/int normalisation
- `test_hybrid_retrieve_combines_sources` → `hybrid_retrieve()` = vector + graph + dedup

### Plan 04-03 — Assembler & Citations (Wave 2, parallel with 04-02)

| Task | Verification Command | Expected |
|------|---------------------|---------|
| Task 1: assembler.py implementation | `pytest tests/test_query_assembler.py -x -q --tb=short` | 4 PASSED |

Specific test-to-function mapping:
- `test_assemble_context_respects_token_budget` → `truncate_to_budget()` stops at 3000 tokens, vector-first sort
- `test_citation_confidence_high` → `build_citations()` HIGH for >= 3 same-source appearances
- `test_citation_confidence_low` → `build_citations()` LOW for 1-2 appearances
- `test_format_answer_with_citations` → `format_answer()` appends "Citations:" section

### Plan 04-04 — Pipeline & CLI (Wave 3)

| Task | Verification Command | Expected |
|------|---------------------|---------|
| Task 1: pipeline.py implementation | `pytest tests/test_query_pipeline.py -x -q -k "not lm_studio" --tb=short` | 2 PASSED, 1 xfailed |
| Task 2: query subcommand in main.py | `python src/main.py query --help` | shows all 7 args |
| Task 2: all subcommands intact | `python src/main.py --help` | shows ingest, stats, embed, graph, query |

---

## Wave 0 Requirements Checklist

Before any Wave 2 plan runs, verify Wave 1 is complete:

- [ ] `src/query/__init__.py` exists
- [ ] `src/query/retriever.py` exists with `raise NotImplementedError` stubs
- [ ] `src/query/assembler.py` exists with `CONTEXT_TOKEN_BUDGET = 3000` and `raise NotImplementedError` stubs
- [ ] `src/query/pipeline.py` exists with `raise NotImplementedError` stub
- [ ] `tests/test_query_retriever.py` exists with 4 xfail stubs
- [ ] `tests/test_query_assembler.py` exists with 4 xfail stubs
- [ ] `tests/test_query_pipeline.py` exists with 3 stubs (2 xfail + 1 lm_studio+xfail)
- [ ] `conftest.py` registers `lm_studio` marker (no PytestUnknownMarkWarning)
- [ ] `pytest tests/test_query_retriever.py tests/test_query_assembler.py tests/test_query_pipeline.py -x -q -k "not lm_studio"` exits 0 (xfail, not error)

---

## Manual Verification Items

These cannot be automated and require human judgement.

### After Plan 04-04 (Human Checkpoint)

1. **CLI smoke test** (requires live data from Phases 1-3):
   ```bash
   python src/main.py query \
     --question "What EV battery technologies appear in our consulting documents?" \
     --db data/chunks.db \
     --chroma data/chroma_db \
     --graph data/kuzu_db
   ```
   Verify:
   - Answer is coherent English prose (not JSON, not an embedding vector)
   - Citations section appears with at least one `[N] filename, p.X  (HIGH|LOW)` entry
   - "Query completed in X.Xs" latency displayed and X < 15

2. **VRAM model mismatch detection** (requires LM Studio with embedding model loaded, not LLM):
   ```bash
   python src/main.py query --question "test" --db data/chunks.db
   ```
   Expected: If embedding model is loaded instead of LLM, the answer will be garbled or LM Studio returns an error. Verify the error is surfaced clearly — not a silent wrong answer.

3. **Empty corpus handling**:
   ```bash
   python src/main.py query --question "test" --db data/empty.db --chroma data/empty_chroma --graph data/empty_kuzu
   ```
   Expected: Returns "The available documents do not contain sufficient information to answer this question." — does not crash.

4. **Citation confidence spot-check**:
   Review 2-3 answers from the live corpus. Confirm HIGH-confidence citations reference pages with multiple entity mentions (dense pages), and LOW-confidence citations reference pages with sparse mentions. This is a qualitative check — no automated test covers it.

---

## Coverage Verification

| Requirement | Test(s) | Status After Phase |
|-------------|---------|-------------------|
| QUERY-01: User submits question, receives answer | `test_query_pipeline_end_to_end`, `test_lm_studio_integration`, CLI checkpoint | Wave 3 |
| QUERY-02: Vector similarity retrieval | `test_vector_search_returns_chunks`, `test_hybrid_retrieve_combines_sources` | Wave 2 |
| QUERY-03: Graph traversal augmentation | `test_graph_expansion_finds_neighbors`, `test_hybrid_retrieve_combines_sources` | Wave 2 |
| QUERY-04: Source citations with HIGH/LOW confidence | `test_citation_confidence_high`, `test_citation_confidence_low`, `test_format_answer_with_citations` | Wave 2 |
| QUERY-05: LM Studio LLM answer generation | `test_lm_studio_integration` (lm_studio marker), pipeline mocked in `test_query_pipeline_end_to_end` | Wave 3 |

---

## Regression Guard

After Phase 4 completes, run the full suite to verify no prior-phase regressions:

```bash
# Full regression check — excludes LM Studio live calls only
pytest tests/ -x -q -k "not lm_studio" --tb=short

# Expected output:
# XX passed, 1 xfailed in X.XXs
# (prior phases: ~30+ tests; phase 4 adds 10 tests; lm_studio integration is 1 xfail)
```

If any prior-phase test fails after Phase 4, check:
- `src/main.py` — adding `cmd_query()` must not break existing subcommand registration
- `conftest.py` — lm_studio marker addition must not break existing marker registrations
- No circular imports between `src/query/` and `src/embed/` or `src/graph/`
