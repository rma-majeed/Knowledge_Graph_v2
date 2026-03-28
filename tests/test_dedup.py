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
