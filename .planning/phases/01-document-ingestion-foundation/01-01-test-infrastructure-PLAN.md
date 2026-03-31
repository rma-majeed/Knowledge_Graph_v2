---
phase: 01-document-ingestion-foundation
plan: 01
type: execute
wave: 0
depends_on: []
files_modified:
  - requirements.txt
  - tests/conftest.py
  - tests/test_extraction.py
  - tests/test_chunking.py
  - tests/test_ingest_e2e.py
  - tests/test_dedup.py
  - tests/fixtures/sample.pdf
  - tests/fixtures/sample.pptx
autonomous: true
requirements:
  - INGEST-01
  - INGEST-02
  - INGEST-03

must_haves:
  truths:
    - "pytest discovers and runs all test stubs without import errors"
    - "All test stubs are marked xfail or skip so suite is green before any implementation"
    - "Sample fixture files exist and are loadable by PyMuPDF and python-pptx"
    - "All project dependencies are pinned in requirements.txt and pip-installable"
  artifacts:
    - path: "requirements.txt"
      provides: "Pinned pip-installable dependencies"
      contains: "PyMuPDF"
    - path: "tests/conftest.py"
      provides: "Shared pytest fixtures for sample documents and DB"
      exports: ["sample_pdf_path", "sample_pptx_path", "tmp_db_path"]
    - path: "tests/test_extraction.py"
      provides: "Extraction test stubs for PDF and PPTX"
      contains: "test_pdf_extract_text"
    - path: "tests/test_chunking.py"
      provides: "Chunking test stubs"
      contains: "test_chunk_fixed_size"
    - path: "tests/fixtures/sample.pdf"
      provides: "Minimal synthetic PDF fixture (2 pages, 1 table)"
    - path: "tests/fixtures/sample.pptx"
      provides: "Minimal synthetic PPTX fixture (3 slides, speaker notes, 1 table)"
  key_links:
    - from: "tests/conftest.py"
      to: "tests/fixtures/sample.pdf"
      via: "pytest fixture returning Path"
      pattern: "sample_pdf_path"
    - from: "tests/test_extraction.py"
      to: "tests/conftest.py"
      via: "pytest fixture injection"
      pattern: "def test_.*\\(.*sample_pdf_path"
---

<objective>
Set up the complete test infrastructure before any implementation begins. This plan installs all project dependencies, creates synthetic fixture files, writes test stubs (marked xfail), and verifies pytest runs clean.

Purpose: Wave 0 must exist before any implementation wave so the Nyquist rule is satisfied — every subsequent task can immediately run its automated verify command.

Output: Green pytest suite (all stubs xfail), requirements.txt, conftest.py, fixture files.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/01-document-ingestion-foundation/01-RESEARCH.md
@.planning/phases/01-document-ingestion-foundation/01-VALIDATION.md
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Install dependencies and create requirements.txt</name>

  <read_first>
    - .planning/phases/01-document-ingestion-foundation/01-RESEARCH.md (Standard Stack section — pinned versions)
    - C:/Users/2171176/Documents/Python/Knowledge_Graph_v2/requirements.txt (if exists — check before overwriting)
  </read_first>

  <files>requirements.txt</files>

  <action>
Create `requirements.txt` in the project root `C:/Users/2171176/Documents/Python/Knowledge_Graph_v2/` with these exact pinned entries (all pip-installable, no conda/Docker/system packages):

```
# Document extraction
PyMuPDF>=1.23.0
python-pptx>=0.6.0

# Chunking / token counting
tiktoken>=0.5.0

# Progress display
tqdm>=4.66.0

# Testing
pytest>=7.4.0
pytest-cov>=4.0.0
```

Then run the install:
```bash
pip install -r requirements.txt
```

Verify installation:
```bash
python -c "import fitz; print('PyMuPDF:', fitz.version)"
python -c "import pptx; print('python-pptx:', pptx.__version__)"
python -c "import tiktoken; enc = tiktoken.get_encoding('cl100k_base'); print('tiktoken: ok')"
python -c "import tqdm; print('tqdm:', tqdm.__version__)"
python -c "import pytest; print('pytest:', pytest.__version__)"
```

