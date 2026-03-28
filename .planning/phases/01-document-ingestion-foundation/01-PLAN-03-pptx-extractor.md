---
phase: 01-document-ingestion-foundation
plan: 03
type: execute
wave: 1
depends_on:
  - "01-PLAN-01-test-infrastructure"
files_modified:
  - src/ingest/pptx_extractor.py
autonomous: true
requirements:
  - INGEST-02

must_haves:
  truths:
    - "extract_pptx() returns a list of dicts, one per slide, with slide_num and text keys"
    - "Slide numbers are 1-indexed (first slide is slide_num=1)"
    - "Speaker notes are included in slide text (prefixed with [NOTES])"
    - "Table cell text is included in slide text"
    - "All test_extraction.py PPTX tests pass (not xfail)"
  artifacts:
    - path: "src/ingest/pptx_extractor.py"
      provides: "python-pptx-based PPTX text extraction"
      exports: ["extract_pptx"]
      contains: "def extract_pptx("
  key_links:
    - from: "src/ingest/pptx_extractor.py"
      to: "pptx (python-pptx)"
      via: "from pptx import Presentation"
      pattern: "from pptx import Presentation"
    - from: "tests/test_extraction.py"
      to: "src/ingest/pptx_extractor.py"
      via: "from src.ingest.pptx_extractor import extract_pptx"
      pattern: "from src.ingest.pptx_extractor import extract_pptx"
---

<objective>
Implement the PPTX text extractor using python-pptx. The extractor iterates all slides, collects text from shapes, table cells, and speaker notes, and returns a list of slide dicts with 1-indexed slide numbers.

Purpose: INGEST-02 — System extracts text from PPTX files including slide text, speaker notes, and table cells via python-pptx.

Output: src/ingest/pptx_extractor.py with tested extract_pptx() function. All PPTX test stubs in test_extraction.py turn from xfail to passing.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/phases/01-document-ingestion-foundation/01-RESEARCH.md
@.planning/phases/01-document-ingestion-foundation/01-VALIDATION.md
@tests/conftest.py
@tests/test_extraction.py

<interfaces>
<!-- Contracts the executor must satisfy. Test stubs import these. -->

From tests/test_extraction.py (what the tests expect):
```python
from src.ingest.pptx_extractor import extract_pptx

slides = extract_pptx(sample_pptx_path)
# slides is a list of dicts, one per slide
# len(slides) == 3                           (3-slide fixture)
# slides[0]["slide_num"] == 1                (1-indexed)
# "EV Strategy" in slides[0]["text"]         (title text)
# "Emphasize" in slides[0]["text"]           (speaker notes content)
# "Battery Partner" in all_text              (table header cell, slide 3)
# "Panasonic" in all_text                    (table data cell, slide 3)
```

Required return shape:
```python
# extract_pptx(filepath: Path | str) -> list[dict]
# Each dict:
{
    "slide_num": int,  # 1-indexed
    "text": str,       # All slide text: shapes + table cells + "[NOTES] ..." speaker notes
}
```

Fixture content (from tests/fixtures/make_fixtures.py):
- Slide 1: title "EV Strategy Overview", body with bullet points, notes "Speaker note: Emphasize..."
- Slide 2: textbox with market share text, notes "Speaker note: Updated Q3 2025..."
- Slide 3: table with headers ["OEM", "EV Sales 2024", "Battery Partner"], rows [Toyota, BMW]
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement pptx_extractor.py using python-pptx</name>

  <read_first>
    - tests/test_extraction.py (exact assertions the PPTX tests make)
    - tests/conftest.py (fixture shape: sample_pptx_path is a pathlib.Path)
    - tests/fixtures/make_fixtures.py (exact fixture content — what text and notes are in each slide)
    - .planning/phases/01-document-ingestion-foundation/01-RESEARCH.md (PPTX Extraction section, lines 137-177)
  </read_first>

  <files>src/ingest/pptx_extractor.py</files>

  <behavior>
    - extract_pptx(path) on a 3-slide PPTX returns exactly 3 dicts
    - slide_num is 1-indexed: first slide returns {"slide_num": 1, ...}
    - Slide 1 text includes "EV Strategy" (title) and "Emphasize" (speaker notes)
    - Slide 3 text includes "Battery Partner" (table header) and "Panasonic" (table cell)
    - Speaker notes are prefixed with "[NOTES]" in the combined text
    - extract_pptx handles Path objects and str paths equally
    - Shapes without text attribute are skipped gracefully (no AttributeError)
  </behavior>

  <action>
Create `src/ingest/pptx_extractor.py`:

```python
"""PPTX text extraction using python-pptx.

Extracts text from slide shapes, table cells, and speaker notes.
Returns a list of slide dicts with 1-indexed slide numbers.

Usage:
    from src.ingest.pptx_extractor import extract_pptx
    slides = extract_pptx("path/to/presentation.pptx")
    # slides[0] == {"slide_num": 1, "text": "..."}
"""
from __future__ import annotations

from pathlib import Path
from typing import Union

from pptx import Presentation
from pptx.shapes.base import BaseShape


def _extract_shape_text(shape: BaseShape) -> str:
    """Extract text from a single shape, including table cells.

    Args:
        shape: A python-pptx BaseShape object.

    Returns:
        Text string extracted from the shape, or empty string if shape has no text.
    """
    parts: list[str] = []

    if shape.has_table:
        # Table: extract each cell row by row, tab-separated
        table = shape.table
        for row in table.rows:
            row_text = "\t".join(cell.text.strip() for cell in row.cells)
            if row_text.strip():
                parts.append(row_text)
    elif hasattr(shape, "text"):
        text = shape.text.strip()
        if text:
            parts.append(text)

    return "\n".join(parts)


def extract_pptx(filepath: Union[str, Path]) -> list[dict]:
    """Extract text from all slides of a PPTX file.

    For each slide, extracts:
    - Text from all shapes (titles, body text, text boxes, bullet points)
    - Table cell content (row by row, cells tab-separated)
    - Speaker notes (appended as "[NOTES] {notes_text}")

    Args:
        filepath: Path to the PPTX file (str or pathlib.Path).

    Returns:
        List of dicts, one per slide, in presentation order:
        [
            {"slide_num": 1, "text": "..."},  # 1-indexed
            {"slide_num": 2, "text": "..."},
            ...
        ]

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"PPTX not found: {filepath}")

    prs = Presentation(str(filepath))
    slides: list[dict] = []

    for slide_idx, slide in enumerate(prs.slides):
        parts: list[str] = []

        # Extract text from all shapes on the slide
        for shape in slide.shapes:
            shape_text = _extract_shape_text(shape)
            if shape_text:
                parts.append(shape_text)

        # Extract speaker notes
        if slide.has_notes_slide:
            try:
                notes_text = slide.notes_slide.notes_text_frame.text.strip()
                if notes_text:
                    parts.append(f"[NOTES] {notes_text}")
            except Exception:
                # Notes frame can be malformed in some PPTXs — degrade gracefully
                pass

        combined_text = "\n".join(p for p in parts if p)

        slides.append({
            "slide_num": slide_idx + 1,  # Convert 0-indexed to 1-indexed
            "text": combined_text,
        })

    return slides
```

After writing the file, remove the `@pytest.mark.xfail` decorators from the PPTX tests in `tests/test_extraction.py`:
- `test_pptx_extract_slides`
- `test_pptx_extract_notes`
- `test_pptx_extract_tables`

Do NOT modify the PDF tests.

Run the PPTX tests:
```bash
pytest tests/test_extraction.py::test_pptx_extract_slides tests/test_extraction.py::test_pptx_extract_notes tests/test_extraction.py::test_pptx_extract_tables -v
```
  </action>

  <verify>
    <automated>pytest tests/test_extraction.py::test_pptx_extract_slides tests/test_extraction.py::test_pptx_extract_notes tests/test_extraction.py::test_pptx_extract_tables -v</automated>
  </verify>

  <acceptance_criteria>
    - src/ingest/pptx_extractor.py exists
    - src/ingest/pptx_extractor.py contains `def extract_pptx(`
    - src/ingest/pptx_extractor.py contains `from pptx import Presentation`
    - src/ingest/pptx_extractor.py contains `slide_idx + 1` (1-indexed slide numbers)
    - src/ingest/pptx_extractor.py contains `[NOTES]` (speaker notes prefix)
    - src/ingest/pptx_extractor.py contains `shape.has_table` (table handling)
    - `pytest tests/test_extraction.py::test_pptx_extract_slides -v` exits 0 with PASSED
    - `pytest tests/test_extraction.py::test_pptx_extract_notes -v` exits 0 with PASSED
    - `pytest tests/test_extraction.py::test_pptx_extract_tables -v` exits 0 with PASSED
    - `pytest tests/ -q` exits 0 (no FAILED, no ERROR)
  </acceptance_criteria>

  <done>extract_pptx() implemented and tested. All three PPTX extraction tests pass. Full test suite is green.</done>
</task>

</tasks>

<verification>
After plan complete:
1. `pytest tests/test_extraction.py -v` — all 6 tests PASSED (3 PDF + 3 PPTX)
2. `pytest tests/ -q` — exits 0 (no FAILED, no ERROR)
3. `python -c "from src.ingest.pptx_extractor import extract_pptx; slides = extract_pptx('tests/fixtures/sample.pptx'); assert len(slides) == 3; assert slides[0]['slide_num'] == 1; print('ok')"` — exits 0
</verification>

<success_criteria>
- extract_pptx() returns 1-indexed slide dicts
- Speaker notes appear in output with [NOTES] prefix
- Table cell text appears in slide 3 output
- All 3 PPTX test stubs promoted to passing tests
- Full test suite (tests/) exits 0
</success_criteria>

<output>
After completion, create `.planning/phases/01-document-ingestion-foundation/01-03-SUMMARY.md`
</output>
