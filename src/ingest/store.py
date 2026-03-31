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

    def compute_file_hash(self, filepath: Union[str, Path]) -> str:
        """Instance method alias for module-level compute_file_hash().

        Delegates to the module-level function for consistent hashing.

        Args:
            filepath: Path to the file to hash.

        Returns:
            Lowercase hex digest string (64 chars for SHA-256).
        """
        return compute_file_hash(filepath)

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
        # Phase 7: backward-compatible schema additions
        self.add_enriched_text_column()
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS chunk_parents ("
            "    child_chunk_id  INTEGER PRIMARY KEY,"
            "    parent_chunk_id INTEGER NOT NULL,"
            "    parent_text     TEXT NOT NULL,"
            "    parent_token_count INTEGER,"
            "    FOREIGN KEY (child_chunk_id)  REFERENCES chunks(chunk_id),"
            "    FOREIGN KEY (parent_chunk_id) REFERENCES chunks(chunk_id)"
            ")"
        )
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

    # ------------------------------------------------------------------
    # Phase 7: RAG-03 contextual enrichment
    # ------------------------------------------------------------------

    def add_enriched_text_column(self) -> None:
        """Add enriched_text TEXT column to chunks table if it does not exist.

        Idempotent — safe to call on both new and existing databases.
        """
        try:
            self.conn.execute("ALTER TABLE chunks ADD COLUMN enriched_text TEXT")
            self.conn.commit()
        except Exception:
            pass  # Column already exists

    def upsert_chunk_enrichment(self, chunk_id: int, enriched_text: str) -> None:
        """Store LLM-generated enriched_text for a single chunk.

        Args:
            chunk_id: SQLite chunk_id INTEGER.
            enriched_text: 2-3 sentence context summary from enrich_chunk_context().
        """
        self.conn.execute(
            "UPDATE chunks SET enriched_text = ? WHERE chunk_id = ?",
            (enriched_text, chunk_id),
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Phase 7: RAG-04 parent-document retrieval
    # ------------------------------------------------------------------

    def insert_chunk_parents(self, doc_id: int, chunk_rows: list[dict]) -> None:
        """Insert identity-mapping rows into chunk_parents for a newly ingested document.

        v1: each chunk is its own parent (child_chunk_id == parent_chunk_id).
        chunk_rows must have keys: chunk_id (int), text (str), token_count (int).

        Args:
            doc_id: Unused in v1 but kept for future parent-building logic.
            chunk_rows: List of dicts from insert_chunks() augmented with chunk_id.
        """
        rows = [
            (
                int(r["chunk_id"]),
                int(r["chunk_id"]),
                r.get("text", ""),
                r.get("token_count", 0),
            )
            for r in chunk_rows
            if r.get("chunk_id") is not None
        ]
        if rows:
            self.conn.executemany(
                "INSERT OR IGNORE INTO chunk_parents "
                "(child_chunk_id, parent_chunk_id, parent_text, parent_token_count) "
                "VALUES (?, ?, ?, ?)",
                rows,
            )
            self.conn.commit()

    def get_parent_texts(self, chunk_ids: list) -> dict:
        """Fetch parent_text for each child_chunk_id from chunk_parents.

        Returns {str(chunk_id): parent_text}. Missing ids absent from dict.
        """
        if not chunk_ids:
            return {}
        normalised = []
        for cid in chunk_ids:
            try:
                normalised.append(int(cid))
            except (ValueError, TypeError):
                normalised.append(cid)
        placeholders = ",".join("?" * len(normalised))
        try:
            rows = self.conn.execute(
                f"SELECT child_chunk_id, parent_text FROM chunk_parents "
                f"WHERE child_chunk_id IN ({placeholders})",
                normalised,
            ).fetchall()
        except Exception:
            return {}
        if not rows:
            return {}
        if hasattr(rows[0], "keys"):
            return {str(r["child_chunk_id"]): r["parent_text"] for r in rows}
        return {str(r[0]): r[1] for r in rows}

    def get_chunks_with_metadata_for_embedding(
        self, batch_size: int = 8
    ) -> list[sqlite3.Row]:
        """Retrieve a batch of unembedded chunks with document metadata for embedding.

        JOINs chunks with documents to return filename, page_num, chunk_index, and
        token_count alongside chunk_id and chunk_text. The embedding pipeline uses
        these fields to populate ChromaDB metadata for citation at query time.

        Args:
            batch_size: Maximum number of chunks to return (default 8, conservative
                for LM Studio VRAM stability).

        Returns:
            List of sqlite3.Row objects with columns:
                chunk_id, chunk_text, doc_id, filename, page_num, chunk_index, token_count
            Returns [] when no unembedded chunks remain.
        """
        return self.conn.execute(
            """
            SELECT
                c.chunk_id,
                c.chunk_text,
                c.doc_id,
                d.filename,
                c.page_num,
                c.chunk_index,
                c.token_count
            FROM chunks c
            JOIN documents d ON c.doc_id = d.doc_id
            WHERE c.embedding_flag = 0
            LIMIT ?
            """,
            (batch_size,),
        ).fetchall()


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
CREATE TABLE IF NOT EXISTS metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunk_parents (
    child_chunk_id  INTEGER PRIMARY KEY,
    parent_chunk_id INTEGER NOT NULL,
    parent_text     TEXT NOT NULL,
    parent_token_count INTEGER,
    FOREIGN KEY (child_chunk_id)  REFERENCES chunks(chunk_id),
    FOREIGN KEY (parent_chunk_id) REFERENCES chunks(chunk_id)
);
"""
