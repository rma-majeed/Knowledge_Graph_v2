---
phase: 02-embedding-vector-search
plan: 04
type: execute
wave: 3
depends_on:
  - "02-02"
  - "02-03"
files_modified:
  - src/ingest/store.py
  - src/embed/pipeline.py
  - src/main.py
autonomous: true
requirements:
  - EMBED-01
  - EMBED-02
  - EMBED-03

must_haves:
  truths:
    - "embed_all_chunks() reads only embedding_flag=0 chunks from SQLite (incremental)"
    - "embed_all_chunks() sets embedding_flag=1 in SQLite after successful upsert to ChromaDB"
    - "Re-running embed_all_chunks() on a fully-embedded corpus makes zero API calls"
    - "python src/main.py embed --db data/chunks.db --chroma data/chroma_db exits 0"
    - "ChunkStore.get_chunks_with_metadata_for_embedding() JOINs chunks+documents and returns filename, page_num, chunk_index, token_count alongside chunk_id and chunk_text"
  artifacts:
    - path: "src/ingest/store.py"
      provides: "get_chunks_with_metadata_for_embedding() method on ChunkStore"
      exports:
        - "ChunkStore.get_chunks_with_metadata_for_embedding"
    - path: "src/embed/pipeline.py"
      provides: "embed_all_chunks() and check_lm_studio() functions"
      exports:
        - "embed_all_chunks"
        - "check_lm_studio"
    - path: "src/main.py"
      provides: "embed CLI subcommand"
      contains: "embed"
  key_links:
    - from: "src/embed/pipeline.py"
      to: "src/ingest/store.py"
      via: "ChunkStore.get_chunks_with_metadata_for_embedding()"
      pattern: "get_chunks_with_metadata_for_embedding"
    - from: "src/embed/pipeline.py"
      to: "src/embed/embedder.py"
      via: "embed_chunks(batch, client, model)"
      pattern: "from src\\.embed\\.embedder import embed_chunks"
    - from: "src/embed/pipeline.py"
      to: "src/embed/vector_store.py"
      via: "VectorStore.upsert()"
      pattern: "from src\\.embed\\.vector_store import VectorStore"
    - from: "src/embed/pipeline.py"
      to: "src/ingest/store.py"
      via: "ChunkStore.mark_chunks_embedded()"
      pattern: "mark_chunks_embedded"
    - from: "src/main.py"
      to: "src/embed/pipeline.py"
      via: "cmd_embed calls embed_all_chunks"
      pattern: "from src\\.embed\\.pipeline import embed_all_chunks"
---

<objective>
Wire the full embedding pipeline: add get_chunks_with_metadata_for_embedding() to
ChunkStore, implement src/embed/pipeline.py (the embed loop), and add the embed
CLI subcommand to src/main.py.

Purpose: EMBED-01/02/03 end-to-end — the pipeline reads unembedded chunks from SQLite,
calls embed_chunks() in batches of 8, upserts vectors and metadata into ChromaDB via
VectorStore, and marks embedding_flag=1 in SQLite. Incremental: re-runs are safe and
skip already-embedded chunks.

Output:
- src/ingest/store.py — new method get_chunks_with_metadata_for_embedding()
- src/embed/pipeline.py — embed_all_chunks() and check_lm_studio()
- src/main.py — embed subcommand (python src/main.py embed --db ... --chroma ...)
</objective>

<execution_context>
@/Users/2171176/.claude/get-shit-done/workflows/execute-plan.md
@/Users/2171176/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/02-embedding-vector-search/02-RESEARCH.md
@.planning/phases/02-embedding-vector-search/02-02-SUMMARY.md
@.planning/phases/02-embedding-vector-search/02-03-SUMMARY.md

@src/ingest/store.py
@src/embed/pipeline.py
@src/main.py
</context>

<interfaces>
<!-- Existing ChunkStore methods — DO NOT change signatures -->

From src/ingest/store.py (read before touching):
```python
class ChunkStore:
    def get_chunks_for_embedding(self, batch_size: int = 100) -> list[sqlite3.Row]:
        # Returns rows with only chunk_id and chunk_text. embedding_flag=0.
        # SELECT chunk_id, chunk_text FROM chunks WHERE embedding_flag = 0 LIMIT ?

    def mark_chunks_embedded(self, chunk_ids: list[int]) -> None:
        # Sets embedding_flag=1 for the given chunk_ids.
```

