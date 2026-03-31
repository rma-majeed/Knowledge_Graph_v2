---
phase: 04-query-engine-answer-generation
plan: 02
type: execute
wave: 2
depends_on:
  - "04-01"
files_modified:
  - src/query/retriever.py
autonomous: true
requirements:
  - QUERY-02
  - QUERY-03

must_haves:
  truths:
    - "vector_search() embeds query_text via embed_query() and returns top-N chunk dicts from ChromaDB with keys chunk_id, text, metadata, distance, source='vector'"
    - "graph_expand() reads entity names from chunk_citations for the given chunk_ids, runs 1-hop KuzuDB MATCH per (source_type, rel_table, target_type) combination, fetches neighbor chunk IDs via CitationStore, hydrates chunk text from SQLite, returns list of chunk dicts with source='graph'"
    - "deduplicate_chunks() removes duplicates by chunk_id preserving insertion order"
    - "hybrid_retrieve() returns combined deduped list from vector_search + graph_expand; vector chunks are labelled source='vector', graph chunks source='graph'"
    - "test_query_retriever.py tests pass (no longer xfail)"
  artifacts:
    - path: "src/query/retriever.py"
      provides: "vector_search, graph_expand, deduplicate_chunks, hybrid_retrieve"
      exports:
        - vector_search
        - graph_expand
        - deduplicate_chunks
        - hybrid_retrieve
      min_lines: 100
  key_links:
    - from: "src/query/retriever.py"
      to: "src/embed/embedder.py"
      via: "embed_query(query_text, openai_client, embed_model)"
      pattern: "from src.embed.embedder import embed_query"
    - from: "src/query/retriever.py"
      to: "src/embed/vector_store.py"
      via: "VectorStore(chroma_path).query(embedding, n_results)"
      pattern: "from src.embed.vector_store import VectorStore"
    - from: "src/query/retriever.py"
      to: "src/graph/citations.py"
      via: "CitationStore(conn).get_chunks_for_entity(name, etype)"
      pattern: "from src.graph.citations import CitationStore"
    - from: "src/query/retriever.py"
      to: "src/graph/db_manager.py"
      via: "_OUTGOING relationship table map for 1-hop Cypher traversal"
      pattern: "kuzu.Connection"
---

<objective>
Implement `src/query/retriever.py` with full hybrid retrieval: vector similarity search via ChromaDB, 1-hop graph expansion via KuzuDB, and chunk deduplication.

Purpose: This is the retrieval foundation for QUERY-02 (vector search) and QUERY-03 (graph expansion). All retrieval logic lives here. Plans 04-03 and 04-04 consume the output of hybrid_retrieve() without touching retrieval logic.

Output: `src/query/retriever.py` fully implemented; `tests/test_query_retriever.py` stubs become passing.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/04-query-engine-answer-generation/04-RESEARCH.md
@.planning/phases/04-query-engine-answer-generation/04-01-SUMMARY.md

<interfaces>
<!-- src/embed/embedder.py — embed_query() signature -->
```python
def embed_query(query_text: str, client, model: str = "nomic-embed-text-v1.5") -> list[float]:
    """Return embedding vector for a single query string."""
```

<!-- src/embed/vector_store.py — VectorStore.query() return shape -->
```python
class VectorStore:
    def query(self, query_embedding: list[float], n_results: int = 10) -> list[dict]:
        """Returns: [{chunk_id: str, text: str, metadata: {filename, page_num, ...}, distance: float}, ...]"""
```

<!-- src/graph/citations.py — CitationStore.get_chunks_for_entity() return shape -->
```python
class CitationStore:
    def get_chunks_for_entity(self, entity_name: str, entity_type: str) -> list[dict]:
        """Returns: [{chunk_id: int, doc_id: int, filename: str, page_num: int}, ...]
        NOTE: does NOT include chunk_text — must hydrate from SQLite separately."""
```

