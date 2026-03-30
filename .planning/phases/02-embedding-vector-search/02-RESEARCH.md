# Phase 2: Embedding & Vector Search - Research

**Researched:** 2026-03-28
**Domain:** Embedding generation (LM Studio OpenAI API), vector storage (ChromaDB), incremental indexing (SQLite embedding_flag)
**Confidence:** HIGH — ChromaDB 1.5.5 verified from pip dry-run; openai 1.93.0 verified installed; LM Studio API patterns confirmed from official docs; SQLite integration patterns confirmed from Phase 1 source code

---

## Summary

Phase 2 wires together three components: (1) LM Studio's OpenAI-compatible embeddings endpoint, (2) ChromaDB for persistent vector storage, and (3) the existing SQLite chunk store from Phase 1. The architecture is a pull-embed-push loop: query SQLite for chunks where `embedding_flag=0`, call LM Studio in batches to generate embeddings, upsert embeddings into ChromaDB with metadata, then mark chunks `embedding_flag=1` in SQLite. The retrieval path is: embed a query string via LM Studio, call `collection.query(query_embeddings=..., n_results=10)`, return ranked chunk IDs with distances.

The critical constraint is VRAM: nomic-embed-text-v1.5 in GGUF format requires roughly 260MB of VRAM for the model weights (float16; less with quantization). This is well within the 3.5GB safety margin. However, the embedding model and the LLM (Qwen2.5 7B q4_k_m, ~3.8GB) cannot run concurrently — LM Studio must unload one before loading the other. Phase 2 only uses the embedding model, so there is no VRAM conflict in this phase. The Phase 4 plan must enforce sequential model use.

ChromaDB 1.5.5 is pip-installable and confirmed available on this machine. It will be installed as a new dependency. The `openai` package (1.93.0) is already installed and is the correct client for LM Studio's OpenAI-compatible API. Batch sizes of 8–16 chunks per embedding call are safe for LM Studio stability; the Phase 1 schema already supports incremental indexing via `embedding_flag`.

**Primary recommendation:** Use `chromadb.PersistentClient(path="data/chroma_db")` with `embedding_function=None` (pre-computed embeddings). Use `openai.OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")` for embedding calls. Embed in batches of 8 chunks. Store doc_id, filename, page_num, chunk_index, token_count as ChromaDB metadata. Use cosine distance for the collection (`configuration={"hnsw": {"space": "cosine"}}`). Check `collection.count()` before querying to guard against `NotEnoughElementsException`.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EMBED-01 | System generates embeddings for each chunk using a local model served via LM Studio OpenAI-compatible API | `client.embeddings.create(input=[...], model="nomic-embed-text-v1.5")` confirmed from LM Studio official docs; openai 1.93.0 already installed |
| EMBED-02 | System stores chunk embeddings in ChromaDB for semantic retrieval | `chromadb.PersistentClient` + `collection.add(ids, embeddings, documents, metadatas)` confirmed for ChromaDB 1.5.5; pip-installable, no Docker required |
| EMBED-03 | System stores raw chunk text and document metadata (filename, page/slide number) alongside vectors | ChromaDB `metadatas` parameter stores arbitrary dicts per embedding; `documents` parameter stores raw text; both queryable at retrieval time |
</phase_requirements>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **chromadb** | 1.5.5 | Persistent vector store | pip-installable embedded DB; no external process; cosine/L2/IP distance; HNSW index; proven for ≤1M vectors |
| **openai** | 1.93.0 (installed) | LM Studio API client | Already installed; standard client for OpenAI-compatible APIs; `client.embeddings.create()` works against LM Studio unchanged |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **sqlite3** | stdlib | Query chunks WHERE embedding_flag=0, mark flag=1 | Already used in Phase 1 ChunkStore; no new dependency |
| **tqdm** | 4.67.1 (installed) | Progress bar during batch embedding | Wrap the batch loop for 500+ document corpora |
| **unittest.mock** | stdlib | Mock LM Studio API in unit tests | Never call real LM Studio during CI/automated tests |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| chromadb PersistentClient | FAISS | FAISS requires manual metadata management (no built-in metadata storage), harder to query; ChromaDB handles both vectors + metadata |
| openai client against LM Studio | lmstudio-python SDK | lmstudio-python is LM Studio-specific; openai client works against any OpenAI-compatible endpoint including future model changes |
| Pre-computed embeddings (embedding_function=None) | ChromaDB built-in embedding functions | Built-in functions download models from HuggingFace — blocked by corporate firewall; LM Studio must be the embedding source |

