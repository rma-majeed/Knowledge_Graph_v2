---
phase: 01-document-ingestion-foundation
plan: 04
type: execute
wave: 2
depends_on:
  - "01-PLAN-01-test-infrastructure"
files_modified:
  - src/ingest/store.py
  - src/db/schema.sql
autonomous: true
requirements:
  - INGEST-01
  - INGEST-02
  - INGEST-03

must_haves:
  truths:
    - "ChunkStore.init_schema() creates documents and chunks tables with correct columns"
    - "ChunkStore.insert_document() stores a document row and returns its doc_id"
    - "ChunkStore.insert_chunks() batch-inserts chunk rows linked to doc_id"
    - "ChunkStore.is_document_indexed() returns True if file_hash already exists in documents"
    - "compute_file_hash() returns a 64-character lowercase hex SHA-256 string"
    - "All test_dedup.py tests pass (not xfail)"
  artifacts:
    - path: "src/ingest/store.py"
      provides: "ChunkStore class and compute_file_hash function"
      exports: ["ChunkStore", "compute_file_hash"]
      contains: "class ChunkStore"
    - path: "src/db/schema.sql"
      provides: "Authoritative SQL schema for documents and chunks tables"
      contains: "CREATE TABLE documents"
  key_links:
    - from: "src/ingest/store.py"
      to: "sqlite3 (Python stdlib)"
      via: "import sqlite3"
      pattern: "import sqlite3"
    - from: "src/ingest/store.py"
      to: "hashlib (Python stdlib)"
      via: "import hashlib"
      pattern: "import hashlib"
    - from: "tests/test_dedup.py"
      to: "src/ingest/store.py"
      via: "from src.ingest.store import ChunkStore, compute_file_hash"
      pattern: "from src.ingest.store import"
---

<objective>
Implement the SQLite chunk store: schema creation, document insertion with SHA-256 deduplication, and bulk chunk insertion. This is the persistence layer that both the PDF and PPTX extractors will write to.

Purpose: Provides the storage foundation that INGEST-01, INGEST-02, and INGEST-03 all depend on. The pipeline (Plan 06) writes extraction output here; the embedding phase (Phase 2) reads from here.

Output: src/ingest/store.py with ChunkStore class and compute_file_hash() function. src/db/schema.sql as authoritative schema reference. All dedup tests pass.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/phases/01-document-ingestion-foundation/01-RESEARCH.md
@tests/conftest.py
@tests/test_dedup.py

<interfaces>
<!-- Contracts derived from test_dedup.py and pipeline requirements. -->

What tests/test_dedup.py expects:
```python
from src.ingest.store import ChunkStore, compute_file_hash

# compute_file_hash(path) -> str: 64-char lowercase hex SHA-256
h = compute_file_hash(sample_pdf_path)
assert len(h) == 64
assert all(c in "0123456789abcdef" for c in h)

# ChunkStore wraps a sqlite3.Connection
store = ChunkStore(conn)
store.init_schema()

# is_document_indexed checks by file hash
assert not store.is_document_indexed(sample_pdf_path)
store.insert_document(
    filename=..., file_size_bytes=..., file_hash=..., doc_type="pdf", total_pages=2
)
assert store.is_document_indexed(sample_pdf_path)
```

What pipeline (Plan 06) will call:
```python
store = ChunkStore(conn)
store.init_schema()
doc_id = store.insert_document(filename, file_size_bytes, file_hash, doc_type, total_pages)
store.insert_chunks(doc_id, chunks_list)
# chunks_list items: {"page_num": int, "chunk_index": int, "text": str, "token_count": int}
```

