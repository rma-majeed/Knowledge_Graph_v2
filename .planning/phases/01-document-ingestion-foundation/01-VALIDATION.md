---
phase: 1
slug: document-ingestion-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-28
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.4.x |
| **Config file** | `tests/conftest.py` — none yet (Wave 0 installs) |
| **Quick run command** | `pytest tests/test_extraction.py tests/test_chunking.py -v` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~30s (quick) / ~3 min (full) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_extraction.py tests/test_chunking.py -v`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| PDF extraction | TBD | 1 | INGEST-01 | unit | `pytest tests/test_extraction.py::test_pdf_extract_text -x` | ❌ W0 | ⬜ pending |
| PDF table extraction | TBD | 1 | INGEST-01 | unit | `pytest tests/test_extraction.py::test_pdf_extract_tables -x` | ❌ W0 | ⬜ pending |
| PPTX slide text | TBD | 1 | INGEST-02 | unit | `pytest tests/test_extraction.py::test_pptx_extract_slides -x` | ❌ W0 | ⬜ pending |
| PPTX speaker notes | TBD | 1 | INGEST-02 | unit | `pytest tests/test_extraction.py::test_pptx_extract_notes -x` | ❌ W0 | ⬜ pending |
| PPTX table cells | TBD | 1 | INGEST-02 | unit | `pytest tests/test_extraction.py::test_pptx_extract_tables -x` | ❌ W0 | ⬜ pending |
| Chunk fixed-size | TBD | 2 | INGEST-03 | unit | `pytest tests/test_chunking.py::test_chunk_fixed_size -x` | ❌ W0 | ⬜ pending |
| Chunk boundary quality | TBD | 2 | INGEST-03 | integration | `pytest tests/test_chunking.py::test_chunk_boundary_quality -x` | ❌ W0 | ⬜ pending |
| File deduplication | TBD | 1 | INGEST-01–03 | unit | `pytest tests/test_dedup.py::test_file_hash_dedup -x` | ❌ W0 | ⬜ pending |
| End-to-end ingest | TBD | 3 | INGEST-01–03 | integration | `pytest tests/test_ingest_e2e.py::test_ingest_pdf_complete -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — pytest fixtures (sample PDFs, PPTXs, database fixtures)
- [ ] `tests/test_extraction.py` — PyMuPDF and python-pptx extraction test stubs
- [ ] `tests/test_chunking.py` — chunk size, token count, boundary preservation test stubs
- [ ] `tests/test_ingest_e2e.py` — end-to-end ingest workflow test stubs
- [ ] `tests/test_dedup.py` — file hash deduplication test stubs
- [ ] `tests/fixtures/` — sample PDF and PPTX test documents (minimal, synthetic)
- [ ] `pip install "pytest>=7.4.0" "pytest-cov>=4.0.0"` — framework install

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Chunk quality on real automotive documents | INGEST-03 | Requires domain judgment; no ground truth | Sample 10 real docs, inspect 3 chunks/doc, verify natural boundaries |
| Performance: 100-doc sample in <30s | INGEST-01–03 | Depends on real hardware and real documents | Time full ingest run on 100-doc sample; record result |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
