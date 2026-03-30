---
phase: 3
slug: knowledge-graph-construction
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-30
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | existing `pytest.ini` / `pyproject.toml` from Phase 1 |
| **Quick run command** | `pytest tests/test_graph_extraction.py tests/test_deduplicator.py tests/test_kuzu_db.py tests/test_citations.py -x -q -k "not lm_studio"` |
| **Full suite command** | `pytest tests/ -x -q -k "not lm_studio"` |
| **Estimated runtime** | ~20s (quick, mocked) / ~60s (full suite, mocked) |

---

## Sampling Rate

- **After every task commit:** Run quick command above
- **After every plan wave:** Run `pytest tests/ -x -q -k "not lm_studio"`
- **Before `/gsd:verify-work`:** Full suite must be green (including integration with LM Studio running)
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|-------------|-----------|-------------------|-------------|--------|
| extract entities from chunk | 2 | GRAPH-01 | unit (mock LLM) | `pytest tests/test_graph_extraction.py::test_extract_entities_from_chunk -x` | ❌ W0 | ⬜ pending |
| entity type validation | 2 | GRAPH-01 | unit | `pytest tests/test_graph_extraction.py::test_entity_type_validation -x` | ❌ W0 | ⬜ pending |
| confidence threshold filter | 2 | GRAPH-01 | unit | `pytest tests/test_graph_extraction.py::test_confidence_threshold -x` | ❌ W0 | ⬜ pending |
| fuzzy dedup legal suffix | 2 | GRAPH-02 | unit | `pytest tests/test_deduplicator.py::test_fuzzy_dedup_legal_suffix -x` | ❌ W0 | ⬜ pending |
| normalize_entity_name | 2 | GRAPH-02 | unit | `pytest tests/test_deduplicator.py::test_normalize_name -x` | ❌ W0 | ⬜ pending |
| KuzuDB schema idempotent | 2 | GRAPH-03 | unit (tmp dir) | `pytest tests/test_kuzu_db.py::test_create_schema_idempotent -x` | ❌ W0 | ⬜ pending |
| KuzuDB insert entity | 2 | GRAPH-03 | unit (tmp dir) | `pytest tests/test_kuzu_db.py::test_insert_entity_oem -x` | ❌ W0 | ⬜ pending |
| KuzuDB query entity | 2 | GRAPH-03 | unit (tmp dir) | `pytest tests/test_kuzu_db.py::test_query_entity -x` | ❌ W0 | ⬜ pending |
| chunk_citations insert | 2 | GRAPH-04 | unit | `pytest tests/test_citations.py::test_insert_chunk_citation -x` | ❌ W0 | ⬜ pending |
| get_chunks_for_entity | 2 | GRAPH-04 | unit | `pytest tests/test_citations.py::test_get_chunks_for_entity -x` | ❌ W0 | ⬜ pending |
| full extraction pipeline | 3 | GRAPH-01–04 | unit (mock+tmp) | `pytest tests/test_graph_extraction.py tests/test_kuzu_db.py -x` | ❌ W0 | ⬜ pending |
| real LM Studio extraction | 3 | GRAPH-01 | integration (LM Studio) | `pytest tests/test_graph_extraction.py -m lm_studio -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_graph_extraction.py` — xfail stubs (entity extraction, type validation, confidence)
- [ ] `tests/test_deduplicator.py` — xfail stubs (fuzzy dedup, legal suffix removal, normalization)
- [ ] `tests/test_kuzu_db.py` — xfail stubs (schema idempotent, insert, query)
- [ ] `tests/test_citations.py` — xfail stubs (insert citation, get chunks for entity)
- [ ] `src/graph/__init__.py` — empty package marker
- [ ] `src/graph/extractor.py` — stub with `raise NotImplementedError`
- [ ] `src/graph/deduplicator.py` — stub with `raise NotImplementedError`
- [ ] `src/graph/db_manager.py` — stub with `raise NotImplementedError`
- [ ] `src/graph/citations.py` — stub with `raise NotImplementedError`
- [ ] `src/graph/monitor.py` — stub with `raise NotImplementedError`
- [ ] `data/kuzu_db/.gitkeep` — KuzuDB persistence directory
- [ ] `.gitignore` update — add `data/kuzu_db/` to ignore real KuzuDB data
- [ ] `pip install kuzu rapidfuzz` — add to requirements.txt

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Entity extraction quality on real corpus | GRAPH-01 | Requires domain judgment — are "Toyota" and "Toyota Motor Corp." correctly deduped? | Run `graph` CLI on 20-doc sample; manually verify extracted entities are sensible |
| Graph explosion check on 500-doc corpus | GRAPH-03 | Requires real corpus and manual density review | Run full pipeline; check entity count stays < 10K, ratio < 20 entities/doc |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
