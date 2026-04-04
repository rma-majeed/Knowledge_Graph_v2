"""Individual search tools — Phase 2 (not yet implemented).

These tools will expose:
  - vector_search(query, top_k)    → ChromaDB semantic search
  - bm25_search(query, top_k)      → SQLite BM25 keyword search
  - graph_search(entity, hops)     → KuzuDB graph traversal

Placeholder until Phase 2 implementation.
"""


def vector_search(query: str, top_k: int = 10) -> dict:
    """Search the vector store for semantically similar chunks.

    Args:
        query: The search query string.
        top_k: Number of top results to return.

    Returns:
        A dict with status and results list.
    """
    return {
        "status": "not_implemented",
        "message": "vector_search is a Phase 2 feature — use pipeline_rag_agent instead.",
        "results": [],
    }


def bm25_search(query: str, top_k: int = 10) -> dict:
    """Search the document corpus using BM25 keyword matching.

    Args:
        query: The keyword search query.
        top_k: Number of top results to return.

    Returns:
        A dict with status and results list.
    """
    return {
        "status": "not_implemented",
        "message": "bm25_search is a Phase 2 feature — use pipeline_rag_agent instead.",
        "results": [],
    }


def graph_search(entity: str, hops: int = 2) -> dict:
    """Traverse the knowledge graph for entities related to the given entity.

    Args:
        entity: The entity name to search for (e.g. 'Toyota', 'BOSCH').
        hops: Number of graph hops to traverse from the entity.

    Returns:
        A dict with status and nodes/edges found.
    """
    return {
        "status": "not_implemented",
        "message": "graph_search is a Phase 2 feature — use pipeline_rag_agent instead.",
        "nodes": [],
        "edges": [],
    }
