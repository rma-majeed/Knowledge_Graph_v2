---
phase: 01-document-ingestion-foundation
plan: 03
subsystem: ingestion
tags: [pptx, extraction, python-pptx, text-extraction]
requirements: [INGEST-02]

dependency_graph:
  requires:
    - 01-01-test-infrastructure (xfail stubs, fixtures, conftest)
  provides:
    - src/ingest/pptx_extractor.py (extract_pptx function)
  affects:
    - tests/test_extraction.py (3 PPTX stubs promoted to passing tests)

tech_stack:
  added:
    - python-pptx (PPTX parsing via Presentation class)
  patterns:
    - Slide iteration with 0->1 index conversion
    - Shape text extraction with table cell support
    - Speaker notes appended as "[NOTES] ..." prefix

key_files:
  created:
    - src/__init__.py
    - src/ingest/__init__.py
    - src/ingest/pptx_extractor.py
  modified:
    - tests/test_extraction.py (removed 3 xfail decorators)

decisions:
  - Used `shape.has_table` guard before `.text` access to avoid AttributeError on table shapes
  - Speaker notes extracted via `notes_slide.notes_text_frame.text` with try/except for malformed notes
  - Table cells joined tab-separated per row for readable output

metrics:
  duration_seconds: 131
  completed_date: "2026-03-28"
  tasks_completed: 1
  tasks_total: 1
  files_created: 3
  files_modified: 1
---

# Phase 01 Plan 03: PPTX Extractor Summary

**One-liner:** PPTX text extraction via python-pptx with slide shapes, table cells, and speaker notes ([NOTES] prefix).

## What Was Built

Implemented `src/ingest/pptx_extractor.py` with the `extract_pptx()` function that:
- Iterates all slides in a PPTX file
- Extracts text from all shapes (titles, body text, text boxes, bullet points)
- Handles table shapes by extracting cell text row-by-row, tab-separated
- Appends speaker notes with `[NOTES]` prefix to each slide's combined text
- Returns a list of dicts with 1-indexed `slide_num` and combined `text` keys
- Handles both `str` and `pathlib.Path` inputs
- Raises `FileNotFoundError` for missing files

The 3 PPTX test stubs in `tests/test_extraction.py` were promoted from `xfail` to passing tests.

## Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement pptx_extractor.py | 30854a2 | src/ingest/pptx_extractor.py, tests/test_extraction.py |

## Test Results

- `test_pptx_extract_slides` — PASSED (3 slides, 1-indexed, title text present)
- `test_pptx_extract_notes` — PASSED (speaker notes text in slide 1 output)
- `test_pptx_extract_tables` — PASSED ("Battery Partner" and "Panasonic" in slide 3 output)
- Full suite: 3 passed, 15 xfailed (no failures)

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None. All plan deliverables are fully wired.

## Self-Check: PASSED

- `src/ingest/pptx_extractor.py` — exists
- `src/ingest/pptx_extractor.py` contains `def extract_pptx(` — confirmed
- `src/ingest/pptx_extractor.py` contains `from pptx import Presentation` — confirmed
- `src/ingest/pptx_extractor.py` contains `slide_idx + 1` — confirmed
- `src/ingest/pptx_extractor.py` contains `[NOTES]` — confirmed
- `src/ingest/pptx_extractor.py` contains `shape.has_table` — confirmed
- All 3 PPTX extraction tests: PASSED
- Commit 30854a2: verified
