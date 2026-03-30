"""Tests for Phase 2: Embedding & Vector Search.

Wave 0 stubs — all xfail until implementation plans (02, 03, 04) fill them in.

Unit tests (no LM Studio required):
  - test_embed_chunks_calls_api
  - test_embed_chunks_server_unavailable
  - test_embed_chunks_empty_input
  - test_vector_store_upsert
  - test_vector_store_query_returns_n_results
  - test_vector_store_query_small_collection
  - test_vector_store_metadata_fields
  - test_vector_store_metadata_retrievable
  - test_embed_all_chunks_loop
  - test_embed_loop_incremental
  - test_query_latency_under_50ms

Integration test (requires LM Studio running, mark with @pytest.mark.integration):
  - test_real_768_dim_vectors
"""
from __future__ import annotations

import pytest

from src.embed.embedder import embed_chunks, embed_query
from src.embed.vector_store import VectorStore


# ---------------------------------------------------------------------------
# EMBED-01: embed_chunks() LM Studio API calls
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_embed_chunks_calls_api() -> None:
    """embed_chunks() calls client.embeddings.create() once per batch of 8."""
    from unittest.mock import MagicMock

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.1] * 768) for _ in range(2)]
    mock_client.embeddings.create.return_value = mock_response

    chunks = [{"chunk_text": "text one"}, {"chunk_text": "text two"}]
    result = embed_chunks(chunks, client=mock_client, model="nomic-embed-text-v1.5")

    mock_client.embeddings.create.assert_called_once()
    assert len(result) == 2
    assert len(result[0]) == 768


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_embed_chunks_server_unavailable() -> None:
    """embed_chunks() raises a clear RuntimeError when LM Studio is unreachable."""
    from unittest.mock import MagicMock
    import httpx

    mock_client = MagicMock()
    mock_client.embeddings.create.side_effect = httpx.ConnectError("Connection refused")

    chunks = [{"chunk_text": "hello"}]
    with pytest.raises((RuntimeError, Exception)):
        embed_chunks(chunks, client=mock_client, model="nomic-embed-text-v1.5")


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_embed_chunks_empty_input() -> None:
    """embed_chunks() returns [] immediately for an empty input list."""
    from unittest.mock import MagicMock

    mock_client = MagicMock()
    result = embed_chunks([], client=mock_client, model="nomic-embed-text-v1.5")

    mock_client.embeddings.create.assert_not_called()
    assert result == []


# ---------------------------------------------------------------------------
# EMBED-02: VectorStore upsert and query
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_vector_store_upsert() -> None:
    """VectorStore.upsert() stores embeddings without raising an exception."""
    import chromadb

    client = chromadb.EphemeralClient()
    vs = VectorStore.__new__(VectorStore)
    vs._collection = client.get_or_create_collection(
        name="test", configuration={"hnsw": {"space": "cosine"}}
    )

    vs.upsert(
        chunk_ids=[1, 2],
        embeddings=[[0.1] * 768, [0.2] * 768],
        documents=["text one", "text two"],
        metadatas=[
            {"doc_id": 1, "filename": "a.pdf", "page_num": 1, "chunk_index": 0, "token_count": 10},
            {"doc_id": 1, "filename": "a.pdf", "page_num": 1, "chunk_index": 1, "token_count": 12},
        ],
    )
    assert vs.count() == 2


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_vector_store_query_returns_n_results() -> None:
    """VectorStore.query() returns exactly n_results when collection has enough items."""
    import chromadb

    client = chromadb.EphemeralClient()
    vs = VectorStore.__new__(VectorStore)
    vs._collection = client.get_or_create_collection(
        name="test", configuration={"hnsw": {"space": "cosine"}}
    )
    # Insert 5 embeddings
    vs.upsert(
        chunk_ids=list(range(1, 6)),
        embeddings=[[float(i) / 10] * 768 for i in range(1, 6)],
        documents=[f"doc {i}" for i in range(1, 6)],
        metadatas=[
            {"doc_id": 1, "filename": "a.pdf", "page_num": i, "chunk_index": i, "token_count": 10}
            for i in range(1, 6)
        ],
    )
    results = vs.query(query_embedding=[0.15] * 768, n_results=3)
    assert len(results) == 3


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_vector_store_query_small_collection() -> None:
    """VectorStore.query() does not raise when n_results > collection.count()."""
    import chromadb

    client = chromadb.EphemeralClient()
    vs = VectorStore.__new__(VectorStore)
    vs._collection = client.get_or_create_collection(
        name="test", configuration={"hnsw": {"space": "cosine"}}
    )
    vs.upsert(
        chunk_ids=[1],
        embeddings=[[0.1] * 768],
        documents=["only one"],
        metadatas=[{"doc_id": 1, "filename": "a.pdf", "page_num": 1, "chunk_index": 0, "token_count": 5}],
    )
    # Asking for 10 when only 1 exists — must not raise NotEnoughElementsException
    results = vs.query(query_embedding=[0.1] * 768, n_results=10)
    assert len(results) == 1


