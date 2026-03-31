"""Hybrid retriever: vector similarity search + 1-hop graph expansion.

Implements QUERY-02 (vector search via ChromaDB) and QUERY-03 (graph expansion
via KuzuDB). All retrieval logic lives here; downstream plans consume the output
of hybrid_retrieve() without modifying retrieval behaviour.

Public API:
    vector_search(query_text, openai_client, chroma_client, collection_name, embed_model, n_results) -> list[dict]
    graph_expand(vector_chunks, citation_store, kuzu_db, sqlite_conn, n_per_entity) -> list[dict]
    deduplicate_chunks(chunks) -> list[dict]
    hybrid_retrieve(query_text, openai_client, chroma_client, collection_name,
                    citation_store, kuzu_db, sqlite_conn, embed_model, n_results) -> list[dict]
"""
from __future__ import annotations

import kuzu

from src.embed.embedder import embed_query
from src.graph.citations import CitationStore

# Outgoing relationship map: src_type -> [(rel_table, target_type), ...]
# Mirrors the schema defined in src/graph/db_manager.py _REL_TABLE_DDL
_OUTGOING: dict[str, list[tuple[str, str]]] = {
    "OEM": [
        ("IS_A", "OEM"),
        ("USES", "Technology"),
        ("USES_PROD", "Product"),
        ("PRODUCES", "Product"),
    ],
    "Supplier": [
        ("USES_SUP", "Technology"),
        ("PRODUCES_SUP", "Product"),
    ],
    "Recommendation": [
        ("RECOMMENDS", "OEM"),
        ("RECOMMENDS_SUP", "Supplier"),
        ("RECOMMENDS_TECH", "Technology"),
        ("RECOMMENDS_PROD", "Product"),
    ],
    "Technology": [],
    "Product": [],
}