Schema columns (from src/db/schema.sql):
```
chunks:    chunk_id, doc_id, page_num, chunk_index, chunk_text, token_count, embedding_flag
documents: doc_id, filename, ...
JOIN key:  chunks.doc_id = documents.doc_id
```

From src/embed/embedder.py (Plan 02):
```python
def embed_chunks(
    chunks: list[dict],   # each dict must have key "chunk_text"
    client: Any,          # openai.OpenAI
    model: str,
    batch_size: int = 8,
) -> list[list[float]]:   # same order as input chunks
```

From src/embed/vector_store.py (Plan 03):
```python
class VectorStore:
    def __init__(self, chroma_path: str = "data/chroma_db") -> None: ...
    def upsert(
        self,
        chunk_ids: list[int],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],  # required keys: doc_id, filename, page_num, chunk_index, token_count
    ) -> None: ...
    def count(self) -> int: ...
```

From src/main.py (existing subcommand pattern):
```python
def cmd_ingest(args: argparse.Namespace) -> int:
    from src.ingest.pipeline import ingest_directory, ingest_document
    ...
    return 0

p_ingest = subparsers.add_parser("ingest", help="Ingest PDF/PPTX documents")
p_ingest.add_argument("--path", required=True, ...)
p_ingest.add_argument("--db", default="data/chunks.db", ...)
p_ingest.set_defaults(func=cmd_ingest)
```

LM Studio health check (from RESEARCH.md Pattern 3, httpx is installed):
```python
import httpx
def check_lm_studio(host: str = "localhost", port: int = 1234) -> bool:
    try:
        r = httpx.get(f"http://{host}:{port}/v1/models", timeout=2.0)
        return r.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add get_chunks_with_metadata_for_embedding() to ChunkStore</name>

  <read_first>
    - src/ingest/store.py (read full file — find the exact insertion point after mark_chunks_embedded and before _INLINE_SCHEMA)
    - src/db/schema.sql (confirm column names: chunks.doc_id, documents.filename)
  </read_first>

  <files>src/ingest/store.py</files>

  <behavior>
    - Returns list of sqlite3.Row with columns: chunk_id, chunk_text, doc_id, filename, page_num, chunk_index, token_count
    - Returns only rows where embedding_flag = 0
    - Returns at most batch_size rows (default 8)
    - Returns [] when all chunks have embedding_flag = 1
    - Does NOT modify any data — pure SELECT with JOIN
  </behavior>

  <action>
Insert one new method into ChunkStore in src/ingest/store.py. Place it immediately
after mark_chunks_embedded() and before the module-level _INLINE_SCHEMA constant.
Do NOT modify any existing methods.

Add exactly this method:

```python
def get_chunks_with_metadata_for_embedding(
    self, batch_size: int = 8
) -> list[sqlite3.Row]:
    """Retrieve a batch of unembedded chunks with document metadata for embedding.

    JOINs chunks with documents to return filename, page_num, chunk_index, and
    token_count alongside chunk_id and chunk_text. The embedding pipeline uses
    these fields to populate ChromaDB metadata for citation at query time.

    Args:
        batch_size: Maximum number of chunks to return (default 8, conservative
            for LM Studio VRAM stability).

    Returns:
        List of sqlite3.Row objects with columns:
            chunk_id, chunk_text, doc_id, filename, page_num, chunk_index, token_count
        Returns [] when no unembedded chunks remain.
    """
    return self.conn.execute(
        """
        SELECT
            c.chunk_id,
            c.chunk_text,
            c.doc_id,
            d.filename,
            c.page_num,
            c.chunk_index,
            c.token_count
        FROM chunks c
        JOIN documents d ON c.doc_id = d.doc_id
        WHERE c.embedding_flag = 0
        LIMIT ?
        """,
        (batch_size,),
    ).fetchall()