### Installation

```bash
pip install "chromadb>=1.5.5"
```

`openai` is already installed (1.93.0). No other new dependencies required.

**Version verification (confirmed 2026-03-28):**
- chromadb 1.5.5 — available from pip cache
- openai 1.93.0 — already installed, verified with `python -c "import openai; print(openai.__version__)"`

---

## Architecture Patterns

### Recommended Project Structure

```
src/
├── embed/
│   ├── __init__.py
│   ├── embedder.py       # LM Studio client, embed_chunks(), embed_query()
│   └── vector_store.py   # ChromaDB wrapper, VectorStore class
├── ingest/               # Phase 1 (unchanged)
│   ├── store.py          # ChunkStore (get_chunks_for_embedding, mark_chunks_embedded)
│   └── ...
data/
└── chroma_db/            # ChromaDB persistent storage (git-ignored)
tests/
└── test_embedding.py     # Unit tests (mocked LM Studio + EphemeralClient)
```

### Pattern 1: Incremental Embedding Loop

**What:** Pull unembedded chunks from SQLite, embed in batches, push to ChromaDB, mark done.
**When to use:** Every time `embed_all_chunks()` is called — idempotent by design.

```python
# Source: LM Studio official docs + Phase 1 ChunkStore API
from openai import OpenAI
import chromadb
import sqlite3

def embed_all_chunks(db_path: str, chroma_path: str, batch_size: int = 8):
    client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
    chroma = chromadb.PersistentClient(path=chroma_path)
    collection = chroma.get_or_create_collection(
        name="chunks",
        configuration={"hnsw": {"space": "cosine"}},
    )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    store = ChunkStore(conn)

    while True:
        batch = store.get_chunks_for_embedding(batch_size=batch_size)
        if not batch:
            break

        texts = [row["chunk_text"] for row in batch]
        chunk_ids = [row["chunk_id"] for row in batch]

        # Embed batch
        response = client.embeddings.create(
            input=texts,
            model="nomic-embed-text-v1.5",
        )
        vectors = [item.embedding for item in response.data]

        # Fetch metadata for batch
        # (requires get_chunk_metadata() — returns doc_id, filename, page_num, chunk_index, token_count)
        metadatas = [get_chunk_metadata(conn, cid) for cid in chunk_ids]

        # Upsert into ChromaDB
        collection.add(
            ids=[str(cid) for cid in chunk_ids],
            embeddings=vectors,
            documents=texts,
            metadatas=metadatas,
        )

        # Mark embedded in SQLite
        store.mark_chunks_embedded(chunk_ids)

    conn.close()
```

**Note on `get_or_create_collection` idempotency:** Starting with ChromaDB v1.1.13, embedding functions (and configuration) are persisted server-side. The cosine configuration set on first call is preserved on subsequent `get_or_create_collection` calls — do not pass `configuration` on re-runs or it will raise a conflict if different.

**Safe pattern:** Pass `configuration` only on creation. Use `get_or_create_collection` with a try/except or check `collection.metadata` to confirm cosine was set.

### Pattern 2: Semantic Query

**What:** Embed a query string, search ChromaDB for the top-N most similar chunks.
**When to use:** Phase 4 query engine; also used directly in Phase 2 integration test.

```python
# Source: ChromaDB official docs (docs.trychroma.com/docs/querying-collections/query-and-get)
def query_similar(query_text: str, n_results: int = 10) -> list[dict]:
    client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
    chroma = chromadb.PersistentClient(path=chroma_path)
    collection = chroma.get_collection("chunks")

    # Embed the query
    response = client.embeddings.create(input=[query_text], model="nomic-embed-text-v1.5")
    query_vector = response.data[0].embedding

    # Guard: ChromaDB raises NotEnoughElementsException if n_results > collection.count()
    actual_n = min(n_results, collection.count())
    if actual_n == 0:
        return []

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=actual_n,
        include=["documents", "metadatas", "distances"],
    )

    # results["ids"][0], results["documents"][0], results["metadatas"][0], results["distances"][0]
    # are all parallel lists — index [0] is the single query
    return [
        {
            "chunk_id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        }
        for i in range(len(results["ids"][0]))
    ]
```

