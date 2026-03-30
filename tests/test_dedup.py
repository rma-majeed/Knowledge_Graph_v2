"""Tests for SHA-256 file deduplication.

Stubs: marked xfail until src/ingest/store.py is implemented (Plan 04).
"""
import pytest
import tempfile
from pathlib import Path


def test_file_hash_sha256(sample_pdf_path):
    """compute_file_hash returns consistent SHA-256 hex string."""
    from src.ingest.store import compute_file_hash
    h1 = compute_file_hash(sample_pdf_path)
    h2 = compute_file_hash(sample_pdf_path)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex = 64 chars
    assert all(c in "0123456789abcdef" for c in h1)


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


def test_different_files_have_different_hashes(sample_pdf_path, sample_pptx_path):
    """Different files produce different hashes."""
    from src.ingest.store import compute_file_hash
    h_pdf = compute_file_hash(sample_pdf_path)
    h_pptx = compute_file_hash(sample_pptx_path)
    assert h_pdf != h_pptx


# ---------------------------------------------------------------------------
# Plan 02-04: get_chunks_with_metadata_for_embedding() — Task 1
# ---------------------------------------------------------------------------


def test_get_chunks_with_metadata_for_embedding_returns_unembedded(tmp_db_conn):
    """get_chunks_with_metadata_for_embedding() returns only embedding_flag=0 chunks with metadata."""
    import sqlite3
    from src.ingest.store import ChunkStore

    conn = tmp_db_conn
    store = ChunkStore(conn)
    store.init_schema()

    doc_id = store.insert_document(
        filename="report.pdf",
        file_size_bytes=1000,
        file_hash="deadbeef01",
        doc_type="pdf",
        total_pages=3,
    )
    # Insert two chunks: one pending, one already embedded
    store.insert_chunks(doc_id, [
        {"page_num": 1, "chunk_index": 0, "text": "pending text", "token_count": 10},
        {"page_num": 1, "chunk_index": 1, "text": "embedded text", "token_count": 20},
    ])
    # Mark second chunk embedded
    chunk_ids = [row["chunk_id"] for row in conn.execute("SELECT chunk_id FROM chunks").fetchall()]
    store.mark_chunks_embedded([chunk_ids[1]])

    rows = store.get_chunks_with_metadata_for_embedding(batch_size=8)
    assert len(rows) == 1, f"Expected 1 pending chunk, got {len(rows)}"
    row = rows[0]
    assert row["chunk_text"] == "pending text"
    assert row["filename"] == "report.pdf"
    assert row["page_num"] == 1
    assert row["chunk_index"] == 0
    assert row["token_count"] == 10
    assert "doc_id" in row.keys()


def test_get_chunks_with_metadata_for_embedding_empty_when_all_embedded(tmp_db_conn):
    """get_chunks_with_metadata_for_embedding() returns [] when all chunks are embedded."""
    from src.ingest.store import ChunkStore

    conn = tmp_db_conn
    store = ChunkStore(conn)
    store.init_schema()

    doc_id = store.insert_document(
        filename="slides.pptx",
        file_size_bytes=500,
        file_hash="deadbeef02",
        doc_type="pptx",
        total_pages=5,
    )
    store.insert_chunks(doc_id, [
        {"page_num": 1, "chunk_index": 0, "text": "already done", "token_count": 5},
    ])
    chunk_ids = [row["chunk_id"] for row in conn.execute("SELECT chunk_id FROM chunks").fetchall()]
    store.mark_chunks_embedded(chunk_ids)

    rows = store.get_chunks_with_metadata_for_embedding(batch_size=8)
    assert rows == [], f"Expected [], got {rows}"


def test_get_chunks_with_metadata_for_embedding_respects_batch_size(tmp_db_conn):
    """get_chunks_with_metadata_for_embedding() returns at most batch_size rows."""
    from src.ingest.store import ChunkStore

    conn = tmp_db_conn
    store = ChunkStore(conn)
    store.init_schema()

    doc_id = store.insert_document(
        filename="long.pdf",
        file_size_bytes=2000,
        file_hash="deadbeef03",
        doc_type="pdf",
        total_pages=10,
    )
    store.insert_chunks(doc_id, [
        {"page_num": i, "chunk_index": i, "text": f"chunk {i}", "token_count": 50}
        for i in range(10)
    ])

    rows = store.get_chunks_with_metadata_for_embedding(batch_size=3)
    assert len(rows) == 3, f"Expected 3 rows, got {len(rows)}"