SQL Schema (from RESEARCH.md):
- documents(doc_id PK, filename UNIQUE, file_size_bytes, file_hash UNIQUE, doc_type, total_pages, created_at, indexed_at)
- chunks(chunk_id PK, doc_id FK, page_num, chunk_index, chunk_text, token_count, embedding_flag DEFAULT 0, created_at)
- Indexes: idx_documents_hash, idx_chunks_doc_id, idx_chunks_page_num, idx_chunks_embedding_flag, idx_chunks_doc_page_index
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write schema.sql and implement ChunkStore in store.py</name>

  <read_first>
    - tests/test_dedup.py (exact method signatures and assertions)
    - tests/conftest.py (tmp_db_conn fixture: provides sqlite3.Connection with row_factory set)
    - .planning/phases/01-document-ingestion-foundation/01-RESEARCH.md (SQLite Schema section, lines 268-364)
  </read_first>

  <files>
    src/db/__init__.py
    src/db/schema.sql
    src/ingest/store.py
  </files>

  <behavior>
    - compute_file_hash(path) reads file in 8KB chunks and returns 64-char lowercase hex SHA-256
    - ChunkStore(conn): accepts sqlite3.Connection, stores as self.conn
    - init_schema() creates documents + chunks tables and all 5 indexes if not exist (idempotent)
    - insert_document() returns integer doc_id (conn.lastrowid after INSERT)
    - is_document_indexed(filepath) computes hash from file, queries documents.file_hash, returns bool
    - insert_chunks(doc_id, chunks) uses executemany for batch insert — each chunk dict has page_num, chunk_index, text, token_count keys
    - All operations call conn.commit() after write operations
  </behavior>

  <action>
Create `src/db/__init__.py` (empty).

Create `src/db/schema.sql` with the authoritative schema:

```sql
-- Automotive Consulting GraphRAG — Phase 1 SQLite Schema
-- This file is the source of truth. ChunkStore.init_schema() executes this.

CREATE TABLE IF NOT EXISTS documents (
    doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL UNIQUE,
    file_size_bytes INTEGER,
    file_hash TEXT NOT NULL UNIQUE,  -- SHA-256 hex (64 chars) for deduplication
    doc_type TEXT NOT NULL,          -- 'pdf' or 'pptx'
    total_pages INTEGER,             -- Total page or slide count
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    indexed_at TIMESTAMP             -- NULL until embedding phase marks complete
);

CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(file_hash);
CREATE INDEX IF NOT EXISTS idx_documents_filename ON documents(filename);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL,
    page_num INTEGER,       -- 1-indexed page (PDF) or slide (PPTX) number
    chunk_index INTEGER,    -- 0-indexed position within the document
    chunk_text TEXT NOT NULL,
    token_count INTEGER,    -- Token count via tiktoken cl100k_base
    embedding_flag INTEGER DEFAULT 0,  -- 0=pending, 1=embedded, -1=skip
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_page_num ON chunks(doc_id, page_num);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_flag ON chunks(embedding_flag);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_page_index ON chunks(doc_id, page_num, chunk_index);
```

Create `src/ingest/store.py`:

```python
"""SQLite chunk store for document ingestion.

Provides:
- compute_file_hash(): SHA-256 file hashing for deduplication
- ChunkStore: CRUD operations for documents and chunks tables

Schema: src/db/schema.sql (authoritative)

Usage:
    import sqlite3
    from src.ingest.store import ChunkStore, compute_file_hash

    conn = sqlite3.connect("chunks.db")
    store = ChunkStore(conn)
    store.init_schema()

    if not store.is_document_indexed(filepath):
        doc_id = store.insert_document(
            filename=filepath.name,
            file_size_bytes=filepath.stat().st_size,
            file_hash=compute_file_hash(filepath),
            doc_type="pdf",
            total_pages=12,
        )
        store.insert_chunks(doc_id, chunks)
"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Union


def compute_file_hash(filepath: Union[str, Path], algorithm: str = "sha256") -> str:
    """Compute SHA-256 hash of a file using 8KB read chunks.

    Reads the file in 8KB blocks to avoid loading large files into memory.

    Args:
        filepath: Path to the file to hash.
        algorithm: Hash algorithm name (default: 'sha256').

    Returns:
        Lowercase hex digest string (64 chars for SHA-256).

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found for hashing: {filepath}")

    h = hashlib.new(algorithm)
    with open(filepath, "rb") as f:
        while True:
            block = f.read(8192)  # 8KB chunks to avoid memory bloat on large files
            if not block:
                break
            h.update(block)
    return h.hexdigest()


class ChunkStore:
    """Wrapper around a SQLite connection for document and chunk storage.

    The caller is responsible for creating and closing the connection.
    All write operations commit immediately.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialise with an open SQLite connection.

        Args:
            conn: An open sqlite3.Connection object.
        """
        self.conn = conn

    def init_schema(self) -> None:
        """Create documents and chunks tables and indexes if they do not exist.

        Idempotent: safe to call on an existing database.
        Reads schema from src/db/schema.sql relative to this file.
        """
        schema_path = Path(__file__).parent.parent / "db" / "schema.sql"
        if schema_path.exists():
            sql = schema_path.read_text(encoding="utf-8")
        else:
            # Fallback: inline schema (matches schema.sql exactly)
            sql = _INLINE_SCHEMA
        self.conn.executescript(sql)
        self.conn.commit()

    def is_document_indexed(self, filepath: Union[str, Path]) -> bool:
        """Return True if a document with the same SHA-256 hash is already in documents table.

        Args:
            filepath: Path to the file to check.

        Returns:
            True if file hash already exists in documents.file_hash column.
        """
        file_hash = compute_file_hash(filepath)
        row = self.conn.execute(
            "SELECT doc_id FROM documents WHERE file_hash = ?", (file_hash,)
        ).fetchone()
        return row is not None

    def insert_document(
        self,
        filename: str,
        file_size_bytes: int,
        file_hash: str,
        doc_type: str,
        total_pages: int,
    ) -> int:
        """Insert a document record and return its doc_id.

        Args:
            filename: Base filename (not full path).
            file_size_bytes: File size in bytes.
            file_hash: SHA-256 hex digest.
            doc_type: 'pdf' or 'pptx'.
            total_pages: Total page or slide count.

        Returns:
            Integer doc_id assigned by SQLite AUTOINCREMENT.

        Raises:
            sqlite3.IntegrityError: If filename or file_hash already exists (duplicate).
        """
        cur = self.conn.execute(
            """INSERT INTO documents (filename, file_size_bytes, file_hash, doc_type, total_pages)
               VALUES (?, ?, ?, ?, ?)""",
            (filename, file_size_bytes, file_hash, doc_type, total_pages),
        )
        self.conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def insert_chunks(self, doc_id: int, chunks: list[dict]) -> None:
        """Batch-insert chunk records linked to a document.

        Args:
            doc_id: The doc_id from insert_document().
            chunks: List of dicts, each with keys:
                - page_num (int): 1-indexed page or slide number
                - chunk_index (int): 0-indexed position within document
                - text (str): Raw chunk text
                - token_count (int): Token count from tiktoken

        Returns:
            None. Commits after bulk insert.
        """
        rows = [
            (doc_id, c["page_num"], c["chunk_index"], c["text"], c["token_count"], 0)
            for c in chunks
        ]
        self.conn.executemany(
            """INSERT INTO chunks (doc_id, page_num, chunk_index, chunk_text, token_count, embedding_flag)
               VALUES (?, ?, ?, ?, ?, ?)""",
            rows,
        )
        self.conn.commit()

    def get_chunks_for_embedding(self, batch_size: int = 100) -> list[sqlite3.Row]:
        """Retrieve a batch of chunks pending embedding (embedding_flag=0).

        Args:
            batch_size: Maximum number of chunks to return.

        Returns:
            List of sqlite3.Row objects with chunk_id and chunk_text.
        """
        return self.conn.execute(
            "SELECT chunk_id, chunk_text FROM chunks WHERE embedding_flag = 0 LIMIT ?",
            (batch_size,),
        ).fetchall()

    def mark_chunks_embedded(self, chunk_ids: list[int]) -> None:
        """Mark chunks as embedded (embedding_flag=1).

        Args:
            chunk_ids: List of chunk_id values to mark embedded.
        """
        self.conn.executemany(
            "UPDATE chunks SET embedding_flag = 1 WHERE chunk_id = ?",
            [(cid,) for cid in chunk_ids],
        )
        self.conn.commit()


# Inline schema fallback (matches src/db/schema.sql exactly)
_INLINE_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL UNIQUE,
    file_size_bytes INTEGER,
    file_hash TEXT NOT NULL UNIQUE,
    doc_type TEXT NOT NULL,
    total_pages INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    indexed_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(file_hash);
CREATE INDEX IF NOT EXISTS idx_documents_filename ON documents(filename);
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL,
    page_num INTEGER,
    chunk_index INTEGER,
    chunk_text TEXT NOT NULL,
    token_count INTEGER,
    embedding_flag INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_page_num ON chunks(doc_id, page_num);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_flag ON chunks(embedding_flag);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_page_index ON chunks(doc_id, page_num, chunk_index);
"""
```