### Pattern 3: LM Studio Health Check

**What:** Verify LM Studio server is running and embedding model is loaded before starting a batch job.
**When to use:** At the start of `embed_all_chunks()` and `query_similar()`.

```python
# Source: LM Studio REST API docs (lmstudio.ai/docs/developer/rest/endpoints)
import httpx

def check_lm_studio(host: str = "localhost", port: int = 1234) -> bool:
    try:
        r = httpx.get(f"http://{host}:{port}/v1/models", timeout=2.0)
        return r.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False
```

`httpx` is already installed (it is a dependency of `openai`). No new import needed.

### Pattern 4: ChromaDB Collection ID Format

**What:** ChromaDB IDs must be strings. Use `str(chunk_id)` — the integer primary key from SQLite.
**Why:** Keeps the ID space stable, unique, and directly traceable back to SQLite without encoding.

### Anti-Patterns to Avoid

- **Using ChromaDB's built-in embedding functions:** These download models from HuggingFace on first use — the corporate firewall will block them. Always use `embedding_function=None` and supply pre-computed embeddings.
- **Setting `n_results` without checking `collection.count()`:** ChromaDB raises `NotEnoughElementsException` if `n_results > number of items`. Guard with `min(n_results, collection.count())`.
- **Calling `collection.add()` with duplicate IDs:** ChromaDB silently ignores duplicates on `add()`. If a chunk is re-processed (e.g., after a crash mid-batch), use `collection.upsert()` instead of `add()` to ensure idempotency.
- **Passing `configuration` on every `get_or_create_collection` call:** After creation, ChromaDB persists the configuration. Re-passing it with `get_or_create_collection` may raise an error if the values differ from what was stored. Only pass `configuration` on first creation.
- **L2 (default) distance for normalized embeddings:** ChromaDB defaults to L2. nomic-embed-text produces normalized embeddings where cosine similarity is the correct metric. Set `configuration={"hnsw": {"space": "cosine"}}` at collection creation.
- **Embedding empty or whitespace-only chunk text:** LM Studio will return a valid (but meaningless) embedding for empty strings. Filter `chunk_text.strip()` before embedding.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Vector similarity search | Custom cosine similarity + ranking | `collection.query()` | HNSW index is O(log n) vs O(n) linear scan; handles batched queries, metadata filtering, distance computation |
| Metadata storage alongside vectors | Separate SQL table joined at query time | ChromaDB `metadatas` parameter | Built-in, co-located with vectors, returned in the same query response |
| Retry/backoff for LM Studio timeouts | Custom retry loop with sleep | `tenacity` (already installed as chromadb dep) or `openai` built-in retry | openai client has built-in retry with exponential backoff via `max_retries` parameter |
| In-memory vector store for tests | Fake list-based cosine search | `chromadb.EphemeralClient()` | Real ChromaDB behavior in tests without disk I/O; automatically garbage-collected |

**Key insight:** The combination of ChromaDB's HNSW index + metadata storage eliminates the need to join back to SQLite at query time. Store enough metadata (filename, page_num, chunk_index) in ChromaDB to fully construct citations without a second database lookup.

---

## ChromaDB API Reference (verified for 1.5.5)

### Client Creation

```python
# Persistent (production)
import chromadb
client = chromadb.PersistentClient(path="data/chroma_db")

# Ephemeral (tests only)
client = chromadb.EphemeralClient()
```

### Collection Management

```python
# Create with cosine distance — only on first run
collection = client.get_or_create_collection(
    name="chunks",
    configuration={"hnsw": {"space": "cosine"}},
)

# Get existing collection (subsequent runs)
collection = client.get_collection("chunks")

# Check size before querying
count = collection.count()  # returns int
```

### Adding Embeddings

```python
collection.add(
    ids=["1", "2", "3"],               # str — chunk_id from SQLite
    embeddings=[[0.1, ...], ...],      # list[list[float]] — from LM Studio
    documents=["text1", "text2", ...], # list[str] — raw chunk text
    metadatas=[
        {"doc_id": 1, "filename": "report.pdf", "page_num": 3,
         "chunk_index": 0, "token_count": 512},
        ...
    ],
)

# For idempotent re-runs (after crash recovery):
collection.upsert(ids=..., embeddings=..., documents=..., metadatas=...)
```

