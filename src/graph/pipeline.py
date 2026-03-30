"""Knowledge graph construction pipeline: SQLite chunks -> LM Studio -> KuzuDB.

Reads chunks WHERE embedding_flag=1 from SQLite (embedded chunks are ready for extraction),
extracts entities and relationships via LM Studio LLM in batches of 8, deduplicates using
RapidFuzz, upserts canonical entities into KuzuDB, inserts entity-chunk citations into
SQLite, and checks for graph explosion after each batch.

Incremental: tracks processed chunk IDs in extraction_state.json. Re-runs skip
already-processed chunks.

Usage:
    from openai import OpenAI
    import kuzu
    import sqlite3

    conn = sqlite3.connect("data/chunks.db")
    conn.row_factory = sqlite3.Row
    db = kuzu.Database("data/kuzu_db")
    client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

    from src.graph.pipeline import build_knowledge_graph
    result = build_knowledge_graph(
        conn=conn, db=db, openai_client=client,
        model="Qwen2.5-7B-Instruct",
        state_path="data/extraction_state.json",
    )
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import kuzu
from tqdm import tqdm

from src.graph.citations import CitationStore
from src.graph.db_manager import create_graph_schema, insert_relationships, upsert_entity
from src.graph.deduplicator import deduplicate_entities
from src.graph.extractor import BATCH_SIZE, extract_entities_relationships
from src.graph.monitor import check_entity_density

DEFAULT_MODEL = "Qwen2.5-7B-Instruct"
DEFAULT_STATE_PATH = "data/extraction_state.json"


def _load_state(state_path: Path) -> dict:
    """Load extraction checkpoint from JSON file. Returns defaults if file missing."""
    if state_path.exists():
        try:
            return json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"last_chunk_id_processed": 0, "chunks_processed": 0, "total_entities": 0}


def _save_state(state_path: Path, state: dict) -> None:
    """Persist extraction checkpoint to JSON file."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def build_knowledge_graph(
    conn: sqlite3.Connection,
    db: kuzu.Database,
    openai_client: Any = None,
    model: str = DEFAULT_MODEL,
    batch_size: int = BATCH_SIZE,
    state_path: "str | Path" = DEFAULT_STATE_PATH,
) -> dict:
    """Build knowledge graph from embedded SQLite chunks.

    Reads chunks WHERE embedding_flag=1 AND chunk_id > last_checkpoint, extracts
    entities/relationships via LM Studio LLM in batches of batch_size, deduplicates,
    upserts to KuzuDB, inserts citations to SQLite chunk_citations table.

    Args:
        conn: Open sqlite3.Connection with row_factory=sqlite3.Row set.
        db: Open kuzu.Database for the knowledge graph.
        openai_client: openai.OpenAI client for LM Studio. Created automatically if None.
        model: LM Studio model name (default: Qwen2.5-7B-Instruct).
        batch_size: Chunks per LLM call (default 8 — do not exceed 8, causes timeouts).
        state_path: Path to extraction_state.json for incremental resumption.

    Returns:
        Dict with keys:
        - "chunks_processed": int — chunks newly processed this run
        - "entities_extracted": int — total canonical entities after dedup
        - "batches": int — number of LLM API calls made
        - "alert": bool — True if graph explosion threshold exceeded
    """
    if openai_client is None:
        from openai import OpenAI
        openai_client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

    state_path = Path(state_path)
    state = _load_state(state_path)
    last_chunk_id = state["last_chunk_id_processed"]

    # Ensure schema exists in KuzuDB
    create_graph_schema(db)

    # Ensure citation table exists in SQLite
    citation_store = CitationStore(conn)
    citation_store.init_schema()

    # Count pending chunks for progress bar
    pending_count = conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE embedding_flag = 1 AND chunk_id > ?",
        (last_chunk_id,),
    ).fetchone()[0]

    if pending_count == 0:
        print("No new chunks to process. Graph is up to date.")
        return {"chunks_processed": 0, "entities_extracted": 0, "batches": 0, "alert": False}

    total_chunks_processed = 0
    total_entities_extracted = 0
    batches = 0
    alert_raised = False
    max_chunk_id_seen = last_chunk_id

    with tqdm(total=pending_count, desc="Building knowledge graph", unit="chunk") as pbar:
        while True:
            # Fetch next batch of unprocessed embedded chunks
            rows = conn.execute(
                """SELECT c.chunk_id, c.chunk_text, c.doc_id, d.filename, c.page_num
                   FROM chunks c
                   JOIN documents d ON c.doc_id = d.doc_id
                   WHERE c.embedding_flag = 1 AND c.chunk_id > ?
                   ORDER BY c.chunk_id
                   LIMIT ?""",
                (max_chunk_id_seen, batch_size),
            ).fetchall()

            if not rows:
                break

            chunk_ids = [row["chunk_id"] for row in rows]
            chunk_texts = [row["chunk_text"] for row in rows]
            max_chunk_id_seen = max(chunk_ids)

            # Extract entities and relationships from batch
            try:
                extraction = extract_entities_relationships(chunk_texts, openai_client)
            except Exception as exc:
                print(
                    f"\nWarning: extraction failed for batch ending chunk_id={max_chunk_id_seen}: {exc}",
                    file=sys.stderr,
                )
                pbar.update(len(rows))
                total_chunks_processed += len(rows)
                continue

            raw_entities = extraction.get("entities", [])
            relationships = extraction.get("relationships", [])

            # Deduplicate within batch
            canonical_entities = deduplicate_entities(raw_entities)

            # Upsert canonical entities to KuzuDB
            entity_map: dict[str, tuple[str, str]] = {}
            for entity in canonical_entities:
                upsert_entity(db, entity)
                entity_map[entity["name"]] = (entity["type"], entity["name"])

            # Insert typed relationships
            if relationships:
                insert_relationships(db, relationships, entity_map)

            # Insert citations: each canonical entity -> all chunks in this batch
            citations = [
                {
                    "entity_canonical_name": entity["name"],
                    "entity_type": entity["type"],
                    "chunk_id": chunk_id,
                }
                for entity in canonical_entities
                for chunk_id in chunk_ids
            ]
            if citations:
                citation_store.insert_citations(citations)

            total_chunks_processed += len(rows)
            total_entities_extracted += len(canonical_entities)
            batches += 1

            # Update checkpoint after each successful batch
            state["last_chunk_id_processed"] = max_chunk_id_seen
            state["chunks_processed"] = state.get("chunks_processed", 0) + len(rows)
            state["total_entities"] = state.get("total_entities", 0) + len(canonical_entities)
            _save_state(state_path, state)

            pbar.update(len(rows))

    # Graph explosion check
    doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    density = check_entity_density(db, doc_count=doc_count, chunk_count=total_chunks_processed or 1)
    if density["alert"]:
        alert_raised = True
        print(
            f"\nWARNING: Graph explosion detected — {density['reason']}",
            file=sys.stderr,
        )

    return {
        "chunks_processed": total_chunks_processed,
        "entities_extracted": total_entities_extracted,
        "batches": batches,
        "alert": alert_raised,
    }