def vector_search(
    query_text: str,
    openai_client,
    chroma_client,
    collection_name: str = "chunks",
    embed_model: str = "nomic-embed-text-v1.5",
    n_results: int = 10,
) -> list[dict]:
    """Embed query_text and retrieve top-N chunks from ChromaDB.

    Args:
        query_text: Natural language query string.
        openai_client: openai.OpenAI client configured for LM Studio.
        chroma_client: An already-opened chromadb client instance (Ephemeral or Persistent).
        collection_name: ChromaDB collection name to query against.
        embed_model: Embedding model name to use via embed_query().
        n_results: Maximum number of chunks to return.

    Returns:
        List of dicts with keys: chunk_id, text, filename, page_num, source='vector', distance.
        Returns empty list if collection is empty or query fails.
    """
    embedding = embed_query(query_text, openai_client, embed_model)

    try:
        collection = chroma_client.get_or_create_collection(
            name=collection_name,
            configuration={"hnsw": {"space": "cosine"}},
        )
    except Exception:
        collection = chroma_client.get_collection(name=collection_name)

    count = collection.count()
    if count == 0:
        return []

    actual_n = min(n_results, count)
    results = collection.query(
        query_embeddings=[embedding],
        n_results=actual_n,
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    for i in range(len(results["ids"][0])):
        metadata = results["metadatas"][0][i] or {}
        chunks.append({
            "chunk_id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "filename": metadata.get("filename", ""),
            "page_num": metadata.get("page_num", 0),
            "source": "vector",
            "distance": results["distances"][0][i],
        })
    return chunks


def _get_entities_for_chunks(
    chunk_ids: list,
    sqlite_conn,
) -> list[tuple[str, str]]:
    """Query chunk_citations table to find entities mentioned in these chunks.

    Args:
        chunk_ids: List of chunk IDs (str or int) from vector search results.
        sqlite_conn: Open sqlite3.Connection to the chunks database.

    Returns:
        List of (entity_canonical_name, entity_type) tuples, deduplicated.
        Returns [] if chunk_ids is empty.
    """
    if not chunk_ids:
        return []

    # Normalise to int where possible (SQLite stores chunk_id as INTEGER)
    normalised = []
    for cid in chunk_ids:
        try:
            normalised.append(int(cid))
        except (ValueError, TypeError):
            normalised.append(cid)

    placeholders = ",".join("?" * len(normalised))
    rows = sqlite_conn.execute(
        f"SELECT DISTINCT entity_canonical_name, entity_type "
        f"FROM chunk_citations WHERE chunk_id IN ({placeholders})",
        normalised,
    ).fetchall()

    if not rows:
        return []
    if rows and hasattr(rows[0], "keys"):
        return [(r["entity_canonical_name"], r["entity_type"]) for r in rows]
    return [(r[0], r[1]) for r in rows]


def _get_neighbors(
    entity_name: str,
    entity_type: str,
    kuzu_db,
) -> list[tuple[str, str]]:
    """Traverse 1 hop outward from entity_name in KuzuDB.

    Uses _OUTGOING map to enumerate relationship tables per entity type.
    Each MATCH query targets a specific (src_type, rel_table, tgt_type) combination,
    matching by canonical_name.

    Args:
        entity_name: Canonical entity name to traverse from.
        entity_type: Node table type (OEM|Supplier|Technology|Product|Recommendation).
        kuzu_db: Open kuzu.Database instance.

    Returns:
        Deduplicated list of (neighbor_canonical_name, neighbor_type) tuples.
    """
    rel_patterns = _OUTGOING.get(entity_type, [])
    if not rel_patterns:
        return []

    seen: set[tuple[str, str]] = set()
    neighbors: list[tuple[str, str]] = []
    safe_name = entity_name.replace("'", "\\'")

    for rel_table, target_type in rel_patterns:
        try:
            conn = kuzu.Connection(kuzu_db)
            result = conn.execute(
                f"MATCH (a:{entity_type} {{canonical_name: '{safe_name}'}})"
                f"-[:{rel_table}]->(b:{target_type}) "
                f"RETURN b.canonical_name",
            )
            rows = result.get_all()  # list-of-lists: [["Toyota"], ...]
            for row in rows:
                neighbor_name = row[0]
                key = (neighbor_name, target_type)
                if key not in seen:
                    seen.add(key)
                    neighbors.append(key)
        except Exception:
            # Tolerate missing tables or nodes gracefully
            continue

    return neighbors


def _hydrate_graph_chunks(
    citation_rows: list[dict],
    sqlite_conn,
) -> list[dict]:
    """Fetch chunk_text from SQLite and build graph chunk dicts.

    CitationStore.get_chunks_for_entity() returns metadata only (chunk_id,
    doc_id, filename, page_num) — no chunk_text. This helper performs a second
    SQLite query to retrieve chunk_text for all chunk_ids in one IN clause.

    Args:
        citation_rows: List of dicts from CitationStore.get_chunks_for_entity()
            with keys: chunk_id, doc_id, filename, page_num.
        sqlite_conn: Open sqlite3.Connection.

    Returns:
        List of chunk dicts with keys: chunk_id, text, filename, page_num,
        source='graph', distance=1.0.
    """
    if not citation_rows:
        return []

    chunk_ids = [r["chunk_id"] for r in citation_rows]
    placeholders = ",".join("?" * len(chunk_ids))
    text_rows = sqlite_conn.execute(
        f"SELECT chunk_id, chunk_text FROM chunks WHERE chunk_id IN ({placeholders})",
        chunk_ids,
    ).fetchall()

    # Build lookup: chunk_id -> chunk_text
    if text_rows and hasattr(text_rows[0], "keys"):
        text_map = {r["chunk_id"]: r["chunk_text"] for r in text_rows}
    else:
        text_map = {r[0]: r[1] for r in text_rows}

    # Build metadata lookup from citation_rows
    meta_map = {r["chunk_id"]: r for r in citation_rows}

    result = []
    for cid, text in text_map.items():
        meta = meta_map.get(cid, {})
        result.append({
            "chunk_id": cid,
            "text": text or "",
            "filename": meta.get("filename", ""),
            "page_num": meta.get("page_num", 0),
            "source": "graph",
            "distance": 1.0,
        })
    return result


def graph_expand(
    vector_chunks: list[dict],
    citation_store: CitationStore,
    kuzu_db,
    sqlite_conn,
    n_per_entity: int = 5,
) -> list[dict]:
    """Expand retrieval via 1-hop KuzuDB graph traversal seeded from vector_chunks.

    Steps:
      1. Extract chunk_ids from vector_chunks.
      2. Query chunk_citations for entities mentioned in those chunks.
      3. For each entity, traverse 1 hop outward in KuzuDB to find neighbors.
      4. For each neighbor entity, retrieve chunks via CitationStore (capped at n_per_entity).
      5. Hydrate chunk_text from SQLite for all neighbor chunks.

    Args:
        vector_chunks: Output of vector_search() — list of chunk dicts.
        citation_store: CitationStore instance wrapping the SQLite connection.
        kuzu_db: Open kuzu.Database instance.
        sqlite_conn: Open sqlite3.Connection (same DB as citation_store).
        n_per_entity: Max chunks per neighbor entity to include.

    Returns:
        List of additional chunk dicts with source='graph'. May be empty if no
        entities are found or graph has no relevant neighbors.
    """
    if not vector_chunks:
        return []

    chunk_ids = [c["chunk_id"] for c in vector_chunks]
    cited_entities = _get_entities_for_chunks(chunk_ids, sqlite_conn)

    if not cited_entities:
        return []

    # Collect all neighbor entities via 1-hop traversal
    neighbor_entities: list[tuple[str, str]] = []
    seen_neighbors: set[tuple[str, str]] = set()

    for entity_name, entity_type in cited_entities:
        neighbors = _get_neighbors(entity_name, entity_type, kuzu_db)
        for neighbor in neighbors:
            if neighbor not in seen_neighbors:
                seen_neighbors.add(neighbor)
                neighbor_entities.append(neighbor)

    if not neighbor_entities:
        return []

    # Fetch and hydrate chunks for each neighbor entity
    graph_chunks: list[dict] = []
    for neighbor_name, neighbor_type in neighbor_entities:
        citation_rows = citation_store.get_chunks_for_entity(neighbor_name, neighbor_type)
        citation_rows = citation_rows[:n_per_entity]
        hydrated = _hydrate_graph_chunks(citation_rows, sqlite_conn)
        graph_chunks.extend(hydrated)

    return graph_chunks


def deduplicate_chunks(chunks: list[dict]) -> list[dict]:
    """Deduplicate chunks by chunk_id, preserving insertion order.

    Prefers the first occurrence of each chunk_id. When both vector and graph
    sources contain the same chunk, vector chunks appear first (from hybrid_retrieve
    ordering: vector_chunks + graph_chunks), so vector source is preserved.

    chunk_id may be str (from ChromaDB) or int (from SQLite) — normalises to str
    for comparison to treat "42" and 42 as the same chunk.

    Args:
        chunks: List of chunk dicts, potentially containing duplicates.

    Returns:
        Deduplicated list preserving original order of first occurrences.
    """
    seen: set[str] = set()
    result: list[dict] = []
    for chunk in chunks:
        # Normalise chunk_id to str for cross-source comparison
        key = str(chunk["chunk_id"])
        if key not in seen:
            seen.add(key)
            result.append(chunk)
    return result


def hybrid_retrieve(
    query_text: str,
    openai_client,
    chroma_client,
    collection_name: str,
    citation_store: CitationStore,
    kuzu_db,
    sqlite_conn,
    embed_model: str = "nomic-embed-text-v1.5",
    n_results: int = 10,
) -> list[dict]:
    """Full hybrid retrieval: vector search followed by 1-hop graph expansion.

    Combines ChromaDB semantic similarity search with KuzuDB graph traversal
    to surface both directly relevant chunks and contextually related chunks.

    Args:
        query_text: Natural language query string.
        openai_client: openai.OpenAI client configured for LM Studio.
        chroma_client: An already-opened chromadb client instance.
        collection_name: ChromaDB collection name to query against.
        citation_store: CitationStore instance for entity-to-chunk lookups.
        kuzu_db: Open kuzu.Database instance for graph traversal.
        sqlite_conn: Open sqlite3.Connection for chunk text hydration.
        embed_model: Embedding model name.
        n_results: Number of vector search results to retrieve.

    Returns:
        Combined, deduplicated list of chunk dicts. Vector chunks appear first,
        followed by graph-expanded chunks not already in the vector results.
        Each dict has keys: chunk_id, text, filename, page_num, source, distance.
    """
    vector_chunks = vector_search(
        query_text, openai_client, chroma_client, collection_name, embed_model, n_results
    )
    graph_chunks = graph_expand(
        vector_chunks, citation_store, kuzu_db, sqlite_conn
    )
    return deduplicate_chunks(vector_chunks + graph_chunks)