### Querying

```python
results = collection.query(
    query_embeddings=[[0.1, ...]],   # list[list[float]] — one vector per query
    n_results=10,
    include=["documents", "metadatas", "distances"],
    # Optional: where={"filename": {"$eq": "report.pdf"}}  — metadata filter
)
# results["ids"][0]        — list[str], chunk_ids ordered by similarity
# results["documents"][0]  — list[str], raw texts
# results["metadatas"][0]  — list[dict]
# results["distances"][0]  — list[float], cosine distance (0=identical, 2=opposite)
```

### Metadata Filter Operators (for Phase 4)

```python
# Equality filter
where={"filename": {"$eq": "report.pdf"}}
# Multiple conditions (AND)
where={"$and": [{"doc_id": {"$eq": 5}}, {"page_num": {"$gte": 3}}]}
```

---

## LM Studio Embedding API Reference (verified)

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio",       # any non-empty string; LM Studio ignores it
    timeout=30.0,              # seconds; embedding should complete well under 10s/batch
    max_retries=2,             # built-in exponential backoff
)

# Single or batch embedding
response = client.embeddings.create(
    input=["text1", "text2", ...],   # list[str]; up to ~100 texts per call
    model="nomic-embed-text-v1.5",   # exact model identifier as shown in LM Studio UI
)

# Access vectors
vectors: list[list[float]] = [item.embedding for item in response.data]
# nomic-embed-text-v1.5 produces 768-dimensional vectors
```

**Model name note:** The model name string must exactly match what LM Studio shows in its "Loaded Model" panel. Common variants: `"nomic-embed-text-v1.5"`, `"nomic-ai/nomic-embed-text-v1.5"`. If uncertain, call `GET /v1/models` to list currently loaded models and use the `id` field from the response.

**Batch size recommendation:** 8 chunks per call. nomic-embed-text is small (~260MB VRAM), but LM Studio's inference server is single-threaded. Batches of 8 keep per-call latency under ~500ms and avoid timeout failures on long texts. Do not exceed 32 without benchmarking.

---

## Metadata Schema per Embedding

Every embedding stored in ChromaDB must include the following fields to support Phase 4 citation generation without a SQLite round-trip:

| Field | Type | Source | Purpose |
|-------|------|--------|---------|
| `doc_id` | int | SQLite `chunks.doc_id` | Link back to document record |
| `filename` | str | SQLite `documents.filename` | Display citation |
| `page_num` | int | SQLite `chunks.page_num` | Page/slide citation |
| `chunk_index` | int | SQLite `chunks.chunk_index` | Order within page |
| `token_count` | int | SQLite `chunks.token_count` | Context window planning in Phase 4 |

**Important:** ChromaDB metadata values must be `str`, `int`, `float`, or `bool` — no nested dicts or lists. Keep all fields flat.

---

## SQLite Integration Points

Phase 1 already provides the two methods needed for Phase 2:

```python
# From src/ingest/store.py (verified)

# Pull pending chunks (batch_size controls VRAM pressure)
batch: list[sqlite3.Row] = store.get_chunks_for_embedding(batch_size=8)
# Each row: chunk_id (int), chunk_text (str)

# Mark batch as done (call AFTER successful ChromaDB upsert)
store.mark_chunks_embedded(chunk_ids=[1, 2, 3, ...])
```

The `get_chunks_for_embedding` method needs extending (or a new method) to also return the metadata fields needed for ChromaDB (doc_id, filename, page_num, chunk_index, token_count). Current implementation only returns `chunk_id` and `chunk_text`. Phase 2 must add a `get_chunks_with_metadata_for_embedding()` method or extend the existing one.

**Proposed query addition to ChunkStore:**

```python
def get_chunks_with_metadata_for_embedding(self, batch_size: int = 8) -> list[sqlite3.Row]:
    return self.conn.execute(
        """SELECT c.chunk_id, c.chunk_text, c.doc_id, c.page_num, c.chunk_index,
                  c.token_count, d.filename
           FROM chunks c
           JOIN documents d ON c.doc_id = d.doc_id
           WHERE c.embedding_flag = 0
           LIMIT ?""",
        (batch_size,),
    ).fetchall()