# ---------------------------------------------------------------------------
# EMBED-03: metadata stored and retrievable
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_vector_store_metadata_fields() -> None:
    """upsert() stores all 5 required metadata fields: doc_id, filename, page_num, chunk_index, token_count."""
    import chromadb

    client = chromadb.EphemeralClient()
    vs = VectorStore.__new__(VectorStore)
    vs._collection = client.get_or_create_collection(
        name="test", configuration={"hnsw": {"space": "cosine"}}
    )
    vs.upsert(
        chunk_ids=[42],
        embeddings=[[0.5] * 768],
        documents=["sample text"],
        metadatas=[
            {"doc_id": 7, "filename": "report.pdf", "page_num": 3, "chunk_index": 2, "token_count": 400}
        ],
    )
    # Retrieve by ID and verify all fields present
    result = vs._collection.get(ids=["42"], include=["metadatas"])
    meta = result["metadatas"][0]
    assert meta["doc_id"] == 7
    assert meta["filename"] == "report.pdf"
    assert meta["page_num"] == 3
    assert meta["chunk_index"] == 2
    assert meta["token_count"] == 400


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_vector_store_metadata_retrievable() -> None:
    """query() result dicts contain 'metadata' key with filename and page_num for citation."""
    import chromadb

    client = chromadb.EphemeralClient()
    vs = VectorStore.__new__(VectorStore)
    vs._collection = client.get_or_create_collection(
        name="test", configuration={"hnsw": {"space": "cosine"}}
    )
    vs.upsert(
        chunk_ids=[1],
        embeddings=[[0.1] * 768],
        documents=["content"],
        metadatas=[{"doc_id": 1, "filename": "slides.pptx", "page_num": 5, "chunk_index": 0, "token_count": 200}],
    )
    results = vs.query(query_embedding=[0.1] * 768, n_results=1)
    assert len(results) == 1
    assert "metadata" in results[0]
    assert results[0]["metadata"]["filename"] == "slides.pptx"
    assert results[0]["metadata"]["page_num"] == 5


