"""Tests for Phase 3: Entity-Chunk Citations (GRAPH-04).

Wave 0 stubs — all xfail until plan 03-04 fills them in.

Unit tests (tmp_db_conn SQLite fixture):
  - test_init_schema_creates_table
  - test_insert_chunk_citation
  - test_insert_duplicate_citation_ignored
  - test_get_chunks_for_entity
  - test_get_chunks_for_entity_empty
"""
from __future__ import annotations

import sqlite3
import pytest


# ---------------------------------------------------------------------------
# GRAPH-04: CitationStore bridge table
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_init_schema_creates_table(tmp_db_conn) -> None:
    """CitationStore.init_schema() creates the chunk_citations table."""
    from src.graph.citations import CitationStore

    # First need the chunks and documents tables for FK constraint
    tmp_db_conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            file_hash TEXT NOT NULL UNIQUE,
            doc_type TEXT NOT NULL,
            total_pages INTEGER
        );
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            page_num INTEGER,
            chunk_index INTEGER,
            chunk_text TEXT NOT NULL,
            token_count INTEGER,
            embedding_flag INTEGER DEFAULT 0
        );
    """)
    store = CitationStore(tmp_db_conn)
    store.init_schema()

    tables = tmp_db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='chunk_citations'"
    ).fetchone()
    assert tables is not None, "chunk_citations table was not created"


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_insert_chunk_citation(tmp_db_conn) -> None:
    """CitationStore.insert_citations() inserts entity-chunk mapping rows."""
    from src.graph.citations import CitationStore

    tmp_db_conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            file_hash TEXT NOT NULL UNIQUE,
            doc_type TEXT NOT NULL,
            total_pages INTEGER
        );
        INSERT INTO documents (filename, file_hash, doc_type, total_pages)
            VALUES ('report.pdf', 'abc123', 'pdf', 5);
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            page_num INTEGER,
            chunk_index INTEGER,
            chunk_text TEXT NOT NULL,
            token_count INTEGER,
            embedding_flag INTEGER DEFAULT 0
        );
        INSERT INTO chunks (doc_id, page_num, chunk_index, chunk_text, token_count)
            VALUES (1, 1, 0, 'Toyota announced EV plans.', 10);
    """)

    store = CitationStore(tmp_db_conn)
    store.init_schema()
    store.insert_citations([
        {"entity_canonical_name": "Toyota", "entity_type": "OEM", "chunk_id": 1}
    ])

    row = tmp_db_conn.execute(
        "SELECT * FROM chunk_citations WHERE entity_canonical_name = 'Toyota'"
    ).fetchone()
    assert row is not None


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_insert_duplicate_citation_ignored(tmp_db_conn) -> None:
    """CitationStore.insert_citations() uses INSERT OR IGNORE — no duplicate error."""
    from src.graph.citations import CitationStore

    tmp_db_conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            file_hash TEXT NOT NULL UNIQUE,
            doc_type TEXT NOT NULL,
            total_pages INTEGER
        );
        INSERT INTO documents (filename, file_hash, doc_type, total_pages)
            VALUES ('report.pdf', 'abc123', 'pdf', 5);
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            page_num INTEGER,
            chunk_index INTEGER,
            chunk_text TEXT NOT NULL,
            token_count INTEGER,
            embedding_flag INTEGER DEFAULT 0
        );
        INSERT INTO chunks (doc_id, page_num, chunk_index, chunk_text, token_count)
            VALUES (1, 1, 0, 'Toyota EV.', 5);
    """)

    store = CitationStore(tmp_db_conn)
    store.init_schema()
    citation = {"entity_canonical_name": "Toyota", "entity_type": "OEM", "chunk_id": 1}
    store.insert_citations([citation])
    store.insert_citations([citation])  # Second insert — must not raise

    count = tmp_db_conn.execute(
        "SELECT COUNT(*) FROM chunk_citations WHERE entity_canonical_name = 'Toyota'"
    ).fetchone()[0]
    assert count == 1


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_get_chunks_for_entity(tmp_db_conn) -> None:
    """CitationStore.get_chunks_for_entity() returns list of chunk dicts with doc metadata."""
    from src.graph.citations import CitationStore

    tmp_db_conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            file_hash TEXT NOT NULL UNIQUE,
            doc_type TEXT NOT NULL,
            total_pages INTEGER
        );
        INSERT INTO documents (filename, file_hash, doc_type, total_pages)
            VALUES ('report.pdf', 'abc123', 'pdf', 5);
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            page_num INTEGER,
            chunk_index INTEGER,
            chunk_text TEXT NOT NULL,
            token_count INTEGER,
            embedding_flag INTEGER DEFAULT 0
        );
        INSERT INTO chunks (doc_id, page_num, chunk_index, chunk_text, token_count)
            VALUES (1, 2, 0, 'Toyota announced new battery tech.', 8);
    """)

    store = CitationStore(tmp_db_conn)
    store.init_schema()
    store.insert_citations([
        {"entity_canonical_name": "Toyota", "entity_type": "OEM", "chunk_id": 1}
    ])

    results = store.get_chunks_for_entity("Toyota", "OEM")

    assert len(results) == 1
    assert results[0]["chunk_id"] == 1
    assert results[0]["filename"] == "report.pdf"
    assert results[0]["page_num"] == 2


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_get_chunks_for_entity_empty(tmp_db_conn) -> None:
    """CitationStore.get_chunks_for_entity() returns empty list for unknown entity."""
    from src.graph.citations import CitationStore

    tmp_db_conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            file_hash TEXT NOT NULL UNIQUE,
            doc_type TEXT NOT NULL,
            total_pages INTEGER
        );
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            page_num INTEGER,
            chunk_index INTEGER,
            chunk_text TEXT NOT NULL,
            token_count INTEGER,
            embedding_flag INTEGER DEFAULT 0
        );
    """)

    store = CitationStore(tmp_db_conn)
    store.init_schema()

    results = store.get_chunks_for_entity("NonExistentEntity", "OEM")
    assert results == []
