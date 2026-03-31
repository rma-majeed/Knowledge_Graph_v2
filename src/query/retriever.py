"""Hybrid retriever stub — implemented in plan 04-02.

Public API (all raise NotImplementedError until plan 04-02):
    vector_search(query_text, openai_client, chroma_path, embed_model, n_results) -> list[dict]
    graph_expand(vector_chunks, sqlite_conn, kuzu_db, n_per_entity) -> list[dict]
    deduplicate_chunks(chunks) -> list[dict]
    hybrid_retrieve(query_text, openai_client, sqlite_conn, kuzu_db, chroma_path, embed_model, n_results) -> list[dict]
"""
from __future__ import annotations


def vector_search(query_text, openai_client, chroma_path="data/chroma_db",
                  embed_model="nomic-embed-text-v1.5", n_results=10):
    """Embed query_text and retrieve top-N chunks from ChromaDB."""
    raise NotImplementedError


def graph_expand(vector_chunks, sqlite_conn, kuzu_db, n_per_entity=5):
    """Expand retrieval via 1-hop KuzuDB graph traversal seeded from vector_chunks."""
    raise NotImplementedError


def deduplicate_chunks(chunks):
    """Deduplicate chunk list by chunk_id, preserving order."""
    raise NotImplementedError


def hybrid_retrieve(query_text, openai_client, sqlite_conn, kuzu_db,
                    chroma_path="data/chroma_db", embed_model="nomic-embed-text-v1.5",
                    n_results=10):
    """Run vector_search + graph_expand + deduplicate_chunks in sequence."""
    raise NotImplementedError