All five commands must print their version without error.
  </action>

  <verify>
    <automated>python -c "import fitz, pptx, tiktoken, tqdm, pytest; print('all imports ok')"</automated>
  </verify>

  <acceptance_criteria>
    - requirements.txt exists at C:/Users/2171176/Documents/Python/Knowledge_Graph_v2/requirements.txt
    - requirements.txt contains the line `PyMuPDF>=1.23.0`
    - requirements.txt contains the line `python-pptx>=0.6.0`
    - requirements.txt contains the line `tiktoken>=0.5.0`
    - requirements.txt contains the line `pytest>=7.4.0`
    - `python -c "import fitz, pptx, tiktoken, tqdm, pytest; print('all imports ok')"` exits 0 and prints "all imports ok"
  </acceptance_criteria>

  <done>requirements.txt written and all dependencies importable in the active Python environment.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Create synthetic fixture files and conftest.py</name>

  <read_first>
    - .planning/phases/01-document-ingestion-foundation/01-VALIDATION.md (Wave 0 Requirements section — lists required fixtures)
    - .planning/phases/01-document-ingestion-foundation/01-RESEARCH.md (Extraction API Patterns — PyMuPDF and python-pptx APIs)
  </read_first>

  <files>
    tests/conftest.py
    tests/fixtures/sample.pdf
    tests/fixtures/sample.pptx
  </files>

  <action>
Create the directory structure:
```
C:/Users/2171176/Documents/Python/Knowledge_Graph_v2/
  tests/
    __init__.py          (empty)
    conftest.py
    fixtures/
      __init__.py        (empty)
      make_fixtures.py   (script that generates sample.pdf and sample.pptx)
      sample.pdf         (generated by make_fixtures.py)
      sample.pptx        (generated by make_fixtures.py)
```

**Step 1 — Write `tests/fixtures/make_fixtures.py`:**

This script generates minimal synthetic fixtures using only the already-installed libraries. Run it once to create sample.pdf and sample.pptx.

```python
"""Generate minimal synthetic fixtures for testing."""
from pathlib import Path
import fitz  # PyMuPDF
from pptx import Presentation
from pptx.util import Inches

FIXTURES = Path(__file__).parent


def make_sample_pdf():
    """Create a 2-page PDF with text and a table."""
    doc = fitz.open()

    # Page 1 — plain text
    page1 = doc.new_page(width=595, height=842)  # A4
    page1.insert_text(
        (72, 72),
        "Automotive Consulting Report\n\nExecutive Summary\n\n"
        "This document covers EV supply chain strategy for OEM clients. "
        "Toyota and BMW are the primary stakeholders. The recommendation is "
        "to diversify battery suppliers beyond CATL to include Panasonic and BYD.\n\n"
        "Section 1: Market Analysis\n\n"
        "The global EV market is projected to reach $800B by 2030. "
        "Key technology trends include solid-state batteries and 800V charging architecture.",
        fontsize=11,
    )

    # Page 2 — text + simulate table content
    page2 = doc.new_page(width=595, height=842)
    page2.insert_text(
        (72, 72),
        "Section 2: Supplier Recommendations\n\n"
        "OEM\tPrimary Supplier\tAlternative\n"
        "Toyota\tPanasonic\tCATL\n"
        "BMW\tSamsung SDI\tBYD\n\n"
        "Conclusion: Dual-source battery strategy reduces supply chain risk by 40%.",
        fontsize=11,
    )

    doc.save(FIXTURES / "sample.pdf")
    doc.close()
    print(f"Created: {FIXTURES / 'sample.pdf'}")


def make_sample_pptx():
    """Create a 3-slide PPTX with text, speaker notes, and a table."""
    prs = Presentation()
    blank_layout = prs.slide_layouts[6]  # Blank layout

    # Slide 1 — title + body text
    slide1 = prs.slides.add_slide(prs.slide_layouts[1])  # Title + Content
    slide1.shapes.title.text = "EV Strategy Overview"
    slide1.placeholders[1].text = (
        "Key findings:\n"
        "- Toyota leads in hybrid technology\n"
        "- Battery costs declining 15% per year\n"
        "- 800V architecture is next inflection point"
    )
    notes1 = slide1.notes_slide.notes_text_frame
    notes1.text = "Speaker note: Emphasize cost trajectory to CFO audience."

    # Slide 2 — blank with text box
    slide2 = prs.slides.add_slide(blank_layout)
    txBox = slide2.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(4))
    txBox.text_frame.text = (
        "Market share analysis\n\n"
        "BYD has captured 35% of China EV market. "
        "Tesla maintains 18% global share. "
        "Legacy OEMs collectively hold 47% share."
    )
    notes2 = slide2.notes_slide.notes_text_frame
    notes2.text = "Speaker note: Updated Q3 2025 data — verify with client before sharing."

    # Slide 3 — table
    slide3 = prs.slides.add_slide(blank_layout)
    rows, cols = 3, 3
    table = slide3.shapes.add_table(rows, cols, Inches(1), Inches(1), Inches(8), Inches(3)).table
    headers = ["OEM", "EV Sales 2024", "Battery Partner"]
    data = [
        ["Toyota", "450,000", "Panasonic / Prime Planet"],
        ["BMW", "375,000", "Samsung SDI"],
    ]
    for col_idx, header in enumerate(headers):
        table.cell(0, col_idx).text = header
    for row_idx, row in enumerate(data):
        for col_idx, val in enumerate(row):
            table.cell(row_idx + 1, col_idx).text = val

    prs.save(FIXTURES / "sample.pptx")
    print(f"Created: {FIXTURES / 'sample.pptx'}")


if __name__ == "__main__":
    make_sample_pdf()
    make_sample_pptx()
    print("Fixtures ready.")
```

