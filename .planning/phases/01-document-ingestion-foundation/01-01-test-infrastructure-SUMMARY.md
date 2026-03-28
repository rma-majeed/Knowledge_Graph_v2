---
phase: 01-document-ingestion-foundation
plan: "01"
subsystem: test-infrastructure
tags: [testing, pytest, fixtures, dependencies, wave-0]
dependency_graph:
  requires: []
  provides:
    - requirements.txt with pinned pip-installable dependencies
    - tests/conftest.py with shared fixtures (sample_pdf_path, sample_pptx_path, tmp_db_path, tmp_db_conn)
    - tests/fixtures/sample.pdf (2-page synthetic PDF)
    - tests/fixtures/sample.pptx (3-slide synthetic PPTX with notes and table)
    - 18 xfail test stubs covering extraction, chunking, dedup, and e2e pipeline
  affects:
    - All subsequent Phase 1 plans (01-02 through 01-06) rely on these fixtures and stubs
tech_stack:
  added:
    - PyMuPDF>=1.23.0 (PDF text extraction)
    - python-pptx>=0.6.0 (PPTX text extraction)
    - tiktoken>=0.5.0 (token counting for chunking)
    - tqdm>=4.66.0 (progress display)
    - pytest>=7.4.0 (test runner)
    - pytest-cov>=4.0.0 (coverage reporting)
  patterns:
    - xfail stubs (strict=False) for TDD wave-0 test infrastructure
    - Session-scoped fixtures for expensive file system objects
    - Function-scoped SQLite fixtures using tmp_path for isolation
key_files:
  created:
    - requirements.txt
    - tests/__init__.py
    - tests/conftest.py
    - tests/fixtures/__init__.py
    - tests/fixtures/make_fixtures.py
    - tests/fixtures/sample.pdf
    - tests/fixtures/sample.pptx
    - tests/test_extraction.py
    - tests/test_chunking.py
    - tests/test_dedup.py
    - tests/test_ingest_e2e.py
  modified: []
decisions:
  - "Used xfail(strict=False) rather than skip so test intent is visible and stubs can pass once implementation lands"
  - "Generated synthetic fixtures programmatically using PyMuPDF and python-pptx rather than shipping binary blobs"
  - "Session-scoped sample_pdf_path and sample_pptx_path fixtures avoid re-reading fixture files per test"
metrics:
  duration_seconds: 278
  completed_date: "2026-03-28"
  tasks_completed: 3
  tasks_total: 3
  files_created: 11
  files_modified: 0
---

# Phase 1 Plan 01: Test Infrastructure Summary

**One-liner:** Pytest xfail stub suite with PyMuPDF/python-pptx synthetic fixtures and pinned requirements, enabling TDD wave-0 green baseline for all Phase 1 plans.

## What Was Built

Wave 0 test infrastructure that satisfies the Nyquist rule: every subsequent Phase 1 task has an automated verify command that works immediately.

Three tasks completed:

1. **requirements.txt + dependency install** — Six pip-installable packages pinned and verified importable (PyMuPDF 1.27.2, python-pptx 1.0.2, tiktoken, tqdm, pytest 9.0.2, pytest-cov).

2. **Synthetic fixture files + conftest.py** — `make_fixtures.py` generates a 2-page PDF and 3-slide PPTX programmatically using the installed libraries. `conftest.py` exposes session-scoped path fixtures and function-scoped SQLite fixtures.

3. **18 xfail test stubs** — Four test files covering all Phase 1 implementation plans:
   - `test_extraction.py`: 6 stubs for PDF and PPTX extractors (Plans 02-03)
   - `test_chunking.py`: 5 stubs for token-based chunking (Plan 05)
   - `test_dedup.py`: 3 stubs for SHA-256 deduplication (Plan 04)
   - `test_ingest_e2e.py`: 4 stubs for end-to-end pipeline (Plan 06)

## Verification Results

```
18 xfailed in 5.03s
```

Exit code 0. No errors, no failures. All stubs xfail as expected.

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | 72267f0 | chore(01-01): install dependencies and create requirements.txt |
| 2 | de84758 | feat(01-01): create synthetic fixture files and conftest.py |
| 3 | e2664b4 | test(01-01): add xfail test stubs for extraction, chunking, dedup, e2e |

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

All 18 test functions are intentional xfail stubs. They are tracked here for the verifier:

| File | Functions | Resolved by |
|------|-----------|-------------|
| tests/test_extraction.py | test_pdf_extract_text, test_pdf_extract_tables, test_pdf_extract_returns_page_count | Plan 01-02 |
| tests/test_extraction.py | test_pptx_extract_slides, test_pptx_extract_notes, test_pptx_extract_tables | Plan 01-03 |
| tests/test_chunking.py | test_chunk_fixed_size, test_chunk_overlap, test_chunk_metadata_fields, test_chunk_boundary_quality, test_chunk_token_count_accuracy | Plan 01-05 |
| tests/test_dedup.py | test_file_hash_sha256, test_file_hash_dedup, test_different_files_have_different_hashes | Plan 01-04 |
| tests/test_ingest_e2e.py | test_ingest_pdf_complete, test_ingest_pptx_complete, test_ingest_deduplication, test_ingest_chunk_metadata_stored | Plan 01-06 |

These stubs are intentional — they define the contract that each subsequent plan must satisfy. The plan's goal (green xfail baseline) is fully achieved.

## Self-Check: PASSED
