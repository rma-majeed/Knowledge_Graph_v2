---
phase: 01-document-ingestion-foundation
plan: 06
type: execute
wave: 4
depends_on:
  - "01-PLAN-02-pdf-extractor"
  - "01-PLAN-03-pptx-extractor"
  - "01-PLAN-04-sqlite-chunk-store"
  - "01-PLAN-05-text-chunker"
files_modified:
  - src/ingest/pipeline.py
  - src/main.py
autonomous: true
requirements:
  - INGEST-01
  - INGEST-02
  - INGEST-03

must_haves:
  truths:
    - "ingest_document(pdf_path, db_path) inserts 1 document row and N chunk rows into SQLite"
    - "ingest_document(pptx_path, db_path) inserts 1 document row and N chunk rows into SQLite"
    - "Calling ingest_document twice on the same file inserts exactly 1 document row (deduplication)"
    - "Chunks stored in DB have page_num >= 1, chunk_index >= 0, token_count > 0"
    - "All test_ingest_e2e.py tests pass (not xfail)"
    - "CLI: python src/main.py ingest --path tests/fixtures/ completes without error and prints chunk count"
  artifacts:
    - path: "src/ingest/pipeline.py"
      provides: "ingest_document() end-to-end function wiring extraction + chunking + storage"
      exports: ["ingest_document", "ingest_directory"]
      contains: "def ingest_document("
    - path: "src/main.py"
      provides: "CLI entry point for batch ingestion"
      contains: "if __name__ == \"__main__\""
  key_links:
    - from: "src/ingest/pipeline.py"
      to: "src/ingest/pdf_extractor.py"
      via: "from src.ingest.pdf_extractor import extract_pdf"
      pattern: "from src.ingest.pdf_extractor import extract_pdf"
    - from: "src/ingest/pipeline.py"
      to: "src/ingest/pptx_extractor.py"
      via: "from src.ingest.pptx_extractor import extract_pptx"
      pattern: "from src.ingest.pptx_extractor import extract_pptx"
    - from: "src/ingest/pipeline.py"
      to: "src/ingest/chunker.py"
      via: "from src.ingest.chunker import chunk_text"
      pattern: "from src.ingest.chunker import chunk_text"
    - from: "src/ingest/pipeline.py"
      to: "src/ingest/store.py"
      via: "from src.ingest.store import ChunkStore, compute_file_hash"
      pattern: "from src.ingest.store import ChunkStore"
---

<objective>
Wire all Phase 1 components into an end-to-end ingestion pipeline. ingest_document() accepts a single file path and a SQLite DB path, runs the full extraction → chunking → storage flow, and handles deduplication. ingest_directory() ingests all PDF and PPTX files in a folder. src/main.py provides a CLI entry point.

Purpose: This plan closes the loop on INGEST-01, INGEST-02, and INGEST-03 together. It also validates the performance target: 100-document sample in under 30 seconds.

Output: Fully wired pipeline. All 4 e2e tests pass. CLI works. Phase 1 is complete.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/phases/01-document-ingestion-foundation/01-RESEARCH.md
@tests/conftest.py
@tests/test_ingest_e2e.py

<interfaces>
<!-- All upstream contracts. Executor reads these instead of exploring codebase. -->

From src/ingest/pdf_extractor.py (Plan 02):
```python
def extract_pdf(filepath: Union[str, Path]) -> list[dict]:
    # Returns: [{"page_num": int (1-indexed), "text": str}, ...]
```

From src/ingest/pptx_extractor.py (Plan 03):
```python
def extract_pptx(filepath: Union[str, Path]) -> list[dict]:
    # Returns: [{"slide_num": int (1-indexed), "text": str}, ...]
```

From src/ingest/chunker.py (Plan 05):
```python
def chunk_text(text: str, chunk_size: int = 512, overlap: int = 100) -> list[dict]:
    # Returns: [{"text": str, "token_count": int, "chunk_index": int}, ...]
```