Run it:
```bash
python tests/fixtures/make_fixtures.py
```

**Step 2 — Write `tests/conftest.py`:**

```python
"""Shared pytest fixtures for Phase 1 tests."""
import pytest
import sqlite3
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def sample_pdf_path() -> Path:
    """Path to synthetic sample PDF fixture."""
    path = FIXTURES_DIR / "sample.pdf"
    assert path.exists(), f"Fixture not found: {path}. Run: python tests/fixtures/make_fixtures.py"
    return path


@pytest.fixture(scope="session")
def sample_pptx_path() -> Path:
    """Path to synthetic sample PPTX fixture."""
    path = FIXTURES_DIR / "sample.pptx"
    assert path.exists(), f"Fixture not found: {path}. Run: python tests/fixtures/make_fixtures.py"
    return path


@pytest.fixture
def tmp_db_path(tmp_path) -> Path:
    """Fresh SQLite database path for each test (auto-cleaned by pytest)."""
    return tmp_path / "test_chunks.db"


@pytest.fixture
def tmp_db_conn(tmp_db_path):
    """Open SQLite connection to a fresh temp database. Closes after test."""
    conn = sqlite3.connect(str(tmp_db_path))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
```
  </action>

  <verify>
    <automated>python tests/fixtures/make_fixtures.py && python -c "import fitz; doc = fitz.open('tests/fixtures/sample.pdf'); print('PDF pages:', doc.page_count); doc.close()" && python -c "from pptx import Presentation; prs = Presentation('tests/fixtures/sample.pptx'); print('PPTX slides:', len(prs.slides))"</automated>
  </verify>

  <acceptance_criteria>
    - tests/conftest.py exists and contains `def sample_pdf_path`
    - tests/conftest.py exists and contains `def sample_pptx_path`
    - tests/conftest.py exists and contains `def tmp_db_path`
    - tests/fixtures/sample.pdf exists (non-zero bytes)
    - tests/fixtures/sample.pptx exists (non-zero bytes)
    - `python -c "import fitz; doc = fitz.open('tests/fixtures/sample.pdf'); assert doc.page_count == 2"` exits 0
    - `python -c "from pptx import Presentation; prs = Presentation('tests/fixtures/sample.pptx'); assert len(prs.slides) == 3"` exits 0
  </acceptance_criteria>

  <done>Fixture files exist on disk, are loadable by the respective libraries, conftest.py declares all required shared fixtures.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Write test stubs (all xfail — suite must be green)</name>

  <read_first>
    - .planning/phases/01-document-ingestion-foundation/01-VALIDATION.md (Per-Task Verification Map — full list of required test names)
    - tests/conftest.py (fixture names to inject correctly)
  </read_first>

  <files>
    tests/test_extraction.py
    tests/test_chunking.py
    tests/test_ingest_e2e.py
    tests/test_dedup.py
  </files>

  <action>
Write four test stub files. Every test function is marked `@pytest.mark.xfail(strict=False, reason="stub — implementation pending")` so the suite is GREEN (xfail is not a failure). No implementation modules are imported yet — stubs use `pytest.importorskip` or are structured to fail gracefully.