<!-- src/graph/db_manager.py — relationship tables for 1-hop traversal -->
# _OUTGOING map for KuzuDB Cypher MATCH queries:
_OUTGOING = {
    "OEM": [
        ("IS_A", "OEM"), ("USES", "Technology"),
        ("USES_PROD", "Product"), ("PRODUCES", "Product"),
    ],
    "Supplier": [("USES_SUP", "Technology"), ("PRODUCES_SUP", "Product")],
    "Recommendation": [
        ("RECOMMENDS", "OEM"), ("RECOMMENDS_SUP", "Supplier"),
        ("RECOMMENDS_TECH", "Technology"), ("RECOMMENDS_PROD", "Product"),
    ],
    "Technology": [],
    "Product": [],
}

<!-- KuzuDB 0.11.3 Cypher pattern — CRITICAL: use result.get_all() NOT result.fetchall() -->
# result.get_all() returns list-of-lists, e.g. [["Toyota"], ["BMW"]]
conn = kuzu.Connection(db)
result = conn.execute(
    f"MATCH (s:{etype} {{canonical_name: '{safe_name}'}}) "
    f"-[:{rel_table}]->(t:{target_type}) "
    f"RETURN t.canonical_name AS name"
)
rows = result.get_all()  # [["Toyota"], ["BMW"]] — list of lists, NOT dicts

<!-- SQLite chunk_citations schema — for seeding graph traversal -->
# chunk_citations(citation_id, entity_canonical_name, entity_type, chunk_id)
# idx_citations_chunk on chunk_id enables fast entity lookup from chunk_id
conn.execute(
    "SELECT entity_canonical_name, entity_type FROM chunk_citations WHERE chunk_id IN (...)"
)

<!-- SQLite chunks schema — for hydrating graph chunk texts -->
# chunks(chunk_id, doc_id, chunk_text, page_num, embedding_flag, ...)
conn.execute("SELECT chunk_id, chunk_text FROM chunks WHERE chunk_id IN (?)", ...)
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement src/query/retriever.py</name>
  <files>src/query/retriever.py, tests/test_query_retriever.py</files>

  <read_first>
    - src/query/retriever.py (current stub — replace NotImplementedError with real implementation)
    - tests/test_query_retriever.py (current xfail stubs — remove xfail decorator once tests pass)
    - src/embed/embedder.py (embed_query signature and error handling)
    - src/embed/vector_store.py (VectorStore.query return shape — exact dict keys)
    - src/graph/citations.py (CitationStore.get_chunks_for_entity — returns no chunk_text, must hydrate)
    - src/graph/db_manager.py (_OUTGOING relationship map and _REL_TABLE_DDL for Cypher queries)
    - .planning/phases/04-query-engine-answer-generation/04-RESEARCH.md (Pattern 1 and Pattern 2 code blocks)
  </read_first>

  <behavior>
    - test_vector_search_returns_chunks: vector_search("EV battery technology", mock_client, ephemeral_chroma_path, n_results=3) returns list of dicts each with chunk_id, text, metadata, distance, source='vector'; length <= 3
    - test_graph_expansion_finds_neighbors: graph_expand([{"chunk_id": "1", ...}], sqlite_conn_with_citations, kuzu_db_with_oem_and_rel) returns list of chunk dicts with source='graph' for the neighbour entity's chunks
    - test_dedup_merged_chunks: deduplicate_chunks([{chunk_id:"1",...},{chunk_id:"2",...},{chunk_id:"1",...}]) returns list of length 2 with chunk_id "1" appearing once
    - test_hybrid_retrieve_combines_sources: hybrid_retrieve(...) result contains both source='vector' and source='graph' entries; no chunk_id repeated
  </behavior>

  <action>
Implement `src/query/retriever.py` replacing all NotImplementedError stubs. Follow the architecture from 04-RESEARCH.md Pattern 1 and Pattern 2 exactly.

