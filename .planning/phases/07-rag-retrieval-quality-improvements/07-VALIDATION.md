---
phase: 7
slug: rag-retrieval-quality-improvements
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-31
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini or pyproject.toml (existing) |
| **Quick run command** | `pytest tests/test_retrieval_quality.py -x -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~15 seconds (no LM Studio required) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_retrieval_quality.py -x -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | RAG-01,02,04,05 | xfail stub | `pytest tests/test_retrieval_quality.py -q` | ❌ W0 | ⬜ pending |
| 07-02-01 | 02 | 2 | RAG-01 | unit | `pytest tests/test_retrieval_quality.py::test_bm25 -q` | ❌ W0 | ⬜ pending |
| 07-03-01 | 03 | 2 | RAG-02 | unit | `pytest tests/test_retrieval_quality.py::test_reranker -q` | ❌ W0 | ⬜ pending |
| 07-04-01 | 04 | 3 | RAG-03,04 | unit | `pytest tests/test_retrieval_quality.py::test_enrichment -q` | ❌ W0 | ⬜ pending |
| 07-05-01 | 05 | 4 | RAG-05 | integration | `pytest tests/ -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_retrieval_quality.py` — xfail stubs for RAG-01 through RAG-05
- [ ] `tests/conftest.py` — fixture updates: mock BM25 corpus, mock reranker scores, sample chunks

*Existing infrastructure (pytest, conftest.py fixtures) expected to cover most needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| BGE reranker model download (~278MB) | RAG-02 | Requires network + disk space | Run `python -c "from sentence_transformers import CrossEncoder; CrossEncoder('BAAI/bge-reranker-v2-m3')"` once |
| End-to-end retrieval quality on real corpus | RAG-01,02,03 | Requires live documents + LM Studio | Run `python src/main.py query --question "what information is available on warranty?"` and verify results |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
