"""End-to-end ingestion pipeline tests.

Stubs: marked xfail until src/ingest/pipeline.py is implemented (Plan 06).
"""
import pytest
import sqlite3
from pathlib import Path


def test_ingest_pdf_complete(sample_pdf_path, tmp_db_path):
    """Full PDF ingest: extraction -> chunking -> storage produces chunks in DB."""
    from src.ingest.pipeline import ingest_document
    ingest_document(sample_pdf_path, db_path=tmp_db_path)
    conn = sqlite3.connect(str(tmp_db_path))
    count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    conn.close()
    assert doc_count == 1
    assert count > 0


def test_ingest_pptx_complete(sample_pptx_path, tmp_db_path):
    """Full PPTX ingest: extraction -> chunking -> storage produces chunks in DB."""
    from src.ingest.pipeline import ingest_document
    ingest_document(sample_pptx_path, db_path=tmp_db_path)
    conn = sqlite3.connect(str(tmp_db_path))
    count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    conn.close()
    assert count > 0


def test_ingest_deduplication(sample_pdf_path, tmp_db_path):
    """Ingesting the same document twice does not create duplicate entries."""
    from src.ingest.pipeline import ingest_document
    ingest_document(sample_pdf_path, db_path=tmp_db_path)
    ingest_document(sample_pdf_path, db_path=tmp_db_path)  # Second call
    conn = sqlite3.connect(str(tmp_db_path))
    doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    conn.close()
    assert doc_count == 1  # Not 2


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