From src/ingest/store.py (Plan 04):
```python
def compute_file_hash(filepath) -> str  # 64-char SHA-256 hex

class ChunkStore:
    def __init__(self, conn: sqlite3.Connection) -> None
    def init_schema(self) -> None
    def is_document_indexed(self, filepath) -> bool
    def insert_document(self, filename, file_size_bytes, file_hash, doc_type, total_pages) -> int
    def insert_chunks(self, doc_id: int, chunks: list[dict]) -> None
    # insert_chunks expects each chunk to have: page_num, chunk_index, text, token_count
```

What tests/test_ingest_e2e.py expects:
```python
from src.ingest.pipeline import ingest_document

ingest_document(sample_pdf_path, db_path=tmp_db_path)
# Creates documents + chunks tables, inserts 1 document row, N chunk rows
# conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
# conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] > 0
# Calling twice: still exactly 1 document row (dedup)
# Chunk rows: page_num >= 1, chunk_index >= 0, token_count > 0

ingest_document(sample_pptx_path, db_path=tmp_db_path)
# Same contract for PPTX files
```

Note: pdf_extractor returns "page_num", pptx_extractor returns "slide_num".
Pipeline must normalize both to "page_num" before calling store.insert_chunks().
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement pipeline.py — ingest_document() and ingest_directory()</name>

  <read_first>
    - tests/test_ingest_e2e.py (exact assertions all 4 tests make)
    - tests/conftest.py (tmp_db_path is a pathlib.Path, not an open connection)
    - src/ingest/pdf_extractor.py (return shape: list of {"page_num": int, "text": str})
    - src/ingest/pptx_extractor.py (return shape: list of {"slide_num": int, "text": str})
    - src/ingest/chunker.py (chunk_text return shape: list of {"text", "token_count", "chunk_index"})
    - src/ingest/store.py (ChunkStore API: init_schema, is_document_indexed, insert_document, insert_chunks)
  </read_first>

  <files>src/ingest/pipeline.py</files>

  <behavior>
    - ingest_document(filepath, db_path) opens a sqlite3 connection to db_path, calls ChunkStore(conn).init_schema(), skips if is_document_indexed(), otherwise extracts + chunks + inserts
    - ingest_document with a PDF: calls extract_pdf(), iterates pages, calls chunk_text(page["text"]) per page, collects all chunks with page_num set, calls insert_chunks()
    - ingest_document with a PPTX: calls extract_pptx(), iterates slides, normalizes "slide_num" key to "page_num" in chunk dicts before insert_chunks()
    - ingest_document returns a dict: {"doc_id": int | None, "chunks_inserted": int, "skipped": bool}
    - Calling ingest_document twice on same file: second call returns {"skipped": True, "chunks_inserted": 0}
    - ingest_directory(folder_path, db_path) calls ingest_document for each .pdf and .pptx in folder (non-recursive), returns list of result dicts
    - ingest_directory uses tqdm progress bar when processing > 1 file
    - Empty page text (after strip) is skipped — no chunk_text call on empty strings
  </behavior>

  <action>
Create `src/ingest/pipeline.py`:

```python
"""End-to-end document ingestion pipeline.

Wires: extraction (PDF/PPTX) → chunking (tiktoken) → storage (SQLite)

Usage:
    from src.ingest.pipeline import ingest_document, ingest_directory

    # Single file
    result = ingest_document("report.pdf", db_path="data/chunks.db")
    print(f"Inserted {result['chunks_inserted']} chunks")

    # Directory batch
    results = ingest_directory("documents/", db_path="data/chunks.db")
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Union

from tqdm import tqdm

from src.ingest.chunker import chunk_text
from src.ingest.pdf_extractor import extract_pdf
from src.ingest.pptx_extractor import extract_pptx
from src.ingest.store import ChunkStore, compute_file_hash

# Supported file extensions
_SUPPORTED_EXTENSIONS = {".pdf", ".pptx"}


def ingest_document(
    filepath: Union[str, Path],
    db_path: Union[str, Path],
    chunk_size: int = 512,
    overlap: int = 100,
) -> dict:
    """Ingest a single PDF or PPTX document into the SQLite chunk store.

    Full pipeline: validate → deduplicate → extract → chunk → store.

    Args:
        filepath: Path to the PDF or PPTX file.
        db_path: Path to the SQLite database file (created if not exists).
        chunk_size: Tokens per chunk (default: 512).
        overlap: Overlap tokens between adjacent chunks (default: 100).

    Returns:
        Dict with keys:
        - "doc_id": int | None — doc_id assigned if newly ingested; None if skipped
        - "chunks_inserted": int — number of chunks written to DB
        - "skipped": bool — True if document was already indexed (dedup)
        - "filename": str — base filename of the document

    Raises:
        ValueError: If file extension is not .pdf or .pptx.
        FileNotFoundError: If file does not exist.
    """
    filepath = Path(filepath)
    db_path = Path(db_path)

    if not filepath.exists():
        raise FileNotFoundError(f"Document not found: {filepath}")

    suffix = filepath.suffix.lower()
    if suffix not in _SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {suffix!r}. Supported: {_SUPPORTED_EXTENSIONS}"
        )

    # Open DB connection (creates file if not exists)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrent read performance in Phase 2+
    conn.execute("PRAGMA journal_mode=WAL")

    try:
        store = ChunkStore(conn)
        store.init_schema()

        # Deduplication check
        if store.is_document_indexed(filepath):
            return {
                "doc_id": None,
                "chunks_inserted": 0,
                "skipped": True,
                "filename": filepath.name,
            }

        # Extract text from document
        if suffix == ".pdf":
            pages = extract_pdf(filepath)
            doc_type = "pdf"
            total_pages = len(pages)
            # Normalize: PDF pages use "page_num" key (already 1-indexed)
            page_items = [{"page_num": p["page_num"], "text": p["text"]} for p in pages]
        else:  # .pptx
            slides = extract_pptx(filepath)
            doc_type = "pptx"
            total_pages = len(slides)
            # Normalize: PPTX uses "slide_num" → map to "page_num" for uniform storage
            page_items = [{"page_num": s["slide_num"], "text": s["text"]} for s in slides]

        # Insert document record
        file_hash = compute_file_hash(filepath)
        doc_id = store.insert_document(
            filename=filepath.name,
            file_size_bytes=filepath.stat().st_size,
            file_hash=file_hash,
            doc_type=doc_type,
            total_pages=total_pages,
        )

        # Chunk each page/slide and collect all chunks with page_num
        all_chunks: list[dict] = []
        for item in page_items:
            text = item["text"].strip()
            if not text:
                continue  # Skip empty pages/slides

            page_chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
            for chunk in page_chunks:
                all_chunks.append(
                    {
                        "page_num": item["page_num"],
                        "chunk_index": chunk["chunk_index"],
                        "text": chunk["text"],
                        "token_count": chunk["token_count"],
                    }
                )

        # Bulk insert all chunks
        if all_chunks:
            store.insert_chunks(doc_id, all_chunks)

        return {
            "doc_id": doc_id,
            "chunks_inserted": len(all_chunks),
            "skipped": False,
            "filename": filepath.name,
        }

    finally:
        conn.close()


def ingest_directory(
    folder_path: Union[str, Path],
    db_path: Union[str, Path],
    chunk_size: int = 512,
    overlap: int = 100,
) -> list[dict]:
    """Ingest all PDF and PPTX files in a folder (non-recursive).

    Args:
        folder_path: Directory containing documents to ingest.
        db_path: Path to the SQLite database file.
        chunk_size: Tokens per chunk (default: 512).
        overlap: Overlap tokens between adjacent chunks (default: 100).

    Returns:
        List of result dicts from ingest_document(), one per file.
        Includes both ingested and skipped (deduplicated) files.
    """
    folder_path = Path(folder_path)
    if not folder_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder_path}")

    # Collect supported files (sorted for deterministic order)
    files = sorted(
        f for f in folder_path.iterdir()
        if f.is_file() and f.suffix.lower() in _SUPPORTED_EXTENSIONS
    )

    if not files:
        return []

    results: list[dict] = []
    for filepath in tqdm(files, desc="Ingesting documents", unit="doc", disable=len(files) == 1):
        result = ingest_document(
            filepath, db_path=db_path, chunk_size=chunk_size, overlap=overlap
        )
        results.append(result)

    return results
```

After writing the file, remove the `@pytest.mark.xfail` decorators from all tests in `tests/test_ingest_e2e.py`:
- `test_ingest_pdf_complete`
- `test_ingest_pptx_complete`
- `test_ingest_deduplication`
- `test_ingest_chunk_metadata_stored`