```
  </action>

  <verify>
    <automated>cd C:/Users/2171176/Documents/Python/Knowledge_Graph_v2 && python -m pytest tests/test_ingest.py tests/test_ingest_e2e.py -q 2>&1 | tail -5</automated>
  </verify>

  <acceptance_criteria>
    - `grep "get_chunks_with_metadata_for_embedding" src/ingest/store.py` exits 0
    - `grep "JOIN documents d ON c.doc_id = d.doc_id" src/ingest/store.py` exits 0
    - `grep "d.filename" src/ingest/store.py` exits 0
    - Existing Phase 1 tests still pass: `pytest tests/test_ingest.py tests/test_ingest_e2e.py -q` exits 0
    - Manual smoke: `python -c "from src.ingest.store import ChunkStore; import sqlite3; print('import ok')"` exits 0
  </acceptance_criteria>

  <done>get_chunks_with_metadata_for_embedding() added. All existing Phase 1 tests still pass.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement src/embed/pipeline.py and add embed subcommand to src/main.py</name>

  <read_first>
    - src/embed/pipeline.py (check if stub exists from Plan 01 — if not, create fresh)
    - src/main.py (read full file to find the exact insertion point for the new subcommand after the stats parser block)
    - tests/test_embedding.py (read test_embed_all_chunks_loop and test_embed_loop_incremental carefully — note they patch "src.embed.pipeline.embed_chunks" and call embed_all_chunks(conn=conn, chroma_client=..., model=...))
    - .planning/phases/02-embedding-vector-search/02-RESEARCH.md (Pattern 1 full loop, lines 91-145)
  </read_first>

  <files>src/embed/pipeline.py, src/main.py</files>

  <behavior>
    - test_embed_all_chunks_loop: embed_all_chunks(conn=conn, chroma_client=EphemeralClient(), model="...") calls embed_chunks once (one pending chunk), sets embedding_flag=1 for that chunk_id
    - test_embed_loop_incremental: embed_all_chunks on a corpus where all embedding_flag=1 never calls embed_chunks (zero API calls)
    - CLI: python src/main.py embed --db data/chunks.db exits 0 when LM Studio is unavailable (prints warning and exits gracefully)
    - CLI: python src/main.py embed --help exits 0 (subcommand is registered)
  </behavior>

  <action>
PART A: Create src/embed/pipeline.py with this exact content:

```python
"""Embedding pipeline: SQLite -> LM Studio -> ChromaDB.

Reads chunks with embedding_flag=0 from SQLite, embeds them via LM Studio
in batches of 8, upserts vectors + metadata into ChromaDB, then marks
embedding_flag=1 in SQLite. Idempotent: safe to re-run; already-embedded
chunks are skipped.

Usage:
    from openai import OpenAI
    import chromadb
    import sqlite3

    conn = sqlite3.connect("data/chunks.db")
    conn.row_factory = sqlite3.Row
    chroma_client = chromadb.PersistentClient(path="data/chroma_db")
    client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

    from src.embed.pipeline import embed_all_chunks
    embed_all_chunks(conn=conn, chroma_client=chroma_client,
                     model="nomic-embed-text-v1.5", openai_client=client)
"""
from __future__ import annotations

import sqlite3
from typing import Any

import httpx
from tqdm import tqdm

from src.embed.embedder import embed_chunks
from src.embed.vector_store import VectorStore
from src.ingest.store import ChunkStore

DEFAULT_MODEL = "nomic-embed-text-v1.5"
DEFAULT_BATCH_SIZE = 8


def check_lm_studio(host: str = "localhost", port: int = 1234) -> bool:
    """Return True if LM Studio REST API is reachable and responding.

    Args:
        host: LM Studio host (default: localhost).
        port: LM Studio port (default: 1234).

    Returns:
        True if GET /v1/models returns 200, False otherwise.
    """
    try:
        r = httpx.get(f"http://{host}:{port}/v1/models", timeout=2.0)
        return r.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


