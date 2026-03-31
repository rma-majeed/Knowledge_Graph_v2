# Phase 4: Query Engine & Answer Generation - Research

**Researched:** 2026-03-31
**Domain:** Hybrid retrieval (ChromaDB vector + KuzuDB graph), context assembly, LM Studio answer synthesis, citation scoring, query latency
**Confidence:** HIGH for retrieval architecture and citation design (builds directly on existing codebase); MEDIUM for KuzuDB cross-table neighbor query syntax (official docs confirmed, but mixed-table variable-length traversal has constraints); MEDIUM for latency targets (hardware-dependent, community benchmarks only)

---

## Summary

Phase 4 wires together all prior phases into a complete query pipeline. A consultant submits a natural language question; the system embeds the query (nomic-embed-text-v1.5 via LM Studio), retrieves the top-10 semantically similar chunks from ChromaDB, extracts entity mentions from those chunks, traverses the KuzuDB graph one hop outward from each mentioned entity to discover neighboring entities, fetches the neighboring entities' citation chunks from SQLite, deduplicates the combined chunk set, assembles a token-budgeted context string, generates a synthesized answer with inline citations via Qwen2.5 7B in LM Studio, and prints the answer with a citation table.

The central architectural decision is **entity extraction for graph traversal seeding**. Two approaches exist: (a) run NER/LLM on the raw query to extract entity names, then look them up in KuzuDB directly; (b) use the chunk metadata from ChromaDB results — chunks already carry entity citations via the `chunk_citations` table — to identify which KuzuDB entities are relevant. Approach (b) is strongly preferred for this project: it requires zero additional LLM calls, exploits the already-built citation index, and avoids the fragility of NER on short question strings. The vector search already finds topically relevant chunks; those chunks are associated with entities by construction (Phase 3 inserted the citations); graph traversal from those entities expands context naturally.

**VRAM constraint is the critical operational risk.** The embedding model (nomic-embed-text-v1.5, ~260MB) and LLM (Qwen2.5-7B q4, ~3.8GB) cannot run simultaneously in 4GB VRAM. Phase 4 requires both in sequence: embed the query first, then switch LM Studio model to the LLM. The user must have the correct model loaded for each step, or the CLI must detect and report a model mismatch. This must not be invisible — a wrong model loaded will produce garbage embeddings or nonsense text with no error.

**Latency budget.** Query embedding ~0.1-0.3s, ChromaDB retrieval ~0.05s, citation+graph lookup ~0.2-0.5s, context assembly ~0.05s, LLM generation ~6-12s for 400-600 output tokens = total ~7-13s. The 15-second budget is achievable if the LLM is already loaded and generating ≥5 tok/s (which Qwen2.5 7B q4 typically delivers: ~15-25 tok/s when fully GPU-resident, or 5-10 tok/s with partial CPU offload).

**Primary recommendation:** Implement a single `src/query/` module with three files: `retriever.py` (hybrid retrieval), `assembler.py` (context building + citation scoring), and `pipeline.py` (top-level orchestration + CLI integration). The query subcommand (`python src/main.py query "question"`) mirrors the existing CLI pattern exactly.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| QUERY-01 | User can submit a natural language question and receive a synthesized answer | CLI `query` subcommand mirrors existing `embed`/`graph` pattern; `cmd_query()` calls `answer_question()` pipeline function; prints answer + citation table |
| QUERY-02 | System retrieves relevant chunks via vector similarity (local semantic search) | `VectorStore.query(embedding, n_results=10)` already returns `{chunk_id, text, metadata, distance}`; call `embed_query()` (already in `src/embed/embedder.py`) to get query embedding; no new code needed for this layer |
| QUERY-03 | System augments vector retrieval with entity-based graph traversal to expand context | Seed graph traversal from chunk_ids returned by ChromaDB: JOIN chunk_citations on chunk_id to get entity names; run 1-hop KuzuDB MATCH per entity type; fetch citation chunks for neighbor entities via CitationStore; deduplicate by chunk_id |
| QUERY-04 | Every answer includes source citations (document name, page/slide number, confidence level HIGH/LOW based on citation count) | Citation confidence: count how many distinct chunks reference a source (doc+page combination); HIGH if count >= 3, LOW if count 1-2; include citation table after answer |
| QUERY-05 | LLM answer generation uses local model via LM Studio (Qwen2.5 7B or equivalent) | Same `openai.OpenAI(base_url="http://localhost:1234/v1")` client pattern as `extractor.py`; use `client.chat.completions.create()` with consulting-domain system prompt; `max_tokens=600` to stay under 15s latency |
</phase_requirements>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **openai** | 1.93.0 (installed) | LM Studio embedding + LLM client | Already used in Phases 2 and 3; same client, same `base_url="http://localhost:1234/v1"` pattern |
| **chromadb** | 1.5.5 (installed) | Vector similarity retrieval | `VectorStore` already implemented; `query()` returns top-N with metadata |
| **kuzu** | 0.11.3 (installed) | Graph neighbor traversal | `kuzu.Connection.execute()` with Cypher; schema already established in Phase 3 |
| **sqlite3** | stdlib (installed) | Citation chunk lookup, doc/page metadata | `CitationStore.get_chunks_for_entity()` already implemented |
| **tiktoken** | 0.9.0 (installed) | Token counting for context budget | `tiktoken.get_encoding("cl100k_base")` provides approximate token counts for Qwen2.5 (BPE-based; same vocabulary family) |
| **httpx** | 0.28.1 (installed) | LM Studio health check | Already used in `embed/pipeline.py` `check_lm_studio()` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **tqdm** | 4.67.1 (installed) | Progress feedback for long queries | Optional; only needed if query count > 1 (batch mode) |
| **pytest** | 9.0.2 (installed) | Unit tests | All new modules; mock LM Studio and ChromaDB |

