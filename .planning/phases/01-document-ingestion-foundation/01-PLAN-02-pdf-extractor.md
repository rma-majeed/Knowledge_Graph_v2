---
phase: 01-document-ingestion-foundation
plan: 02
type: execute
wave: 1
depends_on:
  - "01-PLAN-01-test-infrastructure"
files_modified:
  - src/__init__.py
  - src/ingest/__init__.py
  - src/ingest/pdf_extractor.py
autonomous: true
requirements:
  - INGEST-01

must_haves:
  truths:
    - "extract_pdf() returns a list of dicts, one per page, with page_num and text keys"
    - "Page numbers are 1-indexed (page 1 is page_num=1, not 0)"
    - "Table cell text is included in the page text output"
    - "All test_extraction.py PDF tests pass (not xfail)"
  artifacts:
    - path: "src/ingest/pdf_extractor.py"
      provides: "PyMuPDF-based PDF text extraction"
      exports: ["extract_pdf"]
      contains: "def extract_pdf("
    - path: "src/__init__.py"
      provides: "Package marker for src/"
    - path: "src/ingest/__init__.py"
      provides: "Package marker for src/ingest/"
  key_links:
    - from: "src/ingest/pdf_extractor.py"
      to: "fitz (PyMuPDF)"
      via: "import fitz"
      pattern: "import fitz"
    - from: "tests/test_extraction.py"
      to: "src/ingest/pdf_extractor.py"
      via: "from src.ingest.pdf_extractor import extract_pdf"
      pattern: "from src.ingest.pdf_extractor import extract_pdf"
---

<objective>
Implement the PDF text extractor using PyMuPDF (fitz). The extractor iterates all pages, extracts plain text and table cell text, and returns a list of page dicts with 1-indexed page numbers.

Purpose: INGEST-01 — System extracts full text content from PDF files using PyMuPDF.

Output: src/ingest/pdf_extractor.py with tested extract_pdf() function. All PDF test stubs in test_extraction.py turn from xfail to passing.
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
from src.ingest.pdf_extractor import extract_pdf

pages = extract_pdf(sample_pdf_path)
# pages is a list of dicts, one per page
# pages[0]["page_num"] == 1          (1-indexed)
# pages[0]["text"] is a non-empty string
# "Toyota" in " ".join(p["text"] for p in pages)  (table cells included)
# len(pages) == 2  (matches actual PDF page count)
```

Required return shape:
```python
# extract_pdf(filepath: Path | str) -> list[dict]
# Each dict:
{
    "page_num": int,   # 1-indexed
    "text": str,       # Combined plain text + table cell text for this page
}
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement pdf_extractor.py using PyMuPDF</name>

  <read_first>
    - tests/test_extraction.py (exact assertions the implementation must satisfy)
    - tests/conftest.py (fixture shape: sample_pdf_path is a pathlib.Path)
    - .planning/phases/01-document-ingestion-foundation/01-RESEARCH.md (Extraction API Patterns — PDF section, lines 101-135)
  </read_first>

  <files>
    src/__init__.py
    src/ingest/__init__.py
    src/ingest/pdf_extractor.py
  </files>

  <behavior>
    - extract_pdf(path) on a 2-page PDF returns exactly 2 dicts
    - page_num is 1-indexed: first page returns {"page_num": 1, ...}
    - Table cell text ("Toyota", "BMW") is present in the output text for page 2
    - extract_pdf on the sample fixture: "Automotive" is in pages[0]["text"]
    - extract_pdf handles Path objects and str paths equally
    - extract_pdf closes the fitz document before returning (no resource leak)
  </behavior>

  <action>
Create the package __init__.py files (both empty):
- `src/__init__.py` — empty
- `src/ingest/__init__.py` — empty

Then create `src/ingest/pdf_extractor.py`:

```python
"""PDF text extraction using PyMuPDF (fitz).

Extracts plain text and table cell content from each page of a PDF document.
Returns a list of page dicts with 1-indexed page numbers.

Usage:
    from src.ingest.pdf_extractor import extract_pdf
    pages = extract_pdf("path/to/document.pdf")
    # pages[0] == {"page_num": 1, "text": "..."}
"""
from __future__ import annotations

from pathlib import Path
from typing import Union

import fitz  # PyMuPDF


def extract_pdf(filepath: Union[str, Path]) -> list[dict]:
    """Extract text from all pages of a PDF file.

    For each page, extracts:
    - Plain text via page.get_text()
    - Table cell content via page.find_tables() (appended after plain text)

    Args:
        filepath: Path to the PDF file (str or pathlib.Path).

    Returns:
        List of dicts, one per page, in document order:
        [
            {"page_num": 1, "text": "..."},  # 1-indexed
            {"page_num": 2, "text": "..."},
            ...
        ]

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is not a readable PDF.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"PDF not found: {filepath}")

    doc = fitz.open(str(filepath))
    pages: list[dict] = []

    try:
        for page_idx in range(doc.page_count):
            page = doc[page_idx]

            # Extract plain text (preserves whitespace layout)
            plain_text: str = page.get_text()

            # Extract table cell text and append after plain text
            table_parts: list[str] = []
            try:
                tables = page.find_tables()
                for table in tables:
                    rows = table.extract()  # list[list[str | None]]
                    for row in rows:
                        # Filter None cells, join with tab
                        cells = [cell if cell is not None else "" for cell in row]
                        row_text = "\t".join(cells).strip()
                        if row_text:
                            table_parts.append(row_text)
            except Exception:
                # find_tables can fail on malformed PDFs — degrade gracefully
                pass

            # Combine plain text and table text
            parts = [plain_text.strip()]
            if table_parts:
                parts.append("\n".join(table_parts))
            combined_text = "\n".join(p for p in parts if p)

            pages.append({
                "page_num": page_idx + 1,  # Convert 0-indexed to 1-indexed
                "text": combined_text,
            })
    finally:
        doc.close()

    return pages
```

After writing the file, remove the `@pytest.mark.xfail` decorators from the three PDF tests in `tests/test_extraction.py`:
- `test_pdf_extract_text`
- `test_pdf_extract_tables`
- `test_pdf_extract_returns_page_count`

Do NOT remove xfail from PPTX tests — they are implemented in Plan 03.

Run the PDF tests to confirm they pass:
```bash
pytest tests/test_extraction.py::test_pdf_extract_text tests/test_extraction.py::test_pdf_extract_tables tests/test_extraction.py::test_pdf_extract_returns_page_count -v
```
  </action>

  <verify>
    <automated>pytest tests/test_extraction.py::test_pdf_extract_text tests/test_extraction.py::test_pdf_extract_tables tests/test_extraction.py::test_pdf_extract_returns_page_count -v</automated>
  </verify>

  <acceptance_criteria>
    - src/ingest/pdf_extractor.py exists
    - src/ingest/pdf_extractor.py contains `def extract_pdf(`
    - src/ingest/pdf_extractor.py contains `import fitz`
    - src/ingest/pdf_extractor.py contains `page_idx + 1` (1-indexed page numbers)
    - src/ingest/pdf_extractor.py contains `doc.close()` inside a `finally` block
    - `pytest tests/test_extraction.py::test_pdf_extract_text -v` exits 0 with PASSED
    - `pytest tests/test_extraction.py::test_pdf_extract_tables -v` exits 0 with PASSED
    - `pytest tests/test_extraction.py::test_pdf_extract_returns_page_count -v` exits 0 with PASSED
    - `pytest tests/ -q` exits 0 (remaining tests still xfail, none ERROR)
  </acceptance_criteria>

  <done>extract_pdf() implemented and tested. All three PDF extraction tests pass (not xfail). PPTX tests remain xfail.</done>
</task>

</tasks>

<verification>
After plan complete:
1. `pytest tests/test_extraction.py -v -k "pdf"` — 3 tests PASSED
2. `pytest tests/ -q` — exits 0 (no FAILED, no ERROR)
3. `python -c "from src.ingest.pdf_extractor import extract_pdf; pages = extract_pdf('tests/fixtures/sample.pdf'); assert len(pages) == 2; assert pages[0]['page_num'] == 1; print('ok')"` — exits 0
</verification>

<success_criteria>
- extract_pdf() returns 1-indexed page dicts
- Table cell text appears in page output
- All 3 PDF test stubs promoted to passing tests
- No import errors anywhere in test suite
</success_criteria>

<output>
After completion, create `.planning/phases/01-document-ingestion-foundation/01-02-SUMMARY.md`
</output>