def embed_all_chunks(
    conn: sqlite3.Connection,
    chroma_client: Any,
    model: str = DEFAULT_MODEL,
    openai_client: Any = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict:
    """Embed all pending chunks from SQLite and store in ChromaDB.

    Reads chunks WHERE embedding_flag=0, embeds in batches via LM Studio,
    upserts into ChromaDB with metadata, marks embedding_flag=1. Incremental:
    re-runs skip already-embedded chunks.

    Args:
        conn: Open sqlite3.Connection with row_factory=sqlite3.Row set.
        chroma_client: A chromadb client (PersistentClient or EphemeralClient).
            The pipeline calls get_or_create_collection on it directly.
        model: Embedding model name passed to LM Studio API.
        openai_client: openai.OpenAI client for LM Studio. If None and
            check_lm_studio() returns True, creates one automatically.
            Passing None when LM Studio is down raises RuntimeError.
        batch_size: Chunks per API call (default 8).

    Returns:
        Dict with keys:
        - "chunks_embedded": int -- total chunks newly embedded
        - "batches": int -- number of API calls made
    """
    # Lazily import OpenAI to keep tests fast (mocked via patch)
    if openai_client is None:
        from openai import OpenAI
        openai_client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

    # Get or create ChromaDB collection with cosine distance
    try:
        collection = chroma_client.get_or_create_collection(
            name="chunks",
            configuration={"hnsw": {"space": "cosine"}},
        )
    except Exception:
        collection = chroma_client.get_collection(name="chunks")

    # Build a VectorStore using the provided collection (bypass __init__ for testability)
    vs = VectorStore.__new__(VectorStore)
    vs._client = chroma_client
    vs._collection = collection

    store = ChunkStore(conn)

    total_embedded = 0
    batches = 0

    # Count pending up front for tqdm total
    pending_count = conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE embedding_flag = 0"
    ).fetchone()[0]

    if pending_count == 0:
        return {"chunks_embedded": 0, "batches": 0}

    with tqdm(total=pending_count, desc="Embedding chunks", unit="chunk") as pbar:
        while True:
            batch_rows = store.get_chunks_with_metadata_for_embedding(
                batch_size=batch_size
            )
            if not batch_rows:
                break

            # Build chunk dicts for embed_chunks (must have "chunk_text" key)
            chunk_dicts = [{"chunk_text": row["chunk_text"]} for row in batch_rows]
            chunk_ids = [row["chunk_id"] for row in batch_rows]
            documents = [row["chunk_text"] for row in batch_rows]
            metadatas = [
                {
                    "doc_id": row["doc_id"],
                    "filename": row["filename"],
                    "page_num": row["page_num"],
                    "chunk_index": row["chunk_index"],
                    "token_count": row["token_count"],
                }
                for row in batch_rows
            ]

            # Embed via LM Studio
            vectors = embed_chunks(
                chunk_dicts, client=openai_client, model=model, batch_size=batch_size
            )

            # Upsert into ChromaDB
            vs.upsert(
                chunk_ids=chunk_ids,
                embeddings=vectors,
                documents=documents,
                metadatas=metadatas,
            )

            # Mark embedded in SQLite
            store.mark_chunks_embedded(chunk_ids)

            total_embedded += len(chunk_ids)
            batches += 1
            pbar.update(len(chunk_ids))

    return {"chunks_embedded": total_embedded, "batches": batches}
```

PART B: Add embed subcommand to src/main.py.

Read src/main.py first. Add the following function and parser block.

Add cmd_embed() function after cmd_stats() and before main():

```python
def cmd_embed(args: argparse.Namespace) -> int:
    """Run the embedding pipeline on all pending chunks."""
    import sqlite3
    import chromadb
    from src.embed.pipeline import check_lm_studio, embed_all_chunks

    db_path = Path(args.db)
    chroma_path = Path(args.chroma)

    if not db_path.exists():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        return 1

    # Ensure chroma directory exists
    chroma_path.mkdir(parents=True, exist_ok=True)

    # Health check before connecting to LM Studio
    if not check_lm_studio():
        print(
            "Error: LM Studio is not running or not reachable at localhost:1234.\n"
            "Start LM Studio, load the embedding model, and retry.",
            file=sys.stderr,
        )
        return 1

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    try:
        chroma_client = chromadb.PersistentClient(path=str(chroma_path))
        start = time.perf_counter()
        result = embed_all_chunks(
            conn=conn,
            chroma_client=chroma_client,
            model=args.model,
        )
        elapsed = time.perf_counter() - start
        print(
            f"\nEmbedding complete in {elapsed:.2f}s\n"
            f"  Chunks embedded: {result['chunks_embedded']}\n"
            f"  API batches: {result['batches']}\n"
            f"  ChromaDB: {chroma_path}"
        )
    finally:
        conn.close()

    return 0