**`tests/test_extraction.py`:**
```python
"""Tests for PDF and PPTX text extraction.

Stubs: marked xfail until src/ingest/pdf_extractor.py and
src/ingest/pptx_extractor.py are implemented (Plan 02 and Plan 03).
"""
import pytest


@pytest.mark.xfail(strict=False, reason="stub — pdf_extractor not yet implemented")
def test_pdf_extract_text(sample_pdf_path):
    """PDF extractor returns text with page numbers."""
    from src.ingest.pdf_extractor import extract_pdf
    pages = extract_pdf(sample_pdf_path)
    assert len(pages) == 2
    assert pages[0]["page_num"] == 1
    assert "Automotive" in pages[0]["text"]


@pytest.mark.xfail(strict=False, reason="stub — pdf_extractor not yet implemented")
def test_pdf_extract_tables(sample_pdf_path):
    """PDF extractor includes table cell text in page output."""
    from src.ingest.pdf_extractor import extract_pdf
    pages = extract_pdf(sample_pdf_path)
    all_text = " ".join(p["text"] for p in pages)
    assert "Toyota" in all_text  # Table cell content


@pytest.mark.xfail(strict=False, reason="stub — pdf_extractor not yet implemented")
def test_pdf_extract_returns_page_count(sample_pdf_path):
    """Page count in result matches actual PDF page count."""
    from src.ingest.pdf_extractor import extract_pdf
    pages = extract_pdf(sample_pdf_path)
    assert len(pages) == 2


@pytest.mark.xfail(strict=False, reason="stub — pptx_extractor not yet implemented")
def test_pptx_extract_slides(sample_pptx_path):
    """PPTX extractor returns text for each slide with slide numbers."""
    from src.ingest.pptx_extractor import extract_pptx
    slides = extract_pptx(sample_pptx_path)
    assert len(slides) == 3
    assert slides[0]["slide_num"] == 1
    assert "EV Strategy" in slides[0]["text"]


@pytest.mark.xfail(strict=False, reason="stub — pptx_extractor not yet implemented")
def test_pptx_extract_notes(sample_pptx_path):
    """PPTX extractor includes speaker notes in slide output."""
    from src.ingest.pptx_extractor import extract_pptx
    slides = extract_pptx(sample_pptx_path)
    # Slide 1 has notes
    assert "Speaker note" in slides[0]["text"] or "Emphasize" in slides[0]["text"]


@pytest.mark.xfail(strict=False, reason="stub — pptx_extractor not yet implemented")
def test_pptx_extract_tables(sample_pptx_path):
    """PPTX extractor includes table cell text from slide 3."""
    from src.ingest.pptx_extractor import extract_pptx
    slides = extract_pptx(sample_pptx_path)
    all_text = " ".join(s["text"] for s in slides)
    assert "Battery Partner" in all_text  # Table header cell
    assert "Panasonic" in all_text         # Table data cell
```

**`tests/test_chunking.py`:**
```python
"""Tests for text chunking with tiktoken.

Stubs: marked xfail until src/ingest/chunker.py is implemented (Plan 05).
"""
import pytest


@pytest.mark.xfail(strict=False, reason="stub — chunker not yet implemented")
def test_chunk_fixed_size():
    """Chunker produces chunks of at most 512 tokens."""
    from src.ingest.chunker import chunk_text
    text = "word " * 2000  # ~2000 tokens
    chunks = chunk_text(text, chunk_size=512, overlap=100)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk["token_count"] <= 512


@pytest.mark.xfail(strict=False, reason="stub — chunker not yet implemented")
def test_chunk_overlap():
    """Adjacent chunks share approximately 100 tokens of overlap."""
    from src.ingest.chunker import chunk_text
    text = "word " * 2000
    chunks = chunk_text(text, chunk_size=512, overlap=100)
    assert len(chunks) >= 2
    # Overlap: end of chunk[0] text should appear at start of chunk[1] text
    end_words = chunks[0]["text"].split()[-20:]
    start_words = chunks[1]["text"].split()[:20]
    assert any(w in start_words for w in end_words)


@pytest.mark.xfail(strict=False, reason="stub — chunker not yet implemented")
def test_chunk_metadata_fields():
    """Each chunk dict contains required metadata keys."""
    from src.ingest.chunker import chunk_text
    text = "word " * 600
    chunks = chunk_text(text, chunk_size=512, overlap=100)
    required_keys = {"text", "token_count", "chunk_index"}
    for chunk in chunks:
        assert required_keys.issubset(chunk.keys()), f"Missing keys: {required_keys - chunk.keys()}"


@pytest.mark.xfail(strict=False, reason="stub — chunker not yet implemented")
def test_chunk_boundary_quality():
    """Chunker does not split mid-word at chunk boundaries."""
    from src.ingest.chunker import chunk_text
    # Sentence-structured text to test boundary preservation
    sentences = ". ".join([f"Sentence number {i} about automotive supply chains" for i in range(100)])
    chunks = chunk_text(sentences, chunk_size=512, overlap=100)
    for chunk in chunks:
        # Last char should not be mid-word (no trailing partial word ending with letter + no space)
        text = chunk["text"].rstrip()
        # Chunk should not end with a hyphenation artifact
        assert not text.endswith("-"), f"Chunk ends with hyphen: ...{text[-20:]}"


@pytest.mark.xfail(strict=False, reason="stub — chunker not yet implemented")
def test_chunk_token_count_accuracy():
    """Stored token_count matches actual tiktoken encode length."""
    import tiktoken
    from src.ingest.chunker import chunk_text
    enc = tiktoken.get_encoding("cl100k_base")
    text = "The quick brown fox jumps over the lazy dog. " * 100
    chunks = chunk_text(text, chunk_size=512, overlap=100)
    for chunk in chunks:
        actual = len(enc.encode(chunk["text"]))
        assert abs(actual - chunk["token_count"]) <= 2, (
            f"token_count mismatch: stored={chunk['token_count']}, actual={actual}"
        )
```