# ---------------------------------------------------------------------------
# EMBED-01/02/03: full pipeline loop (unit — mocked embedder + EphemeralClient)
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_embed_all_chunks_loop() -> None:
    """embed_all_chunks() reads chunks from SQLite, embeds, stores in ChromaDB, marks flag=1."""
    import sqlite3
    import chromadb
    from unittest.mock import MagicMock, patch

    # Build an in-memory SQLite DB with one pending chunk
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE documents (
            doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            file_size_bytes INTEGER,
            file_hash TEXT NOT NULL UNIQUE,
            doc_type TEXT NOT NULL,
            total_pages INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            indexed_at TIMESTAMP
        );
        CREATE TABLE chunks (
            chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            page_num INTEGER,
            chunk_index INTEGER,
            chunk_text TEXT NOT NULL,
            token_count INTEGER,
            embedding_flag INTEGER DEFAULT 0
        );
        INSERT INTO documents (filename, file_hash, doc_type) VALUES ('test.pdf', 'abc123', 'pdf');
        INSERT INTO chunks (doc_id, page_num, chunk_index, chunk_text, token_count, embedding_flag)
        VALUES (1, 1, 0, 'sample automotive text', 42, 0);
    """)
    conn.commit()

    mock_embed = MagicMock(return_value=[[0.1] * 768])

    with patch("src.embed.pipeline.embed_chunks", mock_embed):
        from src.embed.pipeline import embed_all_chunks
        embed_all_chunks(conn=conn, chroma_client=chromadb.EphemeralClient(), model="nomic-embed-text-v1.5")

    flag = conn.execute("SELECT embedding_flag FROM chunks WHERE chunk_id = 1").fetchone()[0]
    assert flag == 1, f"Expected embedding_flag=1, got {flag}"
    conn.close()


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_embed_loop_incremental() -> None:
    """embed_all_chunks() skips chunks with embedding_flag=1 on re-run."""
    import sqlite3
    from unittest.mock import MagicMock, patch
    import chromadb

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE documents (
            doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            file_size_bytes INTEGER,
            file_hash TEXT NOT NULL UNIQUE,
            doc_type TEXT NOT NULL,
            total_pages INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            indexed_at TIMESTAMP
        );
        CREATE TABLE chunks (
            chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            page_num INTEGER,
            chunk_index INTEGER,
            chunk_text TEXT NOT NULL,
            token_count INTEGER,
            embedding_flag INTEGER DEFAULT 0
        );
        INSERT INTO documents (filename, file_hash, doc_type) VALUES ('test.pdf', 'abc123', 'pdf');
        INSERT INTO chunks (doc_id, page_num, chunk_index, chunk_text, token_count, embedding_flag)
        VALUES (1, 1, 0, 'already embedded', 42, 1);
    """)
    conn.commit()

    mock_embed = MagicMock(return_value=[[0.1] * 768])

    with patch("src.embed.pipeline.embed_chunks", mock_embed):
        from src.embed.pipeline import embed_all_chunks
        embed_all_chunks(conn=conn, chroma_client=chromadb.EphemeralClient(), model="nomic-embed-text-v1.5")

    # embed_chunks must not have been called — no pending chunks
    mock_embed.assert_not_called()
    conn.close()


# ---------------------------------------------------------------------------
# EMBED-02: latency guard
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_query_latency_under_50ms() -> None:
    """VectorStore.query() returns results in under 50ms for a 100-item collection."""
    import time
    import chromadb

    client = chromadb.EphemeralClient()
    vs = VectorStore.__new__(VectorStore)
    vs._collection = client.get_or_create_collection(
        name="perf_test", configuration={"hnsw": {"space": "cosine"}}
    )
    # Insert 100 items
    import random
    random.seed(42)
    vs.upsert(
        chunk_ids=list(range(1, 101)),
        embeddings=[[random.random() for _ in range(768)] for _ in range(100)],
        documents=[f"chunk {i}" for i in range(100)],
        metadatas=[
            {"doc_id": 1, "filename": "report.pdf", "page_num": i % 20 + 1,
             "chunk_index": i, "token_count": 200}
            for i in range(100)
        ],
    )
    query_vec = [random.random() for _ in range(768)]
    start = time.perf_counter()
    results = vs.query(query_embedding=query_vec, n_results=10)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert len(results) == 10
    assert elapsed_ms < 50, f"Query took {elapsed_ms:.1f}ms — expected < 50ms"


# ---------------------------------------------------------------------------
# EMBED-01: integration test (real LM Studio required)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.xfail(strict=False, reason="requires LM Studio running with nomic-embed-text-v1.5")
def test_real_768_dim_vectors() -> None:
    """embed_chunks() produces real 768-dimensional vectors via LM Studio."""
    from openai import OpenAI

    client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
    chunks = [{"chunk_text": "automotive consulting best practices for OEM supplier negotiation"}]
    result = embed_chunks(chunks, client=client, model="nomic-embed-text-v1.5")

    assert len(result) == 1, "Expected one vector for one chunk"
    assert len(result[0]) == 768, f"Expected 768 dims, got {len(result[0])}"
    assert all(isinstance(v, float) for v in result[0]), "All values must be float"