Run the e2e tests:
```bash
pytest tests/test_ingest_e2e.py -v
```
  </action>

  <verify>
    <automated>pytest tests/test_ingest_e2e.py -v</automated>
  </verify>

  <acceptance_criteria>
    - src/ingest/pipeline.py exists and contains `def ingest_document(`
    - src/ingest/pipeline.py contains `def ingest_directory(`
    - src/ingest/pipeline.py contains `from src.ingest.pdf_extractor import extract_pdf`
    - src/ingest/pipeline.py contains `from src.ingest.pptx_extractor import extract_pptx`
    - src/ingest/pipeline.py contains `from src.ingest.chunker import chunk_text`
    - src/ingest/pipeline.py contains `from src.ingest.store import ChunkStore`
    - src/ingest/pipeline.py contains `slide_num` key normalization to `page_num`
    - src/ingest/pipeline.py contains `"skipped": True` for dedup path
    - `pytest tests/test_ingest_e2e.py::test_ingest_pdf_complete -v` exits 0 with PASSED
    - `pytest tests/test_ingest_e2e.py::test_ingest_pptx_complete -v` exits 0 with PASSED
    - `pytest tests/test_ingest_e2e.py::test_ingest_deduplication -v` exits 0 with PASSED
    - `pytest tests/test_ingest_e2e.py::test_ingest_chunk_metadata_stored -v` exits 0 with PASSED
    - `pytest tests/ -q` exits 0 (no FAILED, no ERROR — all stubs promoted or still xfail)
  </acceptance_criteria>

  <done>ingest_document() wires all Phase 1 components. All 4 e2e tests pass. Full test suite green.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Create CLI entry point (src/main.py) and validate full test suite</name>

  <read_first>
    - src/ingest/pipeline.py (ingest_directory signature and return shape)
    - tests/test_ingest_e2e.py (confirm all tests now pass after Task 1)
  </read_first>

  <files>src/main.py</files>

  <action>
Create `src/main.py` — a minimal CLI that exposes `ingest` subcommand:

```python
"""Automotive Consulting GraphRAG Agent — CLI entry point.

Usage:
    python src/main.py ingest --path <folder_or_file> [--db <db_path>]

Examples:
    python src/main.py ingest --path documents/
    python src/main.py ingest --path report.pdf --db data/chunks.db
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path


def cmd_ingest(args: argparse.Namespace) -> int:
    """Run the ingestion pipeline on a file or directory."""
    from src.ingest.pipeline import ingest_directory, ingest_document

    target = Path(args.path)
    db_path = Path(args.db)

    # Ensure data directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    start = time.perf_counter()

    if target.is_dir():
        results = ingest_directory(target, db_path=db_path)
        ingested = [r for r in results if not r["skipped"]]
        skipped = [r for r in results if r["skipped"]]
        total_chunks = sum(r["chunks_inserted"] for r in ingested)
        elapsed = time.perf_counter() - start
        print(
            f"\nIngestion complete in {elapsed:.2f}s\n"
            f"  Documents ingested: {len(ingested)}\n"
            f"  Documents skipped (already indexed): {len(skipped)}\n"
            f"  Total chunks stored: {total_chunks}\n"
            f"  Database: {db_path}"
        )
    elif target.is_file():
        result = ingest_document(target, db_path=db_path)
        elapsed = time.perf_counter() - start
        if result["skipped"]:
            print(f"Skipped (already indexed): {result['filename']} ({elapsed:.2f}s)")
        else:
            print(
                f"Ingested: {result['filename']} — "
                f"{result['chunks_inserted']} chunks in {elapsed:.2f}s"
            )
    else:
        print(f"Error: {target} is not a file or directory.", file=sys.stderr)
        return 1

    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    """Print ingestion statistics from the database."""
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(str(db_path))
    doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    pending = conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE embedding_flag = 0"
    ).fetchone()[0]
    conn.close()

    print(
        f"Database: {db_path}\n"
        f"  Documents: {doc_count}\n"
        f"  Chunks total: {chunk_count}\n"
        f"  Chunks pending embedding: {pending}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="graphrag",
        description="Automotive Consulting GraphRAG Agent",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ingest subcommand
    p_ingest = subparsers.add_parser("ingest", help="Ingest PDF/PPTX documents")
    p_ingest.add_argument("--path", required=True, help="File or directory to ingest")
    p_ingest.add_argument(
        "--db", default="data/chunks.db", help="SQLite database path (default: data/chunks.db)"
    )
    p_ingest.set_defaults(func=cmd_ingest)

    # stats subcommand
    p_stats = subparsers.add_parser("stats", help="Show database statistics")
    p_stats.add_argument(
        "--db", default="data/chunks.db", help="SQLite database path (default: data/chunks.db)"
    )
    p_stats.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

After writing the file, run the CLI against the fixtures folder to confirm it works end-to-end:

```bash
python src/main.py ingest --path tests/fixtures/ --db /tmp/test_cli_chunks.db
```

Expected output (example):
```
Ingestion complete in 0.xx s
  Documents ingested: 2
  Documents skipped (already indexed): 0
  Total chunks stored: N
  Database: /tmp/test_cli_chunks.db