Key implementation rules:
- `vector_search()`: calls `embed_query(query_text, openai_client, embed_model)` then `VectorStore(chroma_path).query(embedding, n_results)`. Adds `source='vector'` to each returned dict. Returns empty list if collection is empty (VectorStore.query already handles this).
- `_get_entities_for_chunks(conn, chunk_ids)`: private helper. SELECT entity_canonical_name, entity_type FROM chunk_citations WHERE chunk_id IN (...) using `conn.execute()` with a parameterised `IN` clause via `",".join("?" * len(chunk_ids))`. Returns list of (name, etype) tuples. Returns [] if chunk_ids is empty.
- `_get_neighbors(kuzu_db, cited_entities)`: private helper. Uses _OUTGOING dict (replicate from research doc) and `kuzu.Connection(kuzu_db).execute(cypher).get_all()`. `result.get_all()` returns list-of-lists — access `row[0]` for the name. Wrap each entity MATCH in try/except to tolerate missing nodes. Returns list of (name, etype) tuples as a deduplicated set converted to list.
- `_hydrate_graph_chunks(conn, chunk_citation_rows, n_per_entity)`: private helper. Takes list of {chunk_id, filename, page_num} dicts, fetches `chunk_text` from SQLite `chunks` table for all chunk_ids (single IN query), merges text back into dicts. Returns list of chunk dicts with keys chunk_id (int), text, filename, page_num, source='graph', distance=1.0.
- `graph_expand()`: calls `_get_entities_for_chunks` → `_get_neighbors` → `CitationStore(conn).get_chunks_for_entity()` capped at `n_per_entity` rows per entity → `_hydrate_graph_chunks`. Returns [] if vector_chunks is empty or no entities found.
- `deduplicate_chunks()`: iterate chunks, track seen `chunk_id` values in a set, skip duplicates. Normalise chunk_id to int for comparison (VectorStore returns str chunk_ids, graph returns int).
- `hybrid_retrieve()`: calls `vector_search()` → `graph_expand(vector_chunks, ...)` → `deduplicate_chunks(vector_chunks + graph_chunks)`.

After implementing, update `tests/test_query_retriever.py`:
- Remove `@pytest.mark.xfail(strict=False, reason="not implemented yet")` from all 4 tests
- Replace `raise NotImplementedError` with real test bodies using `chromadb.EphemeralClient()`, `tempfile.mkdtemp()` for KuzuDB, `unittest.mock.MagicMock` for openai client
  </action>

  <verify>
    <automated>cd "C:/Users/2171176/Documents/Python/Knowledge_Graph_v2" && python -m pytest tests/test_query_retriever.py -x -q -k "not lm_studio" --tb=short 2>&1 | tail -8</automated>
  </verify>

  <done>All 4 test_query_retriever tests pass (not xfail); hybrid_retrieve() importable and callable; no NotImplementedError remains in retriever.py</done>
</task>

</tasks>

<verification>
```bash
# Retriever tests pass
pytest tests/test_query_retriever.py -x -q --tb=short

# Import check
python -c "
from src.query.retriever import vector_search, graph_expand, deduplicate_chunks, hybrid_retrieve
print('retriever imports OK')
"

# Full suite still green (assembler/pipeline still xfail — that is expected)
pytest tests/ -x -q -k "not lm_studio" --tb=short 2>&1 | tail -5
```
</verification>

<success_criteria>
- tests/test_query_retriever.py: 4 tests PASS (not xfail, not ERROR)
- vector_search() returns list of dicts with source='vector' key present
- graph_expand() fetches neighbor chunks via 1-hop KuzuDB traversal; chunk_text hydrated from SQLite
- deduplicate_chunks() handles str and int chunk_ids uniformly
- hybrid_retrieve() combines both sources; no duplicate chunk_id in result
- Full test suite green: pytest tests/ -x -q -k "not lm_studio" exits 0
</success_criteria>

<output>
After completion, create `.planning/phases/04-query-engine-answer-generation/04-02-SUMMARY.md`
</output>
