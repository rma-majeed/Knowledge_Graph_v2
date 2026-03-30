---
phase: 2
slug: embedding-vector-search
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-30
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | existing `pytest.ini` / `pyproject.toml` from Phase 1 |
| **Quick run command** | `pytest tests/test_embedding.py -x -q -m "not integration"` |
| **Full suite command** | `pytest tests/ -x -q -m "not integration"` |
| **Estimated runtime** | ~15s (quick, mocked) / ~45s (full suite, mocked) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_embedding.py -x -q -m "not integration"`
- **After every plan wave:** Run `pytest tests/ -x -q -m "not integration"`
- **Before `/gsd:verify-work`:** Full suite must be green (including integration with LM Studio running)
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| embed_chunks API call | TBD | 2 | EMBED-01 | unit (mock) | `pytest tests/test_embedding.py::test_embed_chunks_calls_api -x` | ❌ W0 | ⬜ pending |
| embed_chunks server unavailable | TBD | 2 | EMBED-01 | unit (mock) | `pytest tests/test_embedding.py::test_embed_chunks_server_unavailable -x` | ❌ W0 | ⬜ pending |
| embed_chunks empty input | TBD | 2 | EMBED-01 | unit | `pytest tests/test_embedding.py::test_embed_chunks_empty_input -x` | ❌ W0 | ⬜ pending |
| VectorStore upsert | TBD | 2 | EMBED-02 | unit (EphemeralClient) | `pytest tests/test_embedding.py::test_vector_store_upsert -x` | ❌ W0 | ⬜ pending |
| VectorStore query top-N | TBD | 2 | EMBED-02 | unit (EphemeralClient) | `pytest tests/test_embedding.py::test_vector_store_query_returns_n_results -x` | ❌ W0 | ⬜ pending |
| VectorStore query guard | TBD | 2 | EMBED-02 | unit (EphemeralClient) | `pytest tests/test_embedding.py::test_vector_store_query_small_collection -x` | ❌ W0 | ⬜ pending |
| metadata fields stored | TBD | 2 | EMBED-03 | unit (EphemeralClient) | `pytest tests/test_embedding.py::test_vector_store_metadata_fields -x` | ❌ W0 | ⬜ pending |
| metadata retrievable | TBD | 2 | EMBED-03 | unit (EphemeralClient) | `pytest tests/test_embedding.py::test_vector_store_metadata_retrievable -x` | ❌ W0 | ⬜ pending |
| full embed loop | TBD | 3 | EMBED-01–03 | unit (mock+Ephemeral) | `pytest tests/test_embedding.py::test_embed_all_chunks_loop -x` | ❌ W0 | ⬜ pending |
| incremental re-run | TBD | 3 | EMBED-01–03 | unit (mock+Ephemeral) | `pytest tests/test_embedding.py::test_embed_loop_incremental -x` | ❌ W0 | ⬜ pending |
| query latency <50ms | TBD | 2 | EMBED-02 | unit (timed) | `pytest tests/test_embedding.py::test_query_latency_under_50ms -x` | ❌ W0 | ⬜ pending |
| real 768-dim vectors | TBD | 2 | EMBED-01 | integration (LM Studio) | `pytest tests/test_embedding.py -m integration -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_embedding.py` — 12 xfail stubs (11 unit + 1 integration with `@pytest.mark.integration`)
- [ ] `src/embed/__init__.py` — empty package marker
- [ ] `src/embed/embedder.py` — stub with `raise NotImplementedError`
- [ ] `src/embed/vector_store.py` — stub with `raise NotImplementedError`
- [ ] `data/chroma_db/.gitkeep` — ChromaDB persistence directory
- [ ] `.gitignore` update — add `data/chroma_db/` to ignore real ChromaDB data
- [ ] `pip install "chromadb>=0.5.0"` — add to requirements.txt

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| VRAM peak <3.5GB during embedding | EMBED-01 | Requires hardware monitoring with LM Studio loaded | Run `ingest` + `embed` CLI on 100-doc sample; monitor GPU VRAM via LM Studio or nvidia-smi |
| Retrieval precision >80% on 20 test queries | EMBED-02 | Requires domain judgment on relevance | Run 20 queries against embedded corpus; manually verify top-3 results per query are relevant |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