```

**Incremental indexing guarantee:** Because `mark_chunks_embedded()` is called AFTER a successful ChromaDB `upsert()`, a crash mid-batch leaves `embedding_flag=0` for that batch — the loop retries it on the next run. Use `upsert()` not `add()` in ChromaDB to make re-runs idempotent.

---

## VRAM Budget Analysis

| Model | VRAM (float16 GGUF) | Notes |
|-------|---------------------|-------|
| nomic-embed-text-v1.5 | ~260MB | Verified from HuggingFace model card; int4 quantized is ~65MB |
| Safety margin target | <3.5GB | 50% of 4GB ceiling per success criteria |
| Headroom | ~3.24GB | Well within budget — embedding only, no LLM running |
| Qwen2.5 7B q4_k_m | ~3.8GB | NOT running in Phase 2; important for Phase 4 serialization |

**Conclusion (HIGH confidence):** VRAM is not a constraint in Phase 2. The embedding model leaves 3.24GB of headroom. The 3.5GB ceiling only becomes relevant in Phase 4 when the LLM must be loaded and the embedding model must first be unloaded.

---

## Common Pitfalls

### Pitfall 1: ChromaDB Default L2 Distance

**What goes wrong:** Collection created without specifying distance metric uses L2 by default. nomic-embed-text produces normalized unit vectors where cosine similarity is the semantically correct metric. L2 on normalized vectors correlates with cosine, but the distance values differ — this confuses Phase 4 confidence scoring.
**Why it happens:** ChromaDB documentation prominently shows `create_collection(name="...")` without distance config; readers copy this.
**How to avoid:** Always pass `configuration={"hnsw": {"space": "cosine"}}` on collection creation.
**Warning signs:** `distances` values in results are in range [0, 4] instead of [0, 2].

### Pitfall 2: NotEnoughElementsException on Small Collections

**What goes wrong:** `collection.query(n_results=10)` raises `NotEnoughElementsException` when fewer than 10 chunks are indexed.
**Why it happens:** ChromaDB does not auto-clip n_results to collection size.
**How to avoid:** Guard with `actual_n = min(n_results, collection.count())` before every query call.
**Warning signs:** Tests with small fixture datasets crash; integration tests during early indexing fail.

### Pitfall 3: Duplicate ID Silent Drop on Add

**What goes wrong:** If `collection.add()` is called with an ID that already exists, ChromaDB silently ignores it without raising an error. After a crash mid-batch, re-running with `add()` appears to succeed but new embeddings are not written.
**Why it happens:** ChromaDB's `add()` treats duplicate IDs as no-ops for performance.
**How to avoid:** Use `collection.upsert()` for all writes in Phase 2.
**Warning signs:** Collection count does not increase on re-run even though new chunks exist.

### Pitfall 4: Model Name Mismatch

**What goes wrong:** LM Studio returns a 404 or model-not-found error when the `model` parameter does not exactly match the loaded model's identifier.
**Why it happens:** LM Studio model IDs vary by how the model was downloaded (e.g., `"nomic-embed-text-v1.5"` vs `"nomic-ai/nomic-embed-text-v1.5"` vs `"text-embedding-nomic-embed-text-v1.5"`).
**How to avoid:** Call `GET http://localhost:1234/v1/models` at startup and use the `id` field of the first (or only) loaded embedding model.
**Warning signs:** HTTP 404 or JSON error response from `client.embeddings.create()`.

### Pitfall 5: ChromaDB Built-in Embedding Function Downloads on First Use

**What goes wrong:** If `embedding_function` is not explicitly set to `None`, ChromaDB defaults to downloading `all-MiniLM-L6-v2` from HuggingFace on first collection access. The corporate firewall blocks this download, causing a silent hang or SSL error.
**Why it happens:** ChromaDB's default `embedding_function` parameter is `DefaultEmbeddingFunction()` which downloads models.
**How to avoid:** Always pass `embedding_function=None` explicitly when creating/getting collections.
**Warning signs:** First `get_or_create_collection()` hangs indefinitely or raises a network error.

### Pitfall 6: Embedding Empty Chunks