```

Add the parser block inside main(), immediately after the p_stats block
(before `args = parser.parse_args()`):

```python
    # embed subcommand
    p_embed = subparsers.add_parser("embed", help="Generate embeddings for pending chunks")
    p_embed.add_argument(
        "--db", default="data/chunks.db", help="SQLite database path (default: data/chunks.db)"
    )
    p_embed.add_argument(
        "--chroma", default="data/chroma_db", help="ChromaDB path (default: data/chroma_db)"
    )
    p_embed.add_argument(
        "--model", default="nomic-embed-text-v1.5",
        help="LM Studio embedding model name (default: nomic-embed-text-v1.5)"
    )
    p_embed.set_defaults(func=cmd_embed)
```
  </action>

  <verify>
    <automated>cd C:/Users/2171176/Documents/Python/Knowledge_Graph_v2 && python -m pytest tests/test_embedding.py::test_embed_all_chunks_loop tests/test_embedding.py::test_embed_loop_incremental -v 2>&1 | tail -10</automated>
    <automated>cd C:/Users/2171176/Documents/Python/Knowledge_Graph_v2 && python src/main.py embed --help 2>&1 | head -5</automated>
  </verify>

  <acceptance_criteria>
    - `pytest tests/test_embedding.py::test_embed_all_chunks_loop -v` exits 0 and shows PASSED (not xfailed)
    - `pytest tests/test_embedding.py::test_embed_loop_incremental -v` exits 0 and shows PASSED
    - `python src/main.py embed --help` exits 0 and output contains "--db" and "--chroma"
    - `grep "embed_all_chunks" src/embed/pipeline.py` exits 0
    - `grep "check_lm_studio" src/embed/pipeline.py` exits 0
    - `grep "get_chunks_with_metadata_for_embedding" src/embed/pipeline.py` exits 0
    - `grep "mark_chunks_embedded" src/embed/pipeline.py` exits 0
    - `grep "embedding_flag" src/embed/pipeline.py` exits 0 (pending_count check present)
    - `grep "cmd_embed" src/main.py` exits 0
    - `grep "p_embed" src/main.py` exits 0
    - `python -m pytest tests/test_embedding.py -q -m "not integration"` exits 0 (all 11 unit tests pass, 0 xfailed)
    - `python -m pytest tests/ -q -m "not integration"` exits 0 (full suite including Phase 1 still green)
  </acceptance_criteria>

  <done>
embed_all_chunks() and check_lm_studio() implemented. embed CLI subcommand registered.
All 11 unit tests pass. Full test suite exits 0.
  </done>
</task>

</tasks>

<verification>
Run after both tasks complete:

```
pytest tests/test_embedding.py -q -m "not integration"
```
Expected: 11 passed, 0 xfailed, exit code 0.

```
pytest tests/ -q -m "not integration"
```
Expected: all tests pass (Phase 1 + Phase 2 unit), exit code 0.

```
python src/main.py embed --help
```
Expected: prints usage with --db, --chroma, --model options, exits 0.
</verification>

<success_criteria>
- ChunkStore.get_chunks_with_metadata_for_embedding() JOINs chunks+documents, returns all 7 columns
- embed_all_chunks() loops until no embedding_flag=0 chunks remain
- embed_all_chunks() marks embedding_flag=1 after each successful upsert batch
- Re-running on fully-embedded corpus: zero API calls (test_embed_loop_incremental PASSES)
- python src/main.py embed --help exits 0
- All 11 unit tests in test_embedding.py PASSED (none xfailed)
- Full test suite (pytest tests/ -m "not integration") exits 0
</success_criteria>

<output>
After completion, create `.planning/phases/02-embedding-vector-search/02-04-SUMMARY.md`
</output>
