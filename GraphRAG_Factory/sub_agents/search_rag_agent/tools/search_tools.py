"""Individual search tools for search_rag_agent (Phase 2).

Four standalone tools the agent can call independently or in combination:
  - vector_search  : ChromaDB semantic similarity search
  - bm25_search    : SQLite BM25 keyword search
  - graph_search   : KuzuDB entity graph traversal
  - rerank         : BGE cross-encoder re-scoring of chunk_ids from prior searches

DB connections (KuzuDB, SQLite, ChromaDB) are shared process-wide singletons
imported from db_singletons — this prevents KuzuDB file lock conflicts when
both sub-agents are loaded in the same process under adk web.
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

_EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-nomic-embed-text-v1.5")
_COLLECTION  = "chunks"

# Node types defined in src/graph/db_manager.py
_NODE_TYPES = ["OEM", "Supplier", "Technology", "Product", "Recommendation"]

# Shared process-wide DB singletons (avoids KuzuDB file lock between agents)
from GraphRAG_Factory.db_singletons import _get_sqlite_conn, _get_kuzu_db, _get_chroma_client

_embed_client = None


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


# ---------------------------------------------------------------------------
# Tool 4: Rerank
# ---------------------------------------------------------------------------

def rerank(query: str, chunk_ids: list[str]) -> dict:
    """Re-score a list of chunk_ids using the BGE cross-encoder reranker.

    Call this after vector_search or bm25_search to improve result ordering.
    The reranker scores each (query, chunk_text) pair together — it catches
    relevance that embedding similarity misses.

    Requires RAG_ENABLE_RERANKER=true in .env and the BGE model downloaded.
    If the reranker is unavailable, returns chunks in original order.

    Args:
        query: The original search query string.
        chunk_ids: List of chunk_id strings from a prior vector_search or bm25_search.

    Returns:
        Dict with status and reranked list of chunks with rerank_score added.
    """
    if not chunk_ids:
        return {"status": "success", "query": query, "count": 0, "results": []}

    try:
        # Fetch chunk texts from SQLite for the given chunk_ids
        conn = _get_sqlite_conn()
        placeholders = ",".join("?" * len(chunk_ids))
        rows = conn.execute(
            f"SELECT c.chunk_id, c.chunk_text, c.page_num, d.filename "
            f"FROM chunks c JOIN documents d ON c.doc_id = d.doc_id "
            f"WHERE c.chunk_id IN ({placeholders})",
            chunk_ids,
        ).fetchall()

        if not rows:
            return {"status": "success", "query": query, "count": 0, "results": [],
                    "message": "None of the provided chunk_ids were found in the database."}

        chunks = [
            {
                "chunk_id": str(r["chunk_id"]),
                "text": r["chunk_text"] or "",
                "page_num": r["page_num"] or 0,
                "filename": r["filename"] or "",
            }
            for r in rows
        ]

        # Apply BGE reranker if enabled
        from src.config.retrieval_config import RAG_ENABLE_RERANKER
        if RAG_ENABLE_RERANKER:
            from src.query.reranker import get_reranker
            reranked = get_reranker().rerank(query, chunks)
        else:
            reranked = chunks

        return {
            "status": "success",
            "query": query,
            "reranker_active": bool(RAG_ENABLE_RERANKER),
            "count": len(reranked),
            "results": [
                {
                    "chunk_id": c["chunk_id"],
                    "text": c["text"][:600],
                    "filename": c["filename"],
                    "page_num": c["page_num"],
                    "rerank_score": round(float(c.get("_rerank_score", 0.0)), 4),
                }
                for c in reranked
            ],
        }
    except Exception as exc:
        return {"status": "error", "query": query, "count": 0, "results": [], "error": str(exc)}


# ---------------------------------------------------------------------------
# Tool 5: Format citations
# ---------------------------------------------------------------------------

def format_citations(chunk_ids: list[str]) -> dict:
    """Build a formatted Citations block from a list of chunk_ids.

    ALWAYS call this as the last step before finishing your answer.
    Pass all chunk_ids collected from prior search tool results.
    Append the returned citations_block verbatim at the end of your answer.

    Args:
        chunk_ids: List of chunk_id strings used as evidence in the answer.

    Returns:
        Dict with 'citations_block' string — append it verbatim to your answer.
    """
    if not chunk_ids:
        return {"status": "success", "citations_block": "(No source citations available.)"}

    try:
        conn = _get_sqlite_conn()
        placeholders = ",".join("?" * len(chunk_ids))
        rows = conn.execute(
            f"SELECT c.chunk_id, c.page_num, d.filename "
            f"FROM chunks c JOIN documents d ON c.doc_id = d.doc_id "
            f"WHERE c.chunk_id IN ({placeholders})",
            chunk_ids,
        ).fetchall()

        # Deduplicate by (filename, page_num), preserve order of chunk_ids
        seen: set[tuple] = set()
        lines: list[str] = []
        index = 1
        for chunk_id in chunk_ids:
            row = next((r for r in rows if str(r["chunk_id"]) == str(chunk_id)), None)
            if row is None:
                continue
            key = (row["filename"], row["page_num"])
            if key not in seen:
                seen.add(key)
                lines.append(f"  [{index}] {row['filename']}, p.{row['page_num']}")
                index += 1

        if not lines:
            return {"status": "success", "citations_block": "(No source citations available.)"}

        return {"status": "success", "citations_block": "Citations:\n" + "\n".join(lines)}

    except Exception as exc:
        return {"status": "error", "citations_block": "(Citations unavailable.)", "error": str(exc)}