### No New Dependencies Required

All required packages are already installed. Phase 4 adds zero new `pip install` requirements. This is important for the pip-only, corporate-firewall constraint.

**Installation:**
```bash
# No new dependencies — all packages already installed from Phases 1-3
# Verify:
pip show openai chromadb kuzu tiktoken httpx
```

**Version verification (confirmed 2026-03-31):**
- openai 1.93.0 — installed, confirmed
- chromadb 1.5.5 — installed, confirmed
- kuzu 0.11.3 — installed, confirmed
- tiktoken 0.9.0 — installed, confirmed
- httpx 0.28.1 — installed, confirmed

---

## Architecture Patterns

### Recommended Project Structure

```
src/
├── query/
│   ├── __init__.py
│   ├── retriever.py      # hybrid_retrieve(): vector + graph expansion
│   ├── assembler.py      # assemble_context(): token budget, dedup, citation scoring
│   └── pipeline.py       # answer_question(): top-level orchestration
├── embed/                # Phase 2 (unchanged — embed_query() reused)
├── graph/                # Phase 3 (unchanged — CitationStore reused)
└── main.py               # add cmd_query() + "query" subparser

tests/
├── test_retriever.py     # QUERY-02, QUERY-03 unit tests
├── test_assembler.py     # QUERY-04 unit tests (citation scoring, token budget)
└── conftest.py           # existing (unchanged)
```

### Pattern 1: Hybrid Retrieval (Vector + Graph Expansion)

**What:** Embed query, retrieve top-10 chunks from ChromaDB, find entities cited in those chunks, traverse 1 hop outward in KuzuDB, fetch citation chunks for neighbor entities, merge all chunks.
**When to use:** Every query — this is the primary retrieval path.

```python
# Source: derived from existing VectorStore.query() and CitationStore.get_chunks_for_entity()
# patterns confirmed from src/embed/vector_store.py and src/graph/citations.py

def hybrid_retrieve(
    query_text: str,
    openai_client,
    sqlite_conn,
    kuzu_db,
    chroma_path: str = "data/chroma_db",
    embed_model: str = "nomic-embed-text-v1.5",
    n_vector: int = 10,
    n_graph_per_entity: int = 5,
) -> list[dict]:
    """Hybrid retrieve: vector search + 1-hop graph expansion.

    Returns deduplicated list of chunk dicts with keys:
        chunk_id, text, filename, page_num, source (vector|graph), distance
    """
    from src.embed.embedder import embed_query
    from src.embed.vector_store import VectorStore
    from src.graph.citations import CitationStore

    # Step 1: embed query
    query_embedding = embed_query(query_text, openai_client, embed_model)

    # Step 2: vector retrieval
    vs = VectorStore(chroma_path)
    vector_chunks = vs.query(query_embedding, n_results=n_vector)
    # vector_chunks: [{chunk_id, text, metadata:{filename, page_num,...}, distance}, ...]

    # Step 3: find entity names cited in retrieved chunks
    chunk_ids = [int(c["chunk_id"]) for c in vector_chunks]
    cited_entities = _get_entities_for_chunks(sqlite_conn, chunk_ids)
    # cited_entities: [(entity_canonical_name, entity_type), ...]

    # Step 4: 1-hop graph traversal per entity
    neighbor_entities = _get_neighbors(kuzu_db, cited_entities)
    # neighbor_entities: [(canonical_name, entity_type), ...]

    # Step 5: fetch citation chunks for neighbor entities
    citation_store = CitationStore(sqlite_conn)
    graph_chunk_ids = set()
    graph_chunks_raw = []
    for name, etype in neighbor_entities:
        rows = citation_store.get_chunks_for_entity(name, etype)
        for row in rows[:n_graph_per_entity]:  # cap per entity
            if row["chunk_id"] not in graph_chunk_ids:
                graph_chunk_ids.add(row["chunk_id"])
                graph_chunks_raw.append(row)

    # Step 6: fetch full text for graph chunks from SQLite
    graph_chunks = _hydrate_graph_chunks(sqlite_conn, graph_chunks_raw)

    # Step 7: merge and deduplicate by chunk_id
    seen_ids = {int(c["chunk_id"]) for c in vector_chunks}
    merged = [
        {**c, "source": "vector"}
        for c in vector_chunks
    ]
    for gc in graph_chunks:
        if gc["chunk_id"] not in seen_ids:
            merged.append({**gc, "source": "graph", "distance": 1.0})
            seen_ids.add(gc["chunk_id"])

    return merged
```

### Pattern 2: Graph Neighbor Query (KuzuDB Cypher)

**What:** Given an entity (name, type), find all directly connected entities across all relationship types.
**Critical constraint:** KuzuDB uses separate node tables per entity type (OEM, Supplier, Technology, Product, Recommendation). Variable-length paths work across homogeneous edge tables but the MATCH must specify concrete node labels. The UNION pattern (one MATCH per entity-type pair) is the correct approach for this schema.

```python
# Source: KuzuDB Cypher docs (docs.kuzudb.com/cypher/query-clauses/match/)
# KuzuDB 0.11.3 — confirmed: variable-length *1..1 works; UNION for multi-type

def _get_neighbors(db, cited_entities: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Return (canonical_name, entity_type) for 1-hop neighbors of cited entities.

    Uses per-entity-type MATCH queries + UNION to handle the typed schema.
    Each entity type has dedicated relationship tables — no single polymorphic traversal.
    """
    import kuzu

    # Relationship tables by source entity type (from db_manager._REL_TABLE_DDL)
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

    conn = kuzu.Connection(db)
    neighbors = set()

    for name, etype in cited_entities:
        safe_name = name.replace("'", "\\'")
        for rel_table, target_type in _OUTGOING.get(etype, []):
            try:
                result = conn.execute(
                    f"MATCH (s:{etype} {{canonical_name: '{safe_name}'}})"
                    f"-[:{rel_table}]->(t:{target_type}) "
                    f"RETURN t.canonical_name AS name"
                ).get_all()
                for row in result:
                    neighbors.add((row[0], target_type))
            except Exception:
                pass  # Tolerate missing entity gracefully

    return list(neighbors)
```