**What goes wrong:** If a chunk's text is empty or whitespace-only (possible with sparse slides), LM Studio embeds it and returns a valid vector. This populates ChromaDB with useless noise that appears in query results.
**Why it happens:** `get_chunks_with_metadata_for_embedding()` doesn't filter on text content.
**How to avoid:** Filter `if not row["chunk_text"].strip(): continue` before adding to the batch. Phase 1 pipeline already skips empty pages, but defensive filtering in Phase 2 is still warranted.
**Warning signs:** Query results include clearly irrelevant blank-content chunks near the top.

### Pitfall 7: Configuration Conflict on Re-run

**What goes wrong:** Calling `get_or_create_collection(name="chunks", configuration={"hnsw": {"space": "cosine"}})` on subsequent runs raises an error if ChromaDB detects the persisted configuration differs from the passed value (or if the API version changed behavior).
**Why it happens:** ChromaDB 1.x persists collection configuration server-side; re-passing it is redundant and in some versions raises a conflict error.
**How to avoid:** Check `collection.count() > 0` and use `client.get_collection("chunks")` on re-runs instead of `get_or_create_collection`. Or use a try/except pattern: try `get_collection`, on `ValueError` create with configuration.
**Warning signs:** `ValueError: Collection already exists` or configuration mismatch errors on second run.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `chromadb.Client()` | `chromadb.PersistentClient(path=...)` | ChromaDB 0.4+ | Old `Client()` is deprecated; `PersistentClient` is the current persistent client |
| `openai.Embedding.create()` (v0) | `client.embeddings.create()` (v1+) | openai-python 1.0.0 (Nov 2023) | Old class-level API removed; all calls go through a client instance |
| `collection.metadata={"hnsw:space":"cosine"}` | `configuration={"hnsw": {"space": "cosine"}}` | ChromaDB 1.x | Both syntaxes appear in docs/web; `configuration` is the current canonical form |

**Deprecated/outdated:**
- `chromadb.Client()`: Removed in ChromaDB 0.4+; use `EphemeralClient()`, `PersistentClient()`, or `HttpClient()`.
- `openai.Embedding.create()` (old v0 API): Removed in openai-python 1.0; current installed version is 1.93.0.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Runtime | Yes | 3.13.5 | — |
| openai (pip) | LM Studio API client | Yes (installed) | 1.93.0 | — |
| chromadb (pip) | Vector store | Not yet installed | 1.5.5 (confirmed from pip) | — |
| LM Studio server | Embedding generation | Assumed running | Unknown — verify at runtime | Use mock for unit tests; integration tests require it |
| nomic-embed-text-v1.5 | EMBED-01 | Assumed loaded in LM Studio | Unknown — verify via /v1/models | Cannot embed without it; block noted in STATE.md |
| pytest | Testing | Yes (installed) | 9.0.2 | — |
| sqlite3 | Chunk retrieval | Yes (stdlib) | bundled | — |
| httpx | Health check for LM Studio | Yes (installed, transitive) | via openai dep | — |

**Missing dependencies with no fallback:**
- LM Studio must be running with nomic-embed-text-v1.5 loaded for integration tests and production use. Unit tests must mock this.

**Missing dependencies with fallback:**
- chromadb not yet installed — install step is Wave 0 of Phase 2.

---

## Open Questions

1. **Model name exact string in LM Studio**
   - What we know: Common variants are `"nomic-embed-text-v1.5"` or `"nomic-ai/nomic-embed-text-v1.5"`.
   - What's unclear: Which exact string LM Studio shows for this installation.
   - Recommendation: Plan must include a startup check that calls `GET /v1/models` and uses the returned `id` field, or documents the exact model ID for hard-coding.

2. **get_or_create_collection configuration idempotency in ChromaDB 1.5.5**
   - What we know: ChromaDB 1.x persists configuration server-side; re-passing may conflict.
   - What's unclear: Whether `get_or_create_collection` in 1.5.5 silently accepts repeated same-value configuration or raises an error.
   - Recommendation: Use try/except — `get_collection` first, fall back to `create_collection` with configuration on first run. Document this in the embedder module.

3. **Embedding dimension for nomic-embed-text-v1.5**
   - What we know: nomic-embed-text produces 768-dimensional vectors (confirmed from HuggingFace model card).
   - What's unclear: LM Studio may serve a GGUF variant with different output dimensions depending on quantization.
   - Recommendation: Log `len(response.data[0].embedding)` on first call and assert it is 768. Fail fast if different.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `pytest.ini` or `pyproject.toml` (uses existing config from Phase 1) |
