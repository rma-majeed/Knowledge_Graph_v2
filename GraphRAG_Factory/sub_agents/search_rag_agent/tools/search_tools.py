"""Individual search tools for search_rag_agent (Phase 2).

Three standalone tools the agent can call independently or in combination:
  - vector_search  : ChromaDB semantic similarity search
  - bm25_search    : SQLite BM25 keyword search
  - graph_search   : KuzuDB entity graph traversal

Each tool uses lazy singleton DB connections (same pattern as pipeline_tools.py).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env", override=True)

_CHROMA_PATH = str(_PROJECT_ROOT / "data" / "chroma_db")
_SQLITE_PATH = str(_PROJECT_ROOT / "data" / "chunks.db")
_KUZU_PATH   = str(_PROJECT_ROOT / "data" / "kuzu_db")
_EMBED_MODEL  = os.getenv("EMBED_MODEL", "text-embedding-nomic-embed-text-v1.5")
_COLLECTION   = "chunks"

# Node types defined in src/graph/db_manager.py
_NODE_TYPES = ["OEM", "Supplier", "Technology", "Product", "Recommendation"]

# Lazy singletons — created on first tool call, reused after
_sqlite_conn   = None
_kuzu_db       = None
_chroma_client = None
_embed_client  = None


def _get_sqlite_conn():
    global _sqlite_conn
    if _sqlite_conn is None:
        import sqlite3
        _sqlite_conn = sqlite3.connect(_SQLITE_PATH, check_same_thread=False)
        _sqlite_conn.row_factory = sqlite3.Row
    return _sqlite_conn


def _get_kuzu_db():
    global _kuzu_db
    if _kuzu_db is None:
        import kuzu
        _kuzu_db = kuzu.Database(_KUZU_PATH)
    return _kuzu_db


def _get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        import chromadb
        _chroma_client = chromadb.PersistentClient(path=_CHROMA_PATH)
    return _chroma_client


def _get_embed_client():
    global _embed_client
    if _embed_client is None:
        from src.config.providers import get_embed_client
        _embed_client = get_embed_client()
    return _embed_client


# ---------------------------------------------------------------------------
# Tool 1: Vector search
# ---------------------------------------------------------------------------

def vector_search(query: str, top_k: int = 10) -> dict:
    """Search ChromaDB for chunks semantically similar to the query.

    Use this for broad conceptual questions where the exact keywords may
    vary — e.g. 'electric vehicle strategies', 'cost reduction initiatives'.

    Args:
        query: Natural language search query.
        top_k: Number of results to return (default 10, max 20).

    Returns:
        Dict with status, count, and list of matching chunks
        (chunk_id, text snippet, filename, page_num, score).
    """
    top_k = min(top_k, 20)
    try:
        from src.query.retriever import vector_search as _vs
        chunks = _vs(
            query_text=query,
            openai_client=_get_embed_client(),
            chroma_client=_get_chroma_client(),
            collection_name=_COLLECTION,
            embed_model=_EMBED_MODEL,
            n_results=top_k,
        )
        return {
            "status": "success",
            "query": query,
            "count": len(chunks),
            "results": [
                {
                    "chunk_id": c["chunk_id"],
                    "text": c["text"][:600],
                    "filename": c["filename"],
                    "page_num": c["page_num"],
                    "score": round(1.0 - c.get("distance", 1.0), 4),
                }
                for c in chunks
            ],
        }
    except Exception as exc:
        return {"status": "error", "query": query, "count": 0, "results": [], "error": str(exc)}


# ---------------------------------------------------------------------------
# Tool 2: BM25 keyword search
# ---------------------------------------------------------------------------

def bm25_search(query: str, top_k: int = 10) -> dict:
    """Search the document corpus using BM25 keyword matching.

    Use this when the query contains specific terms, names, or acronyms
    likely to appear verbatim in the documents — e.g. 'BOSCH', 'OTA update',
    'Tier 1 supplier', 'ISO 26262'.

    Args:
        query: Keyword search query string.
        top_k: Number of results to return (default 10, max 20).

    Returns:
        Dict with status, count, and list of matching chunks
        (chunk_id, text snippet, filename, page_num, bm25_score).
    """
    top_k = min(top_k, 20)
    try:
        from src.query.bm25_index import BM25Indexer
        conn = _get_sqlite_conn()
        rows = conn.execute(
            "SELECT c.chunk_id, c.chunk_text, c.page_num, d.filename "
            "FROM chunks c JOIN documents d ON c.doc_id = d.doc_id"
        ).fetchall()
        all_chunks = [
            {
                "chunk_id": str(r["chunk_id"]),
                "text": r["chunk_text"] or "",
                "page_num": r["page_num"] or 0,
                "filename": r["filename"] or "",
                "source": "bm25",
                "distance": 1.0,
            }
            for r in rows
        ]
        indexer = BM25Indexer()
        indexer.build(all_chunks)
        results = indexer.query(query, n_results=top_k)
        return {
            "status": "success",
            "query": query,
            "count": len(results),
            "results": [
                {
                    "chunk_id": c["chunk_id"],
                    "text": c["text"][:600],
                    "filename": c["filename"],
                    "page_num": c["page_num"],
                    "bm25_score": round(float(1.0 / (c.get("distance", 1.0) + 1e-9)), 4),
                }
                for c in results
            ],
        }
    except Exception as exc:
        return {"status": "error", "query": query, "count": 0, "results": [], "error": str(exc)}


# ---------------------------------------------------------------------------
# Tool 3: Graph search
# ---------------------------------------------------------------------------

def graph_search(entity: str, hops: int = 1) -> dict:
    """Search the knowledge graph for an entity and its connected relationships.

    Use this to explore how a specific company, technology, or product connects
    to others in the knowledge graph — e.g. 'Toyota', 'solid-state battery',
    'BOSCH', 'autonomous driving'.

    The graph covers node types: OEM, Supplier, Technology, Product, Recommendation.
    Relationships include: USES, PRODUCES, IS_A, RECOMMENDS and their variants.

    Args:
        entity: Entity name to look up (partial match supported).
        hops: Graph traversal depth — 1 returns direct neighbours (default).

    Returns:
        Dict with status, matched nodes, and their 1-hop relationships.
    """
    hops = min(hops, 2)
    try:
        import kuzu
        from src.query.retriever import _get_neighbors  # reuse tested traversal logic

        db = _get_kuzu_db()
        safe_entity = entity.replace("'", "\\'").lower()

        # Step 1: find matching nodes across all types
        matched_nodes: list[dict] = []
        for node_type in _NODE_TYPES:
            try:
                conn = kuzu.Connection(db)
                result = conn.execute(
                    f"MATCH (n:{node_type}) "
                    f"WHERE lower(n.canonical_name) CONTAINS '{safe_entity}' "
                    f"RETURN n.canonical_name LIMIT 5"
                )
                rows = result.get_all()
                for row in rows:
                    matched_nodes.append({"name": row[0], "type": node_type})
            except Exception:
                continue

        if not matched_nodes:
            return {
                "status": "not_found",
                "entity": entity,
                "message": f"No entity matching '{entity}' found in the knowledge graph.",
                "matched_nodes": [],
                "relationships": [],
            }

        # Step 2: get 1-hop neighbours for each matched node
        relationships: list[dict] = []
        seen: set[tuple] = set()

        for node in matched_nodes[:5]:
            neighbours = _get_neighbors(node["name"], node["type"], db)
            for neighbour_name, neighbour_type in neighbours:
                key = (node["name"], neighbour_name)
                if key not in seen:
                    seen.add(key)
                    relationships.append({
                        "from": node["name"],
                        "from_type": node["type"],
                        "to": neighbour_name,
                        "to_type": neighbour_type,
                    })

        return {
            "status": "success",
            "entity": entity,
            "matched_nodes": matched_nodes,
            "relationship_count": len(relationships),
            "relationships": relationships[:40],
        }
    except Exception as exc:
        return {
            "status": "error",
            "entity": entity,
            "matched_nodes": [],
            "relationships": [],
            "error": str(exc),
        }