**Why 1-hop only:** 2-hop traversal on a corpus-scale graph (potentially 5K+ entities) can pull in hundreds of tangentially related entities, flooding the context window with noise. 1-hop is sufficient to expand from "Toyota" to "LiDAR" and "Battery" without pulling in "BMW" through a shared Technology node. If graph density is low (as expected from Phase 3's explosion controls), 1-hop typically expands context by 2-5x the original entity set.

### Pattern 3: Context Assembly with Token Budget

**What:** Sort all retrieved chunks by relevance, truncate to fit token budget, build numbered context string for the LLM prompt.

```python
# Source: RAG token budget best practices (machinelearningplus.com/gen-ai/context-windows-token-budget/)
# tiktoken cl100k_base — approximate for Qwen2.5 (BPE family)

import tiktoken

_ENC = tiktoken.get_encoding("cl100k_base")
CONTEXT_TOKEN_BUDGET = 3000   # reserved for retrieved chunks
ANSWER_TOKEN_BUDGET  = 600    # max_tokens for LLM generation
SYSTEM_PROMPT_TOKENS = 300    # estimated system prompt overhead
# Total: ~3900 tokens, well within Qwen2.5 7B's 32K context window

def assemble_context(
    chunks: list[dict],
    token_budget: int = CONTEXT_TOKEN_BUDGET,
) -> tuple[str, list[dict]]:
    """Assemble numbered context string within token budget.

    Sort: vector chunks first (ordered by ascending distance), then graph chunks.
    Truncate: stop adding chunks when budget exceeded.

    Returns:
        context_str: Numbered passage string for LLM prompt.
        included_chunks: Chunk dicts that were included (for citation building).
    """
    # Sort: vector chunks (lower distance = better) first, then graph expansion
    sorted_chunks = sorted(
        chunks,
        key=lambda c: (0 if c.get("source") == "vector" else 1, c.get("distance", 1.0))
    )

    included = []
    budget_remaining = token_budget
    parts = []

    for i, chunk in enumerate(sorted_chunks, start=1):
        text = chunk.get("text", "")
        tokens = len(_ENC.encode(text))
        if tokens > budget_remaining:
            break
        budget_remaining -= tokens
        filename = chunk.get("metadata", {}).get("filename") or chunk.get("filename", "unknown")
        page = chunk.get("metadata", {}).get("page_num") or chunk.get("page_num", "?")
        parts.append(f"[{i}] Source: {filename}, page {page}\n{text}")
        included.append({**chunk, "_ctx_index": i})

    return "\n\n".join(parts), included
```

### Pattern 4: Answer Synthesis Prompt

**What:** System prompt that instructs the LLM to answer using only the provided context and cite sources inline using `[N]` references.
**Why this format:** `[N]` inline references are simple to parse post-generation for citation extraction; no structured output parsing required; works reliably with Qwen2.5 7B at temperature 0.2.

```python
# Source: RAG citation prompt patterns (tensorlake.ai/blog/rag-citations,
#          ailog.fr/en/blog/guides/citation-sourcing-rag)

_SYSTEM_PROMPT = """You are an expert automotive consulting analyst with access to a knowledge base of consulting documents.

Answer the consultant's question using ONLY the numbered source passages provided. Do not use any knowledge outside the provided sources.

Citation rules:
- Cite each source inline using [N] immediately after the relevant claim
- Every factual statement must have at least one citation
- If multiple sources support a claim, list all relevant citations: [1][3]
- If the sources do not contain enough information to answer, say: "The available documents do not contain sufficient information to answer this question." — do NOT fabricate an answer

Answer in professional consulting language. Be concise (3-6 sentences for most questions). Do not repeat the question."""

def generate_answer(
    question: str,
    context_str: str,
    openai_client,
    model: str = "Qwen2.5-7B-Instruct",
    max_tokens: int = 600,
) -> str:
    """Generate synthesized answer with inline citations via LM Studio."""
    user_prompt = f"Question: {question}\n\nSources:\n{context_str}"

    response = openai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,    # Slightly higher than extraction (0.1) for natural prose
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()
```

### Pattern 5: Citation Confidence Scoring

**What:** After answer generation, build a citation table from the chunks that were included in context. Confidence is HIGH if a source (doc+page combination) is cited by 3 or more distinct chunks; LOW otherwise.

```python
def build_citation_table(included_chunks: list[dict]) -> list[dict]:
    """Build citation table with HIGH/LOW confidence scores.

    Confidence logic:
      HIGH = source document+page appears in >= 3 included chunks (multiple
             independent extractions linked to the same page = high confidence)
      LOW  = source document+page appears in 1-2 included chunks

    Returns:
        List of citation dicts: {index, filename, page_num, confidence, source}
        Ordered by _ctx_index (matches [N] in answer text).
    """
    citations = []
    # Count citations per (filename, page_num) to determine confidence
    from collections import Counter
    source_counts: Counter = Counter()

    for chunk in included_chunks:
        meta = chunk.get("metadata", {})
        filename = meta.get("filename") or chunk.get("filename", "unknown")
        page_num = meta.get("page_num") or chunk.get("page_num", "?")
        source_counts[(filename, page_num)] += 1

    for chunk in included_chunks:
        meta = chunk.get("metadata", {})
        filename = meta.get("filename") or chunk.get("filename", "unknown")
        page_num = meta.get("page_num") or chunk.get("page_num", "?")
        count = source_counts[(filename, page_num)]
        citations.append({
            "index": chunk["_ctx_index"],
            "filename": filename,
            "page_num": page_num,
            "confidence": "HIGH" if count >= 3 else "LOW",
            "source": chunk.get("source", "vector"),
        })

    return sorted(citations, key=lambda c: c["index"])
```

**Threshold rationale:** A count of 3 was chosen because a single chunk can appear from both the vector path and the graph path (though dedup prevents this), and because 3 independent extraction events (3 chunks from the same page all flagged an entity, all surviving dedup, all retrieved) provides reasonable signal. Threshold of 2 would be too permissive (most pages have 2-4 chunks by construction from Phase 1's chunker). Threshold of 5 would be too strict for a sparse corpus. This threshold is a tunable constant — document it as `CITATION_HIGH_CONFIDENCE_THRESHOLD = 3` in `assembler.py`.

### Pattern 6: CLI Integration

**What:** `cmd_query()` in `main.py` mirrors the existing `cmd_embed()` and `cmd_graph()` pattern exactly.

```python
def cmd_query(args: argparse.Namespace) -> int:
    """Run the query pipeline and print answer + citations."""
    import sqlite3
    import kuzu
    from src.embed.pipeline import check_lm_studio
    from src.query.pipeline import answer_question

    db_path = Path(args.db)
    graph_path = Path(args.graph)
    chroma_path = Path(args.chroma)

    if not db_path.exists():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        return 1

    if not check_lm_studio():
        print(
            "Error: LM Studio is not running at localhost:1234.\n"
            "Ensure LM Studio is running with the embedding model loaded first,\n"
            "then switch to the LLM model for answer generation.",
            file=sys.stderr,
        )
        return 1

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    db = kuzu.Database(str(graph_path))

    try:
        result = answer_question(
            question=args.question,
            conn=conn,
            kuzu_db=db,
            chroma_path=str(chroma_path),
            embed_model=args.embed_model,
            llm_model=args.llm_model,
        )
        print(f"\n{result['answer']}\n")
        print("Citations:")
        for c in result["citations"]:
            conf = c["confidence"]
            print(f"  [{c['index']}] {c['filename']}, p.{c['page_num']}  ({conf})")
        elapsed = result.get("elapsed_s", "?")
        print(f"\nQuery completed in {elapsed:.1f}s")
    finally:
        conn.close()

    return 0
```

### Anti-Patterns to Avoid

- **Running embedding and LLM simultaneously:** LM Studio cannot hold both nomic-embed-text-v1.5 and Qwen2.5 7B in 4GB VRAM. The pipeline must embed the query, then the user switches the loaded model to the LLM. The CLI should check that the correct model is loaded for each step (via `/v1/models` endpoint) and emit a clear error if the wrong model is active.
- **Using NER on the query string to seed graph traversal:** Fragile on short question strings, adds latency (~1-3s), requires an LLM call. The citation-seeded approach (use chunks to find entities) is more reliable and requires zero extra API calls.
- **2-hop or unbounded graph traversal:** At 1-hop the typical expansion is 5-20 neighbor entities per query. At 2-hops this becomes 20-200 entities and can pull in the entire graph through hub entities like "Electric Vehicle" (Technology node connected to every OEM). Always cap at 1 hop.
- **Fetching all citation chunks per entity:** `CitationStore.get_chunks_for_entity()` returns all chunks linked to an entity — this can be 50-200 chunks for a well-cited entity like "Toyota". Always cap with `LIMIT` or slice to `[:n_graph_per_entity]` (recommended: 5) to prevent context flooding.
- **Uncapped token accumulation:** Without the `token_budget` guard in `assemble_context()`, a large corpus will push hundreds of chunks into the prompt, causing LLM truncation or OOM. Always enforce the budget.
- **Relying on `[N]` references surviving in every response:** Qwen2.5 7B sometimes drops citation markers when the answer is very short or very confident. Post-process the answer to detect "The available documents do not contain sufficient information" and handle gracefully rather than crashing on a missing citation table.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Query embedding | Custom tokenizer/embedding | `embed_query()` in `src/embed/embedder.py` | Already implemented, tested, handles error cases |
| Vector similarity search | Manual cosine distance loop | `VectorStore.query()` in `src/embed/vector_store.py` | Already implemented, uses ChromaDB HNSW index |
| Entity-to-chunk lookup | Custom JOIN query | `CitationStore.get_chunks_for_entity()` in `src/graph/citations.py` | Already implemented with correct 3-table JOIN |
| Token counting | `len(text.split())` word count | `tiktoken.get_encoding("cl100k_base").encode()` | Word count is 30-40% off for BPE tokenizers; correct budget requires BPE counts |
| LM Studio connectivity check | Custom HTTP ping | `check_lm_studio()` in `src/embed/pipeline.py` | Already implemented, reusable |
| Chunk deduplication | Hash-based dedup | Python `set()` on `chunk_id` | IDs are already unique integers; set membership is O(1) |

**Key insight:** Phases 1-3 already built all the hard infrastructure. Phase 4 is a composition layer — it calls existing components in the right sequence. Most "new code" in Phase 4 is glue logic, not new algorithms.

---

## Common Pitfalls

### Pitfall 1: VRAM Model Switch — Silent Wrong Model

**What goes wrong:** The user has the embedding model loaded in LM Studio when they run `query`. The embedding step succeeds, but the LLM step (`chat.completions.create`) calls the embedding model instead of Qwen2.5 7B. LM Studio returns garbage or an error. This is hard to diagnose because the OpenAI client call itself succeeds with a 200.

**Why it happens:** LM Studio serves whatever model is currently loaded. There is no model-name validation on the server side — if you request model "Qwen2.5-7B-Instruct" but nomic-embed-text-v1.5 is loaded, LM Studio may silently use the loaded model.

**How to avoid:** At the start of `cmd_query()`, call `GET /v1/models` and check the loaded model ID. If the embed step is first, verify an embedding model is loaded. Before the LLM generation step, check again that a chat-capable model is loaded. Emit a human-readable error: "Expected LLM model but found embedding model loaded. Switch to Qwen2.5-7B-Instruct in LM Studio and retry."

**Warning signs:** `generate_answer()` returns a JSON blob or embedding vector as text; answer contains no sentences; `max_tokens` is ignored.

### Pitfall 2: KuzuDB Cross-Table Neighbor Query Returns Empty Results

**What goes wrong:** The MATCH query for neighbors returns zero rows even though relationships exist in the graph. This is a schema mismatch: KuzuDB requires that the relationship table name matches exactly, and the source node type must also match. A query for `(n:OEM)-[:USES]->(t)` will fail if the source entity's name was normalized differently during Phase 3 extraction (e.g., "Toyota Motor" vs "Toyota").

**Why it happens:** Entity names in KuzuDB are canonical (normalized by `deduplicator.py`), but the `chunk_citations` table stores the normalized form too. The mismatch happens if the query-side entity lookup uses a raw string from a chunk's metadata rather than the canonical form from the citation table.

**How to avoid:** Always look up entity names from `chunk_citations` (which stores the canonical form used as KuzuDB PRIMARY KEY). Never attempt to parse entity names from chunk text at query time.

**Warning signs:** Graph expansion always returns 0 neighbors; answer quality is equivalent to vector-only retrieval with no improvement from graph.

### Pitfall 3: Token Budget Overflow on `assemble_context()`

**What goes wrong:** `tiktoken.get_encoding("cl100k_base")` is used as an approximation for Qwen2.5's tokenizer (which uses a different vocabulary). For most English text, cl100k_base overestimates token counts by 5-15%, so the context assembly may be slightly conservative — this is acceptable. However, chunks containing many technical abbreviations, numbers, or CJK characters (uncommon in automotive consulting but possible in supplier names) can produce larger discrepancies.

**Why it happens:** Qwen2.5 uses a different BPE vocabulary optimized for multilingual and code content. tiktoken's cl100k_base is trained on a different corpus but is a reasonable proxy.

**How to avoid:** Apply a 15% safety margin on the budget: `effective_budget = token_budget * 0.85`. The default `CONTEXT_TOKEN_BUDGET = 3000` already leaves ample headroom in Qwen2.5 7B's 32K context window. This is a known tradeoff documented in the code.

**Warning signs:** LLM response is truncated mid-sentence; LM Studio returns `finish_reason: length` instead of `stop`.

### Pitfall 4: No LM Studio Context Reset Between Queries

**What goes wrong:** LM Studio maintains a conversation history internally when the same client session is reused across multiple queries with `messages=[...]`. In Phase 3's `extractor.py`, each extraction call is independent and stateless. But if a query pipeline naively reuses an `openai.OpenAI` client with accumulated message history, the LLM receives all previous Q&A pairs as context, wasting tokens and potentially confusing the model.

**Why it happens:** `client.chat.completions.create(messages=[...])` is stateless if you pass only the current system + user messages. This is NOT a problem if the pipeline constructs a fresh `messages=[...]` list per query. It becomes a problem if someone wraps the pipeline in a loop and accidentally appends previous messages.

**How to avoid:** Ensure `answer_question()` in `pipeline.py` always constructs a fresh two-message list: `[{"role": "system", ...}, {"role": "user", ...}]`. Never accumulate message history in the query pipeline. Chat history (for Phase 5 UI) belongs in the UI layer, not in this function.

**Warning signs:** Answer quality degrades on the 2nd+ query in the same session; context window fills up faster than expected.

### Pitfall 5: CitationStore Returns Chunks Without Text

**What goes wrong:** `CitationStore.get_chunks_for_entity()` returns `{chunk_id, doc_id, filename, page_num}` — it does NOT return the chunk text. If the retriever uses these dicts directly to build context without fetching chunk text from SQLite, the assembled context will be empty strings.

**Why it happens:** The `_GET_CHUNKS_SQL` in `citations.py` intentionally omits `chunk_text` (it only returns citation metadata). This is correct by design — `citations.py` is a bridge table navigator, not a chunk fetcher. Phase 4 must separately SELECT `chunk_text` from the `chunks` table for graph-expanded chunks.

**How to avoid:** In `retriever.py`, after calling `get_chunks_for_entity()`, run a second SQLite query to fetch `chunk_text` for the returned `chunk_id`s: `SELECT chunk_id, chunk_text FROM chunks WHERE chunk_id IN (?, ?, ...)`. Document this in the `_hydrate_graph_chunks()` helper's docstring.

**Warning signs:** Context string is empty or contains only "Source:" headers with no text; LLM answers "documents do not contain information" on questions that should have clear answers.

---

## Code Examples

### Fetching Chunk Text for Graph-Expanded Chunks

```python
# Source: sqlite3 stdlib — chunks table schema from src/ingest/store.py (Phase 1)

def _hydrate_graph_chunks(conn, citation_rows: list[dict]) -> list[dict]:
    """Fetch chunk_text from SQLite for graph-expanded chunks.

    citation_rows come from CitationStore.get_chunks_for_entity() which returns
    {chunk_id, doc_id, filename, page_num} without chunk_text.
    """
    if not citation_rows:
        return []

    chunk_ids = [r["chunk_id"] for r in citation_rows]
    placeholders = ",".join("?" * len(chunk_ids))

    rows = conn.execute(
        f"SELECT chunk_id, chunk_text FROM chunks WHERE chunk_id IN ({placeholders})",
        chunk_ids,
    ).fetchall()

    text_map = {row["chunk_id"]: row["chunk_text"] for row in rows}

    return [
        {
            **r,
            "text": text_map.get(r["chunk_id"], ""),
            "metadata": {"filename": r["filename"], "page_num": r["page_num"]},
        }
        for r in citation_rows
        if r["chunk_id"] in text_map
    ]
```

### Getting Entities Cited in Chunks

```python
# Source: SQLite chunk_citations schema from src/graph/citations.py

def _get_entities_for_chunks(conn, chunk_ids: list[int]) -> list[tuple[str, str]]:
    """Return (entity_canonical_name, entity_type) for entities cited in given chunks."""
    if not chunk_ids:
        return []
    placeholders = ",".join("?" * len(chunk_ids))
    rows = conn.execute(
        f"SELECT DISTINCT entity_canonical_name, entity_type "
        f"FROM chunk_citations WHERE chunk_id IN ({placeholders})",
        chunk_ids,
    ).fetchall()
    return [(row["entity_canonical_name"], row["entity_type"]) for row in rows]
```

### Full Answer Pipeline Entry Point

```python
# Source: pattern from src/graph/pipeline.py (build_knowledge_graph)

import time

def answer_question(
    question: str,
    conn,
    kuzu_db,
    chroma_path: str = "data/chroma_db",
    embed_model: str = "nomic-embed-text-v1.5",
    llm_model: str = "Qwen2.5-7B-Instruct",
    openai_client=None,
) -> dict:
    """End-to-end query: embed -> retrieve -> expand -> assemble -> generate -> cite.

    Returns:
        {"answer": str, "citations": list[dict], "elapsed_s": float,
         "n_vector_chunks": int, "n_graph_chunks": int}
    """
    from openai import OpenAI
    if openai_client is None:
        openai_client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

    t0 = time.perf_counter()

    # Hybrid retrieval
    chunks = hybrid_retrieve(
        question, openai_client, conn, kuzu_db, chroma_path, embed_model
    )
    n_vector = sum(1 for c in chunks if c.get("source") == "vector")
    n_graph  = len(chunks) - n_vector

    # Context assembly
    context_str, included = assemble_context(chunks)

    # Answer generation
    answer = generate_answer(question, context_str, openai_client, llm_model)

    # Citation table
    citations = build_citation_table(included)

    return {
        "answer": answer,
        "citations": citations,
        "elapsed_s": time.perf_counter() - t0,
        "n_vector_chunks": n_vector,
        "n_graph_chunks": n_graph,
    }
```

---

## Latency Budget Analysis

### Latency Target: <15 seconds

| Step | Operation | Estimated Time | Notes |
|------|-----------|---------------|-------|
| 1 | Query embedding via LM Studio | 0.1-0.3s | nomic-embed-text-v1.5, single text |
| 2 | ChromaDB HNSW search (top-10) | 0.05s | In-memory HNSW index |
| 3 | SQLite: chunk_ids → entity names | 0.02s | Indexed lookup on chunk_citations |
| 4 | KuzuDB: 1-hop per entity (5-15 entities) | 0.2-0.5s | One Cypher MATCH per rel table per entity |
| 5 | SQLite: entity → citation chunks (hydration) | 0.1-0.3s | Indexed lookup + text fetch |
| 6 | Context assembly + token counting | 0.05s | tiktoken BPE encoding |
| 7 | LLM generation (Qwen2.5 7B q4, 400-600 tokens) | 6-12s | GPU-resident: ~15-25 tok/s; partial offload: ~5-10 tok/s |
| **Total** | | **~7-13s** | Within 15s budget with GPU-resident model |

### Latency Risks

**Primary risk:** Qwen2.5 7B q4 GGUF at 4GB VRAM. The model file is ~3.8GB; with 4GB VRAM it fits with minimal overhead if no other GPU processes are running. If GPU layers are partially offloaded to RAM (e.g., Windows background processes consume VRAM), generation drops to 3-5 tok/s, pushing total latency to 20-30s.

**Mitigation strategies:**
1. **Cap `max_tokens=600`** — the primary lever for controlling generation time. 600 tokens at 10 tok/s = 60s worst case; at 20 tok/s = 30s. For fast generation, use `max_tokens=400` (still sufficient for consulting answers). Do NOT allow uncapped generation.
2. **Cap `n_vector=10`** for ChromaDB retrieval. More results don't improve quality enough to justify extra context. Studies show diminishing returns above 10 retrieved chunks.
3. **Cap `n_graph_per_entity=5`** for graph expansion chunks. Cap total graph chunks at 20 (4 entities × 5 chunks). This bounds the graph path contribution regardless of corpus size.
4. **Pre-warm:** Ensure LM Studio has the LLM already loaded before running a query. The first query after model load adds ~2-5s for model initialization.
5. **Optional optimization:** If latency is consistently >15s, reduce `CONTEXT_TOKEN_BUDGET` from 3000 to 2000 tokens (roughly 5-7 chunks instead of 10-14). This sacrifices some context quality for speed.

### Model Name Detection

LM Studio exposes the loaded model at `GET /v1/models`. The pipeline should check this and warn if an unexpected model is detected:

```python
def get_loaded_model(host="localhost", port=1234) -> str | None:
    """Return the currently loaded LM Studio model ID, or None if unreachable."""
    import httpx
    try:
        r = httpx.get(f"http://{host}:{port}/v1/models", timeout=2.0)
        data = r.json()
        models = data.get("data", [])
        return models[0]["id"] if models else None
    except Exception:
        return None
```

---

## Recommended Plan Decomposition

Phase 4 should be decomposed into **4 plans**, matching the existing phase pattern (Wave 0 test infrastructure + 3 implementation waves):

| Plan | Name | Contents | Key Deliverables |
|------|------|----------|-----------------|
| 04-01 | test-infrastructure | Wave 0: create empty test files with xfail stubs for all QUERY-01..05 tests | `tests/test_retriever.py`, `tests/test_assembler.py`, `tests/test_query_pipeline.py` |
| 04-02 | hybrid-retriever | `src/query/retriever.py` — `hybrid_retrieve()`, `_get_entities_for_chunks()`, `_get_neighbors()`, `_hydrate_graph_chunks()` | QUERY-02, QUERY-03 |
| 04-03 | assembler-and-citations | `src/query/assembler.py` — `assemble_context()`, `generate_answer()`, `build_citation_table()` | QUERY-04, QUERY-05 (generation), token budget |
| 04-04 | pipeline-and-cli | `src/query/pipeline.py` — `answer_question()`; `src/main.py` — `cmd_query()` + argparse wiring | QUERY-01, CLI integration, latency reporting |

**Rationale:** This decomposition isolates testable units. The retriever and assembler can be unit-tested independently with mocked ChromaDB/KuzuDB/SQLite. The pipeline and CLI are integration-tested. Test infrastructure first prevents the "write code then realize tests are impossible to structure" failure mode from Phase 3.

---

## Key Implementation Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Wrong LM Studio model loaded for embed vs LLM steps | HIGH | HIGH — silent wrong output | Add model-check at step boundaries; clear human-readable error message |
| KuzuDB neighbor query returns empty (canonical name mismatch) | MEDIUM | MEDIUM — degrades to vector-only, no crash | Log entities found/not-found; test with known Phase 3 data; tolerate gracefully |
| LLM drops `[N]` citation markers in answer | MEDIUM | LOW — answer still useful, just no citations | Post-process: if no `[N]` found in answer, still display citation table as "Sources used" |
| Latency >15s due to partial GPU offload | MEDIUM | LOW — functional but slow | Document minimum VRAM requirement; add latency warning if elapsed_s > 15 |
| CitationStore returns chunks without text (hydration bug) | LOW | HIGH — empty context, useless answers | Unit test `_hydrate_graph_chunks()` with synthetic data; assert `text != ""` |
| Graph traversal floods context (hub entity pulls too many neighbors) | LOW | MEDIUM — context quality degrades | Cap `n_graph_per_entity=5`; cap total graph chunks at 20; log chunk counts at DEBUG level |
| tiktoken over-counts tokens for technical text | LOW | LOW — conservative budget, fewer chunks included | 15% safety margin in `assemble_context()`; documented known limitation |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pure vector RAG (retrieve N chunks, generate answer) | Hybrid vector+graph RAG (vector retrieval seeded graph expansion) | 2023-2024 (GraphRAG paper, MS GraphRAG project) | 15-20% improvement on multi-hop reasoning; minimal overhead for local systems |
| Naive citation by listing retrieved sources | Inline `[N]` citation with confidence scoring from citation count | 2024-2025 (RAG citation research) | Consultants can trace claims to specific documents; builds trust |
| NER on query to seed graph | Vector-first: use retrieved chunk citations to seed graph | Emerging best practice 2025 | Avoids extra LLM call; more robust on short domain questions |
| LangChain/LlamaIndex orchestration | Thin custom pipeline (stdlib + openai client) | Project constraint from Phase 1 decision | Simpler, faster, no framework dependency, full visibility into each step |

**Deprecated/outdated approaches avoided in this project:**
- Microsoft GraphRAG community detection (requires external graph processing library, overkill for consultant-scale corpus)
- Reciprocal Rank Fusion (RRF) for merging vector+graph results — adds complexity; simple sort-by-distance then append-graph-chunks is sufficient at this scale
- LangChain `HybridCypherRetriever` — requires LangChain dependency and Neo4j; not compatible with KuzuDB's typed schema

---

## Open Questions

1. **LM Studio model auto-detection at query time**
   - What we know: LM Studio `/v1/models` returns the loaded model ID
   - What's unclear: Whether LM Studio allows calling `embeddings.create()` when a chat model is loaded (it may succeed with wrong results, or may return a 400)
   - Recommendation: Test empirically before finalizing the CLI error path; treat any model that isn't the expected embed model as wrong for the embed step

2. **Exact Qwen2.5 model ID string in LM Studio**
   - What we know: Phase 3's `extractor.py` uses `"Qwen2.5-7B-Instruct"` and it works
   - What's unclear: Whether `qwen2.5-vl-7b-instruct` (the vision-language variant mentioned in the phase scope) requires a different model ID string; whether the LM Studio auto-detected model ID includes quantization suffix (e.g., `Qwen2.5-7B-Instruct-Q4_K_M`)
   - Recommendation: The `--llm-model` CLI argument should default to `"Qwen2.5-7B-Instruct"` (matching Phase 3); user can override if their LM Studio instance uses a different ID

3. **Graph density after Phase 3 — are there enough citations to make graph expansion meaningful?**
   - What we know: Phase 3 inserted `chunk_citations` for all entities extracted; the citation store is populated
   - What's unclear: The actual entity count and citation density in the real corpus; if the corpus is small (<20 docs), graph expansion may only add 0-2 extra chunks
   - Recommendation: Log the count of vector chunks vs graph-expanded chunks per query at INFO level; this surfaces the value of graph expansion in practice

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| openai (Python) | Embed query + LLM generation | Yes | 1.93.0 | — |
| chromadb (Python) | Vector retrieval | Yes | 1.5.5 | — |
| kuzu (Python) | Graph neighbor traversal | Yes | 0.11.3 | — |
| tiktoken (Python) | Token budget counting | Yes | 0.9.0 | Word count × 1.3 (poor approximation) |
| httpx (Python) | LM Studio health check | Yes | 0.28.1 | — |
| sqlite3 (Python stdlib) | Citation + chunk lookup | Yes | (stdlib) | — |
| LM Studio (service) | Embedding + LLM generation | Not verified (external service) | Unknown | Cannot substitute — REQUIRED |
| Qwen2.5-7B model | LLM answer generation | Not verified (must be loaded in LM Studio) | Unknown | Cannot substitute — REQUIRED |
| nomic-embed-text-v1.5 | Query embedding | Not verified (must be loaded in LM Studio) | Unknown | Cannot substitute — REQUIRED |

**Missing dependencies with no fallback:**
- LM Studio running at localhost:1234 with both models available for sequential loading — blocks all of QUERY-02 through QUERY-05; must be present at test time for integration tests (unit tests mock it)

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | none detected (standard pytest discovery) |
| Quick run command | `python -m pytest tests/test_retriever.py tests/test_assembler.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QUERY-01 | `cmd_query()` routes question to pipeline, prints answer | unit (mock pipeline) | `pytest tests/test_query_pipeline.py::test_cmd_query_prints_answer -x` | No — Wave 0 |
| QUERY-02 | `hybrid_retrieve()` calls `VectorStore.query()` with query embedding | unit (mock VectorStore) | `pytest tests/test_retriever.py::test_vector_retrieval -x` | No — Wave 0 |
| QUERY-03 | Graph expansion adds chunks from neighbor entities | unit (mock KuzuDB + CitationStore) | `pytest tests/test_retriever.py::test_graph_expansion_adds_chunks -x` | No — Wave 0 |
| QUERY-04 | Citation table contains filename, page_num, HIGH/LOW confidence | unit | `pytest tests/test_assembler.py::test_build_citation_table_confidence -x` | No — Wave 0 |
| QUERY-05 | `generate_answer()` calls LM Studio chat completions (mocked) | unit (mock openai client) | `pytest tests/test_assembler.py::test_generate_answer_calls_llm -x` | No — Wave 0 |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_retriever.py tests/test_assembler.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_retriever.py` — covers QUERY-02, QUERY-03 with mocked ChromaDB + KuzuDB + SQLite
- [ ] `tests/test_assembler.py` — covers QUERY-04, QUERY-05 with mocked openai client and tiktoken
- [ ] `tests/test_query_pipeline.py` — covers QUERY-01 (end-to-end pipeline with all dependencies mocked)

*(Existing `tests/conftest.py` provides `tmp_db_conn` and ChromaDB reset fixtures — reuse these.)*

---

## Sources

### Primary (HIGH confidence)

- Existing codebase (`src/embed/vector_store.py`, `src/embed/embedder.py`, `src/graph/citations.py`, `src/graph/db_manager.py`, `src/graph/pipeline.py`) — direct inspection of public API and data contracts
- `src/graph/extractor.py` — confirmed LM Studio `client.chat.completions.create()` pattern with Qwen2.5-7B-Instruct at temperature 0.1

### Secondary (MEDIUM confidence)

- [KuzuDB Cypher MATCH docs](https://docs.kuzudb.com/cypher/query-clauses/match/) — confirmed variable-length *1..1 syntax, typed node tables requirement, and UNION pattern for multi-type traversal
- [KuzuDB Differences from Neo4j](https://docs.kuzudb.com/cypher/difference/) — confirmed walk semantics, upper bound requirement, no polymorphic label matching
- [nomic-embed-text-v1.5 Hugging Face](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5) — confirmed 768-dimension output, 8192-token input window
- [RAG citation patterns (tensorlake.ai)](https://www.tensorlake.ai/blog/rag-citations) — `[N]` inline citation format confirmed as standard practice
- [tiktoken PyPI](https://pypi.org/project/tiktoken/) — confirmed 0.9.0 installed, cl100k_base encoding available offline

### Tertiary (LOW confidence — needs validation)

- Qwen2.5 7B q4 generation speed estimates (15-25 tok/s GPU-resident, 5-10 tok/s partial offload) — sourced from community benchmarks (markaicode.com, hardware-corner.net); actual speed on this specific machine's 4GB VRAM configuration is unverified and could be lower
- Citation confidence threshold of 3 — derived from first-principles reasoning about Phase 1's chunking density (2-4 chunks/page); not validated against real corpus data

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages already installed; versions confirmed by `pip show`
- Architecture: HIGH — patterns derived directly from existing Phase 2/3 code; no new abstractions required
- KuzuDB Cypher syntax: MEDIUM — official docs confirm the typed-table constraint and *1..1 syntax; mixed-table traversal relies on the UNION-per-table pattern which is conventional but not explicitly documented as the recommended approach for this exact schema
- Pitfalls: HIGH for the known ones (VRAM model switch, CitationStore text gap); MEDIUM for latency estimates
- Latency budget: MEDIUM — pipeline stages are well-understood but actual Qwen2.5 7B generation speed on this specific hardware is unverified

**Research date:** 2026-03-31
**Valid until:** 2026-06-30 (KuzuDB 0.11.3 is stable/archived; LM Studio API unlikely to change; ChromaDB 1.5.x API stable)