| Quick run command | `pytest tests/test_embedding.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### What Can Be Unit Tested (Mocked LM Studio + EphemeralClient)

All Phase 2 logic can be unit tested without LM Studio running and without disk I/O by:
1. Mocking `openai.OpenAI.embeddings.create` using `unittest.mock.patch`
2. Using `chromadb.EphemeralClient()` instead of `PersistentClient`
3. Using a `tmp_path` SQLite database pre-populated with fixture chunks

### What Requires Integration Testing (Real LM Studio)

| Test | Reason |
|------|--------|
| Actual embedding vector dimensions | Must verify nomic-embed-text produces 768-dim vectors on this LM Studio installation |
| Embedding quality / retrieval precision | Semantic similarity requires real vectors |
| LM Studio timeout/retry behavior | Cannot simulate real server behavior with mocks |
| VRAM footprint measurement | Requires hardware interaction |

Integration tests should be decorated with `@pytest.mark.integration` and skipped in CI via `-m "not integration"`.

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EMBED-01 | `embed_chunks()` calls LM Studio API and returns vectors | unit (mocked) | `pytest tests/test_embedding.py::test_embed_chunks_calls_api -x` | No — Wave 0 |
| EMBED-01 | `embed_chunks()` handles LM Studio not running (raises clear error) | unit (mocked) | `pytest tests/test_embedding.py::test_embed_chunks_server_unavailable -x` | No — Wave 0 |
| EMBED-01 | `embed_chunks()` handles empty input gracefully | unit | `pytest tests/test_embedding.py::test_embed_chunks_empty_input -x` | No — Wave 0 |
| EMBED-02 | `VectorStore.upsert()` stores embeddings in ChromaDB | unit (EphemeralClient) | `pytest tests/test_embedding.py::test_vector_store_upsert -x` | No — Wave 0 |
| EMBED-02 | `VectorStore.query()` returns top-N results ordered by distance | unit (EphemeralClient) | `pytest tests/test_embedding.py::test_vector_store_query_returns_n_results -x` | No — Wave 0 |
| EMBED-02 | `VectorStore.query()` guards against n_results > collection.count() | unit (EphemeralClient) | `pytest tests/test_embedding.py::test_vector_store_query_small_collection -x` | No — Wave 0 |
| EMBED-03 | Stored metadata contains filename, page_num, chunk_index, token_count | unit (EphemeralClient) | `pytest tests/test_embedding.py::test_vector_store_metadata_fields -x` | No — Wave 0 |
| EMBED-03 | Metadata fields are retrievable via `include=["metadatas"]` in query | unit (EphemeralClient) | `pytest tests/test_embedding.py::test_vector_store_metadata_retrievable -x` | No — Wave 0 |
| All | Full embed loop: SQLite chunks → embeddings → ChromaDB → flag=1 | unit (mocked + EphemeralClient) | `pytest tests/test_embedding.py::test_embed_all_chunks_loop -x` | No — Wave 0 |
| All | Incremental: re-running embed loop skips already-embedded chunks | unit (mocked + EphemeralClient) | `pytest tests/test_embedding.py::test_embed_loop_incremental -x` | No — Wave 0 |
| Performance | Top-10 retrieval completes in under 50ms | unit (EphemeralClient, timed) | `pytest tests/test_embedding.py::test_query_latency_under_50ms -x` | No — Wave 0 |
| EMBED-01 | Real embedding vectors are 768-dimensional | integration (LM Studio required) | `pytest tests/test_embedding.py -m integration -x` | No — Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_embedding.py -x -q -m "not integration"`
- **Per wave merge:** `pytest tests/ -x -q -m "not integration"`
- **Phase gate:** Full suite green (including integration with LM Studio running) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_embedding.py` — all unit tests listed above (stubs with `xfail(strict=False)`)
- [ ] `src/embed/__init__.py` — empty module marker
- [ ] `src/embed/embedder.py` — stub with `raise NotImplementedError`
- [ ] `src/embed/vector_store.py` — stub with `raise NotImplementedError`
- [ ] `data/chroma_db/` directory — create with `.gitkeep`; add `data/chroma_db/` to `.gitignore`

### Mock Pattern for Unit Tests

```python
# tests/test_embedding.py — illustrative pattern
import pytest
from unittest.mock import MagicMock, patch
import chromadb

