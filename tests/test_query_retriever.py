"""Tests for src/query/retriever.py — hybrid retrieval (QUERY-02, QUERY-03).

All tests are xfail stubs. They become passing once plan 04-02 implements
vector_search(), graph_expand(), deduplicate_chunks(), and hybrid_retrieve().

Test isolation:
  - ChromaDB: chromadb.EphemeralClient() — never PersistentClient
  - KuzuDB: tempfile.mkdtemp() for each test that needs a graph database
  - LM Studio: unittest.mock.MagicMock for openai.OpenAI client
"""
from __future__ import annotations

import pytest


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_vector_search_returns_chunks() -> None:
    """vector_search() embeds query and returns list of chunk dicts from ChromaDB.

    Expected: returns list of dicts with keys chunk_id, text, metadata, distance.
    Uses chromadb.EphemeralClient() with a pre-populated collection.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_graph_expansion_finds_neighbors() -> None:
    """graph_expand() finds 1-hop neighbors in KuzuDB and fetches their chunks.

    Expected: given vector_chunks citing a known entity, graph_expand() returns
    additional chunk dicts from neighbor entities. Uses tempfile.mkdtemp() KuzuDB.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_dedup_merged_chunks() -> None:
    """deduplicate_chunks() removes duplicates by chunk_id, preserving order.

    Expected: a list with one duplicate chunk_id returns a list with that chunk_id
    appearing only once; total length is reduced by the duplicate count.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_hybrid_retrieve_combines_sources() -> None:
    """hybrid_retrieve() returns union of vector and graph chunks, deduped.

    Expected: result includes chunks with source='vector' and source='graph';
    no chunk_id appears more than once; result is a non-empty list.
    """
    raise NotImplementedError