After writing both files, remove the `@pytest.mark.xfail` decorators from all tests in `tests/test_dedup.py`:
- `test_file_hash_sha256`
- `test_file_hash_dedup`
- `test_different_files_have_different_hashes`

Run the dedup tests:
```bash
pytest tests/test_dedup.py -v
```
  </action>

  <verify>
    <automated>pytest tests/test_dedup.py -v</automated>
  </verify>

  <acceptance_criteria>
    - src/db/schema.sql exists and contains `CREATE TABLE IF NOT EXISTS documents`
    - src/db/schema.sql contains `CREATE TABLE IF NOT EXISTS chunks`
    - src/db/schema.sql contains `file_hash TEXT NOT NULL UNIQUE`
    - src/db/schema.sql contains `embedding_flag INTEGER DEFAULT 0`
    - src/ingest/store.py exists and contains `class ChunkStore`
    - src/ingest/store.py contains `def compute_file_hash(`
    - src/ingest/store.py contains `def init_schema(`
    - src/ingest/store.py contains `def is_document_indexed(`
    - src/ingest/store.py contains `def insert_document(`
    - src/ingest/store.py contains `def insert_chunks(`
    - src/ingest/store.py contains `import hashlib`
    - `pytest tests/test_dedup.py::test_file_hash_sha256 -v` exits 0 with PASSED
    - `pytest tests/test_dedup.py::test_file_hash_dedup -v` exits 0 with PASSED
    - `pytest tests/test_dedup.py::test_different_files_have_different_hashes -v` exits 0 with PASSED
    - `pytest tests/ -q` exits 0 (no FAILED, no ERROR)
  </acceptance_criteria>

  <done>ChunkStore implemented with schema creation, document insert, chunk bulk-insert, and SHA-256 deduplication. All 3 dedup tests pass. Full test suite remains green.</done>
</task>

</tasks>

<verification>
After plan complete:
1. `pytest tests/test_dedup.py -v` — 3 tests PASSED
2. `pytest tests/ -q` — exits 0
3. `python -c "from src.ingest.store import ChunkStore, compute_file_hash; h = compute_file_hash('tests/fixtures/sample.pdf'); assert len(h) == 64; print('hash ok:', h[:8])"` — exits 0
4. `python -c "import sqlite3; from src.ingest.store import ChunkStore; conn = sqlite3.connect(':memory:'); s = ChunkStore(conn); s.init_schema(); tables = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall(); print([t[0] for t in tables])"` — prints `['documents', 'chunks']`
</verification>

<success_criteria>
- schema.sql is the authoritative schema reference (documents + chunks + 5 indexes)
- ChunkStore wraps a sqlite3 connection with clean insert/query methods
- compute_file_hash() returns stable 64-char SHA-256 hex
- Deduplication prevents re-insertion of identical files
- All 3 test_dedup.py tests pass
</success_criteria>

<output>
After completion, create `.planning/phases/01-document-ingestion-foundation/01-04-SUMMARY.md`
</output>
