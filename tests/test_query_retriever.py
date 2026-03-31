"""Tests for src/query/retriever.py — hybrid retrieval (QUERY-02, QUERY-03).

Test isolation:
  - ChromaDB: chromadb.EphemeralClient() — never PersistentClient
  - KuzuDB: tempfile.mkdtemp() for each test that needs a graph database
  - LM Studio: unittest.mock.MagicMock for openai.OpenAI client
"""
from __future__ import annotations

import sqlite3
import tempfile
import os
from unittest.mock import MagicMock

import chromadb
import kuzu
import pytest

from src.graph.citations import CitationStore
from src.graph.db_manager import create_graph_schema, upsert_entity, insert_relationships
from src.query.retriever import (
    deduplicate_chunks,
    graph_expand,
    hybrid_retrieve,
    vector_search,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_openai_mock(embedding: list[float]) -> MagicMock:
    """Return a MagicMock openai client that returns a fixed embedding vector."""
    mock_client = MagicMock()
    mock_embedding_obj = MagicMock()
    mock_embedding_obj.embedding = embedding
    mock_response = MagicMock()
    mock_response.data = [mock_embedding_obj]
    mock_client.embeddings.create.return_value = mock_response
    return mock_client


def _make_sqlite_db() -> sqlite3.Connection:
    """Create an in-memory SQLite database with documents, chunks, and chunk_citations tables."""
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            chunk_text TEXT,
            page_num INTEGER DEFAULT 1,
            embedding_flag INTEGER DEFAULT 0,
            FOREIGN KEY(doc_id) REFERENCES documents(doc_id)
        );
        CREATE TABLE IF NOT EXISTS chunk_citations (
            citation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_canonical_name TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            chunk_id INTEGER NOT NULL,
            FOREIGN KEY(chunk_id) REFERENCES chunks(chunk_id) ON DELETE CASCADE,
            UNIQUE(entity_canonical_name, entity_type, chunk_id)
        );
        CREATE INDEX IF NOT EXISTS idx_citations_entity ON chunk_citations(entity_canonical_name, entity_type);
        CREATE INDEX IF NOT EXISTS idx_citations_chunk ON chunk_citations(chunk_id);
    """)
    conn.commit()
    return conn


def _seed_sqlite(conn: sqlite3.Connection, filename: str, chunks: list[str]) -> list[int]:
    """Insert a document and its chunks. Returns list of chunk_ids."""
    cur = conn.execute("INSERT INTO documents (filename) VALUES (?)", (filename,))
    doc_id = cur.lastrowid
    chunk_ids = []
    for i, text in enumerate(chunks, start=1):
        cur = conn.execute(
            "INSERT INTO chunks (doc_id, chunk_text, page_num) VALUES (?, ?, ?)",
            (doc_id, text, i),
        )
        chunk_ids.append(cur.lastrowid)
    conn.commit()
    return chunk_ids


# ---------------------------------------------------------------------------
# Test 1: vector_search returns proper chunk dicts
# ---------------------------------------------------------------------------

def test_vector_search_returns_chunks() -> None:
    """vector_search() embeds query and returns list of chunk dicts from ChromaDB.

    Expected: returns list of dicts with keys chunk_id, text, filename, page_num,
    distance, source='vector'. Uses chromadb.EphemeralClient() with a
    pre-populated collection.
    """
    dim = 4
    embedding = [0.1, 0.2, 0.3, 0.4]
    mock_client = _make_openai_mock(embedding)

    chroma_client = chromadb.EphemeralClient()
    collection = chroma_client.get_or_create_collection(
        name="test_chunks",
        configuration={"hnsw": {"space": "cosine"}},
    )
    # Seed 3 chunks with unit-normalised embeddings
    collection.upsert(
        ids=["1", "2", "3"],
        embeddings=[
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
        ],
        documents=["EV battery text", "LiDAR sensor text", "OEM strategy text"],
        metadatas=[
            {"filename": "report.pdf", "page_num": 1},
            {"filename": "report.pdf", "page_num": 2},
            {"filename": "report.pdf", "page_num": 3},
        ],
    )

    results = vector_search(
        "EV battery technology",
        mock_client,
        chroma_client,
        collection_name="test_chunks",
        embed_model="nomic-embed-text-v1.5",
        n_results=3,
    )

    assert isinstance(results, list), "Should return a list"
    assert len(results) <= 3, "Should not exceed n_results"
    assert len(results) > 0, "Should return at least one chunk from non-empty collection"

    for chunk in results:
        assert "chunk_id" in chunk, "Must have chunk_id"
        assert "text" in chunk, "Must have text"
        assert "filename" in chunk, "Must have filename"
        assert "page_num" in chunk, "Must have page_num"
        assert "distance" in chunk, "Must have distance"
        assert chunk["source"] == "vector", "source must be 'vector'"


# ---------------------------------------------------------------------------
# Test 2: graph expansion finds 1-hop neighbors
# ---------------------------------------------------------------------------

def test_graph_expansion_finds_neighbors() -> None:
    """graph_expand() finds 1-hop neighbors in KuzuDB and fetches their chunks.

    Expected: given vector_chunks citing a known OEM entity, graph_expand()
    returns additional chunk dicts from neighbor Technology entities.
    Uses tempfile.mkdtemp() for KuzuDB.
    """
    kuzu_dir = tempfile.mkdtemp()
    kuzu_db_path = os.path.join(kuzu_dir, "test.db")
    kuzu_db = kuzu.Database(kuzu_db_path)

    # Build graph schema and seed entities + relationship
    create_graph_schema(kuzu_db)
    upsert_entity(kuzu_db, {"name": "Toyota", "type": "OEM", "confidence": 0.9})
    upsert_entity(kuzu_db, {"name": "LiDAR", "type": "Technology", "confidence": 0.85})
    entity_map = {
        "Toyota": ("OEM", "Toyota"),
        "LiDAR": ("Technology", "LiDAR"),
    }
    insert_relationships(
        kuzu_db,
        [{"source_name": "Toyota", "target_name": "LiDAR", "type": "USES"}],
        entity_map,
    )

    # Set up SQLite: Toyota chunk (chunk_id=1) and LiDAR chunk (chunk_id=2)
    conn = _make_sqlite_db()
    toyota_chunk_ids = _seed_sqlite(conn, "report.pdf", ["Toyota EV strategy"])   # chunk_id=1
    lidar_chunk_ids = _seed_sqlite(conn, "report.pdf", ["LiDAR sensor details"])  # chunk_id=2

    # Link Toyota (chunk 1) and LiDAR (chunk 2) to their respective entities
    conn.execute(
        "INSERT INTO chunk_citations (entity_canonical_name, entity_type, chunk_id) VALUES (?, ?, ?)",
        ("Toyota", "OEM", toyota_chunk_ids[0]),
    )
    conn.execute(
        "INSERT INTO chunk_citations (entity_canonical_name, entity_type, chunk_id) VALUES (?, ?, ?)",
        ("LiDAR", "Technology", lidar_chunk_ids[0]),
    )
    conn.commit()

    citation_store = CitationStore(conn)

    # vector_chunks contain the Toyota chunk to seed graph expansion
    vector_chunks = [
        {
            "chunk_id": str(toyota_chunk_ids[0]),
            "text": "Toyota EV strategy",
            "filename": "report.pdf",
            "page_num": 1,
            "source": "vector",
            "distance": 0.1,
        }
    ]

    graph_chunks = graph_expand(vector_chunks, citation_store, kuzu_db, conn)

    assert isinstance(graph_chunks, list), "graph_expand must return a list"
    assert len(graph_chunks) > 0, "Should find at least one neighbor chunk (LiDAR)"

    sources = {c["source"] for c in graph_chunks}
    assert "graph" in sources, "Graph chunks must have source='graph'"

    # The LiDAR chunk text should appear in graph expansion results
    texts = [c["text"] for c in graph_chunks]
    assert any("LiDAR" in t for t in texts), "Should include LiDAR chunk text"


# ---------------------------------------------------------------------------
# Test 3: deduplication preserves order and removes duplicates
# ---------------------------------------------------------------------------

def test_dedup_merged_chunks() -> None:
    """deduplicate_chunks() removes duplicates by chunk_id, preserving order.

    Expected: a list with one duplicate chunk_id returns a list with that chunk_id
    appearing only once; total length is reduced by the duplicate count.
    """
    chunks = [
        {"chunk_id": "1", "text": "first", "source": "vector", "distance": 0.1},
        {"chunk_id": "2", "text": "second", "source": "vector", "distance": 0.2},
        {"chunk_id": "1", "text": "first-dup", "source": "graph", "distance": 1.0},
    ]

    result = deduplicate_chunks(chunks)

    assert len(result) == 2, "Should deduplicate to 2 unique chunk_ids"
    ids = [str(c["chunk_id"]) for c in result]
    assert ids.count("1") == 1, "chunk_id '1' should appear exactly once"
    assert ids.count("2") == 1, "chunk_id '2' should appear exactly once"

    # Verify first occurrence (vector) is preserved over duplicate (graph)
    chunk_1 = next(c for c in result if str(c["chunk_id"]) == "1")
    assert chunk_1["source"] == "vector", "First occurrence (vector) should be preserved"

    # Verify str/int normalisation: 42 and "42" should dedup
    mixed = [
        {"chunk_id": 42, "text": "int-id", "source": "graph", "distance": 1.0},
        {"chunk_id": "42", "text": "str-id", "source": "vector", "distance": 0.5},
    ]
    deduped = deduplicate_chunks(mixed)
    assert len(deduped) == 1, "int 42 and str '42' should be treated as the same chunk_id"


# ---------------------------------------------------------------------------
# Test 4: hybrid_retrieve combines both sources
# ---------------------------------------------------------------------------

def test_hybrid_retrieve_combines_sources() -> None:
    """hybrid_retrieve() returns union of vector and graph chunks, deduped.

    Expected: result includes chunks with source='vector' and source='graph';
    no chunk_id appears more than once; result is a non-empty list.
    """
    kuzu_dir = tempfile.mkdtemp()
    kuzu_db_path = os.path.join(kuzu_dir, "test.db")
    kuzu_db = kuzu.Database(kuzu_db_path)

    create_graph_schema(kuzu_db)
    upsert_entity(kuzu_db, {"name": "BMW", "type": "OEM", "confidence": 0.9})
    upsert_entity(kuzu_db, {"name": "Battery", "type": "Technology", "confidence": 0.85})
    entity_map = {
        "BMW": ("OEM", "BMW"),
        "Battery": ("Technology", "Battery"),
    }
    insert_relationships(
        kuzu_db,
        [{"source_name": "BMW", "target_name": "Battery", "type": "USES"}],
        entity_map,
    )

    # SQLite with two chunks
    conn = _make_sqlite_db()
    bmw_chunk_ids = _seed_sqlite(conn, "bmw_report.pdf", ["BMW EV roadmap"])       # chunk 1
    bat_chunk_ids = _seed_sqlite(conn, "bmw_report.pdf", ["Battery cell details"]) # chunk 2

    conn.execute(
        "INSERT INTO chunk_citations (entity_canonical_name, entity_type, chunk_id) VALUES (?, ?, ?)",
        ("BMW", "OEM", bmw_chunk_ids[0]),
    )
    conn.execute(
        "INSERT INTO chunk_citations (entity_canonical_name, entity_type, chunk_id) VALUES (?, ?, ?)",
        ("Battery", "Technology", bat_chunk_ids[0]),
    )
    conn.commit()

    citation_store = CitationStore(conn)

    # ChromaDB: seed the BMW chunk so vector_search returns it
    chroma_client = chromadb.EphemeralClient()
    collection = chroma_client.get_or_create_collection(
        name="hybrid_chunks",
        configuration={"hnsw": {"space": "cosine"}},
    )
    fixed_embedding = [0.1, 0.9, 0.0, 0.0]
    collection.upsert(
        ids=[str(bmw_chunk_ids[0])],
        embeddings=[[1.0, 0.0, 0.0, 0.0]],
        documents=["BMW EV roadmap"],
        metadatas=[{"filename": "bmw_report.pdf", "page_num": 1}],
    )

    # Mock openai client to return an embedding close to the BMW chunk vector
    mock_client = _make_openai_mock([1.0, 0.0, 0.0, 0.0])

    results = hybrid_retrieve(
        query_text="BMW electric vehicle strategy",
        openai_client=mock_client,
        chroma_client=chroma_client,
        collection_name="hybrid_chunks",
        citation_store=citation_store,
        kuzu_db=kuzu_db,
        sqlite_conn=conn,
        embed_model="nomic-embed-text-v1.5",
        n_results=5,
    )

    assert isinstance(results, list), "hybrid_retrieve must return a list"
    assert len(results) > 0, "Result should be non-empty"

    sources = {c["source"] for c in results}
    assert "vector" in sources, "Result must contain at least one vector chunk"
    assert "graph" in sources, "Result must contain at least one graph chunk"

    # No duplicate chunk_ids
    chunk_ids = [str(c["chunk_id"]) for c in results]
    assert len(chunk_ids) == len(set(chunk_ids)), "No duplicate chunk_ids in result"