```

Then run the full test suite one final time to confirm everything is green:
```bash
pytest tests/ -v --tb=short
```
  </action>

  <verify>
    <automated>pytest tests/ -v --tb=short 2>&1 | tail -20 && python src/main.py ingest --path tests/fixtures/ --db /tmp/phase1_final_check.db 2>&1</automated>
  </verify>

  <acceptance_criteria>
    - src/main.py exists and contains `def main(`
    - src/main.py contains `if __name__ == "__main__"`
    - src/main.py contains `subparsers.add_parser("ingest"`
    - src/main.py contains `from src.ingest.pipeline import ingest_directory, ingest_document`
    - `python src/main.py ingest --path tests/fixtures/ --db /tmp/cli_test.db` exits 0
    - CLI output contains "Documents ingested: 2" (sample.pdf + sample.pptx)
    - CLI output contains "Total chunks stored:" followed by a number > 0
    - `pytest tests/ -q` exits 0 — all test_extraction.py, test_chunking.py, test_dedup.py, test_ingest_e2e.py tests PASSED
  </acceptance_criteria>

  <done>CLI entry point working. Full test suite green. Phase 1 complete: PDF extraction, PPTX extraction, chunking, deduplication, and storage all implemented and tested end-to-end.</done>
</task>

</tasks>

<verification>
Final Phase 1 verification:

1. `pytest tests/ -v` — ALL tests PASSED (no FAILED, no ERROR, no xfail remaining in extraction/chunking/dedup/e2e stubs)
2. `python src/main.py ingest --path tests/fixtures/ --db /tmp/p1_verify.db` — exits 0, prints "Documents ingested: 2"
3. `python src/main.py stats --db /tmp/p1_verify.db` — shows doc_count=2, chunk_count > 0
4. Deduplication check: run ingest again on same folder → "Documents skipped: 2"
5. `python -c "import sqlite3; conn = sqlite3.connect('/tmp/p1_verify.db'); print(conn.execute('SELECT COUNT(*) FROM chunks WHERE page_num IS NOT NULL AND token_count > 0').fetchone()[0], 'valid chunks')"` — prints a positive number
</verification>

<success_criteria>
- ingest_document() correctly routes PDF to extract_pdf() and PPTX to extract_pptx()
- slide_num is normalized to page_num before storage
- Deduplication: identical file ingested twice = 1 document row
- All 4 test_ingest_e2e.py tests pass
- CLI: `python src/main.py ingest --path tests/fixtures/` completes, reports chunk count
- Full suite: pytest tests/ exits 0 with all stubs promoted to PASSED
- Phase 1 requirements closed: INGEST-01, INGEST-02, INGEST-03 all implemented and tested
</success_criteria>

<output>
After completion, create `.planning/phases/01-document-ingestion-foundation/01-06-SUMMARY.md`

Also update `.planning/STATE.md`:
- Set Current Phase to "Phase 1 Complete"
- Set Current Plan to "All Phase 1 plans complete"
- Update Progress to reflect Phase 1 completion
- Mark INGEST-01, INGEST-02, INGEST-03 as done in the Decisions Log or add a completion note
</output>
