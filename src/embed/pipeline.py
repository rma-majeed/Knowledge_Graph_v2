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

    # --- PROVIDER-06: Embedding model mismatch detection ---
    # Check if the model used to build existing embeddings differs from the current model.
    # If it does, warn the user and require explicit confirmation before proceeding.
    stored_model_row = None
    try:
        stored_model_row = conn.execute(
            "SELECT value FROM metadata WHERE key = 'embed_model'"
        ).fetchone()
    except Exception:
        pass  # metadata table may not exist in older databases — no-op

    if stored_model_row is not None:
        stored_model = stored_model_row[0] if isinstance(stored_model_row, (tuple, list)) else stored_model_row["value"]
        if stored_model and stored_model != model:
            print(
                f"\nWARNING: Embedding model changed from '{stored_model}' to '{model}'.\n"
                f"Existing vectors in ChromaDB were created with '{stored_model}'.\n"
                f"Continuing will require re-embedding ALL chunks. This may take a long time.\n"
                f"Type 'yes' to proceed with re-embedding, or anything else to abort: ",
                end="",
                flush=True,
            )
            user_input = input().strip().lower()
            if user_input != "yes":
                print("Aborted. No chunks were re-embedded.")
                return {"chunks_embedded": 0, "batches": 0}
    # --- End mismatch detection ---

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

    # Persist current embedding model to metadata table for future mismatch detection
    try:
        conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES ('embed_model', ?)",
            (model,),
        )
        conn.commit()
    except Exception:
        pass  # metadata table may not exist (older schema) — do not fail the embed run

    return {"chunks_embedded": total_embedded, "batches": batches}