**`tests/test_dedup.py`:**
```python
"""Tests for SHA-256 file deduplication.

Stubs: marked xfail until src/ingest/store.py is implemented (Plan 04).
"""
import pytest
import tempfile
from pathlib import Path


@pytest.mark.xfail(strict=False, reason="stub — store not yet implemented")
def test_file_hash_sha256(sample_pdf_path):
    """compute_file_hash returns consistent SHA-256 hex string."""
    from src.ingest.store import compute_file_hash
    h1 = compute_file_hash(sample_pdf_path)
    h2 = compute_file_hash(sample_pdf_path)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex = 64 chars
    assert all(c in "0123456789abcdef" for c in h1)


@pytest.mark.xfail(strict=False, reason="stub — store not yet implemented")
def test_file_hash_dedup(tmp_db_conn, sample_pdf_path):
    """is_document_indexed returns True for already-ingested document."""
    from src.ingest.store import ChunkStore
    store = ChunkStore(tmp_db_conn)
    store.init_schema()
    # First ingest: not indexed
    assert not store.is_document_indexed(sample_pdf_path)
    # Insert document
    store.insert_document(
        filename=sample_pdf_path.name,
        file_size_bytes=sample_pdf_path.stat().st_size,
        file_hash=store.compute_file_hash(sample_pdf_path),
        doc_type="pdf",
        total_pages=2,
    )
    # Second check: now indexed
    assert store.is_document_indexed(sample_pdf_path)


@pytest.mark.xfail(strict=False, reason="stub — store not yet implemented")
def test_different_files_have_different_hashes(sample_pdf_path, sample_pptx_path):
    """Different files produce different hashes."""
    from src.ingest.store import compute_file_hash
    h_pdf = compute_file_hash(sample_pdf_path)
    h_pptx = compute_file_hash(sample_pptx_path)
    assert h_pdf != h_pptx
```