@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client that returns deterministic 768-dim embeddings."""
    mock_response = MagicMock()
    mock_response.data = [
        MagicMock(embedding=[0.1] * 768),
        MagicMock(embedding=[0.2] * 768),
    ]
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = mock_response
    return mock_client

@pytest.fixture
def ephemeral_chroma():
    """Fresh in-memory ChromaDB for each test."""
    client = chromadb.EphemeralClient()
    collection = client.get_or_create_collection(
        name="chunks",
        configuration={"hnsw": {"space": "cosine"}},
    )
    return client, collection
```

---

## Sources

### Primary (HIGH confidence)
- LM Studio official docs (lmstudio.ai/docs/developer/openai-compat/embeddings) — LM Studio embedding API, Python client pattern, model name convention
- `pip install chromadb --dry-run` (2026-03-28) — chromadb 1.5.5 confirmed available
- `python -c "import openai; print(openai.__version__)"` (2026-03-28) — openai 1.93.0 confirmed installed
- `src/ingest/store.py` Phase 1 source (2026-03-28) — `get_chunks_for_embedding()`, `mark_chunks_embedded()` confirmed API
- `src/db/schema.sql` Phase 1 source (2026-03-28) — `embedding_flag` column confirmed: `0=pending, 1=embedded, -1=skip`

### Secondary (MEDIUM confidence)
- ChromaDB official docs (docs.trychroma.com/docs/collections) — `PersistentClient`, `EphemeralClient`, `collection.add()`, `collection.query()`, `collection.upsert()` API patterns (WebSearch verified against multiple sources)
- ChromaDB official docs (docs.trychroma.com/docs/collections/configure) — HNSW configuration, cosine distance metric
- LM Studio REST API docs (lmstudio.ai/docs/developer/rest/endpoints) — `/v1/models` health check endpoint
- HuggingFace model card (huggingface.co/nomic-ai/nomic-embed-text-v1.5) — VRAM footprint ~260MB (float16), 768-dimensional output

### Tertiary (LOW confidence)
- WebSearch community sources — batch size 8–16 recommendation for LM Studio stability (not officially documented; based on community reports)
- WebSearch — "duplicate ID silent drop on add" behavior in ChromaDB (GitHub issues; not in official docs; verify in implementation)

---

## Project Constraints (from CLAUDE.md)

No `CLAUDE.md` exists in this project. Constraints are sourced from `PROJECT.md` and `STATE.md`.

| Constraint | Source | Impact on Phase 2 |
|------------|--------|-------------------|
| pip install only (no conda, Docker, system packages) | PROJECT.md | chromadb must install cleanly via pip — confirmed (1.5.5 available) |
| No cloud or external API calls | PROJECT.md | LM Studio is local; openai client pointed to localhost:1234 |
| 4GB VRAM ceiling | PROJECT.md | nomic-embed-text ~260MB VRAM — no risk in Phase 2; Phase 4 must serialize |
| LM Studio as model server | STATE.md (locked) | Cannot use HuggingFace Inference, Ollama, or any other model server |
| ChromaDB for vectors | STATE.md (locked) | Cannot use FAISS, Qdrant, Weaviate, or any other vector store |
| Sequential model execution (embedding + LLM cannot overlap) | STATE.md | Phase 2 uses embedding model only — no conflict; Phase 4 must enforce |
| xfail(strict=False) stubs for TDD wave-0 | STATE.md (locked) | Wave 0 test stubs must use `@pytest.mark.xfail(strict=False)` pattern |

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — packages verified from pip dry-run and installed versions
- Architecture patterns: HIGH — confirmed against LM Studio official docs and ChromaDB official docs
- SQLite integration: HIGH — confirmed against Phase 1 source code (store.py)
- VRAM analysis: HIGH (model size) / MEDIUM (LM Studio overhead) — model size from HuggingFace card; LM Studio overhead not officially documented
- Pitfalls: MEDIUM — most confirmed from official docs or GitHub issues; batch size recommendations are community-sourced

**Research date:** 2026-03-28
**Valid until:** 2026-04-28 (chromadb and openai are fast-moving; re-verify API signatures if more than 30 days elapse)