**`tests/test_ingest_e2e.py`:**
```python
"""End-to-end ingestion pipeline tests.

Stubs: marked xfail until src/ingest/pipeline.py is implemented (Plan 06).
"""
import pytest
import sqlite3
from pathlib import Path


@pytest.mark.xfail(strict=False, reason="stub — pipeline not yet implemented")
def test_ingest_pdf_complete(sample_pdf_path, tmp_db_path):
    """Full PDF ingest: extraction → chunking → storage produces chunks in DB."""
    from src.ingest.pipeline import ingest_document
    ingest_document(sample_pdf_path, db_path=tmp_db_path)
    conn = sqlite3.connect(str(tmp_db_path))
    count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    conn.close()
    assert doc_count == 1
    assert count > 0


@pytest.mark.xfail(strict=False, reason="stub — pipeline not yet implemented")
def test_ingest_pptx_complete(sample_pptx_path, tmp_db_path):
    """Full PPTX ingest: extraction → chunking → storage produces chunks in DB."""
    from src.ingest.pipeline import ingest_document
    ingest_document(sample_pptx_path, db_path=tmp_db_path)
    conn = sqlite3.connect(str(tmp_db_path))
    count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    conn.close()
    assert count > 0


@pytest.mark.xfail(strict=False, reason="stub — pipeline not yet implemented")
def test_ingest_deduplication(sample_pdf_path, tmp_db_path):
    """Ingesting the same document twice does not create duplicate entries."""
    from src.ingest.pipeline import ingest_document
    ingest_document(sample_pdf_path, db_path=tmp_db_path)
    ingest_document(sample_pdf_path, db_path=tmp_db_path)  # Second call
    conn = sqlite3.connect(str(tmp_db_path))
    doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    conn.close()
    assert doc_count == 1  # Not 2


@pytest.mark.xfail(strict=False, reason="stub — pipeline not yet implemented")
def test_ingest_chunk_metadata_stored(sample_pdf_path, tmp_db_path):
    """Chunks stored in DB include page_num, chunk_index, and token_count."""
    from src.ingest.pipeline import ingest_document
    ingest_document(sample_pdf_path, db_path=tmp_db_path)
    conn = sqlite3.connect(str(tmp_db_path))
    rows = conn.execute(
        "SELECT page_num, chunk_index, token_count FROM chunks WHERE page_num IS NOT NULL LIMIT 5"
    ).fetchall()
    conn.close()
    assert len(rows) > 0
    for row in rows:
        assert row[0] >= 1    # page_num is 1-indexed
        assert row[1] >= 0    # chunk_index is 0-indexed
        assert row[2] > 0     # token_count is positive
```

After writing all four files, run the full test suite to confirm it is green (all xfail pass, none error):
```bash
pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected output: all tests show `XFAIL` status, exit code 0.
  </action>

  <verify>
    <automated>pytest tests/ -v --tb=short 2>&1 | grep -E "(PASSED|FAILED|ERROR|XFAIL|xfail)" | head -30 && pytest tests/ --tb=short -q 2>&1 | tail -5</automated>
  </verify>

  <acceptance_criteria>
    - tests/test_extraction.py contains `def test_pdf_extract_text`
    - tests/test_extraction.py contains `def test_pptx_extract_slides`
    - tests/test_extraction.py contains `def test_pptx_extract_notes`
    - tests/test_extraction.py contains `def test_pptx_extract_tables`
    - tests/test_chunking.py contains `def test_chunk_fixed_size`
    - tests/test_chunking.py contains `def test_chunk_boundary_quality`
    - tests/test_dedup.py contains `def test_file_hash_dedup`
    - tests/test_ingest_e2e.py contains `def test_ingest_pdf_complete`
    - `pytest tests/ -q` exits with code 0 (all xfail, no ERROR, no FAILED)
    - No test shows "ERROR" status in pytest output (ImportError counts as ERROR, not xfail)
  </acceptance_criteria>

  <done>pytest tests/ exits 0 with all stubs showing XFAIL. No errors. Wave 0 complete — all subsequent automated verify commands are now valid.</done>
</task>

</tasks>

<verification>
After all three tasks complete:

1. `python -c "import fitz, pptx, tiktoken, tqdm, pytest; print('ok')"` — exits 0
2. `python -c "import fitz; doc = fitz.open('tests/fixtures/sample.pdf'); assert doc.page_count == 2; print('pdf ok')"` — exits 0
3. `python -c "from pptx import Presentation; prs = Presentation('tests/fixtures/sample.pptx'); assert len(prs.slides) == 3; print('pptx ok')"` — exits 0
4. `pytest tests/ -q` — exits 0, all XFAIL
</verification>

<success_criteria>
- requirements.txt present with all 6 dependencies
- tests/fixtures/sample.pdf — 2 pages, loadable by PyMuPDF
- tests/fixtures/sample.pptx — 3 slides with notes and table, loadable by python-pptx
- tests/conftest.py — declares sample_pdf_path, sample_pptx_path, tmp_db_path, tmp_db_conn fixtures
- Four test files present with all stubs from VALIDATION.md Per-Task Verification Map
- pytest exits 0 (all xfail, zero errors)
</success_criteria>

<output>
After completion, create `.planning/phases/01-document-ingestion-foundation/01-01-SUMMARY.md`
</output>
