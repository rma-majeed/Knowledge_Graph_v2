---
phase: 03-knowledge-graph-construction
plan: 05
type: execute
wave: 4
depends_on:
  - "03-02"
  - "03-03"
  - "03-04"
files_modified:
  - src/graph/pipeline.py
  - src/main.py
  - data/extraction_state.json
autonomous: false
requirements:
  - GRAPH-01
  - GRAPH-02
  - GRAPH-03
  - GRAPH-04

must_haves:
  truths:
    - "build_knowledge_graph() reads all chunks from SQLite (embedding_flag=1), extracts entities in batches of 8, deduplicates, upserts to KuzuDB, and inserts citations to SQLite"
    - "build_knowledge_graph() is incremental — chunks already processed (tracked in extraction_state.json) are skipped on re-run"
    - "build_knowledge_graph() prints graph explosion warning to stderr if check_entity_density() returns alert=True"
    - "python src/main.py graph --db data/chunks.db --graph data/kuzu_db prints extraction progress and entity count summary"
    - "python src/main.py graph --help shows --db, --graph, --model arguments"
  artifacts:
    - path: "src/graph/pipeline.py"
      provides: "build_knowledge_graph() end-to-end pipeline"
      exports: ["build_knowledge_graph"]
      min_lines: 80
    - path: "src/main.py"
      provides: "graph subcommand wired to build_knowledge_graph()"
      contains: "cmd_graph"
  key_links:
    - from: "src/graph/pipeline.py"
      to: "src/graph/extractor.py"
      via: "extract_entities_relationships(batch_texts, client)"
      pattern: "from src.graph.extractor import"
    - from: "src/graph/pipeline.py"
      to: "src/graph/deduplicator.py"
      via: "deduplicate_entities(all_extracted)"
      pattern: "from src.graph.deduplicator import"
    - from: "src/graph/pipeline.py"
      to: "src/graph/db_manager.py"
      via: "upsert_entity(db, entity); insert_relationships(db, rels, entity_map)"
      pattern: "from src.graph.db_manager import"
    - from: "src/graph/pipeline.py"
      to: "src/graph/citations.py"
      via: "citation_store.insert_citations(citations)"
      pattern: "from src.graph.citations import"
    - from: "src/graph/pipeline.py"
      to: "src/graph/monitor.py"
      via: "check_entity_density(db, doc_count, chunk_count)"
      pattern: "from src.graph.monitor import"
    - from: "src/main.py"
      to: "src/graph/pipeline.py"
      via: "from src.graph.pipeline import build_knowledge_graph"
      pattern: "from src.graph.pipeline import"
---

<objective>
Wire all Phase 3 components into `src/graph/pipeline.py` (build_knowledge_graph) and add the `graph` subcommand to `src/main.py`.

Purpose: This is the integration plan — it connects extractor, deduplicator, db_manager, citations, and monitor into a single callable pipeline that reads from SQLite chunks, writes to KuzuDB, and persists citations. Adds the `graph` CLI subcommand matching the pattern established by `ingest` and `embed`.

Output: `src/graph/pipeline.py` with `build_knowledge_graph()`; `src/main.py` updated with `cmd_graph()` and `graph` subcommand parser. Human checkpoint verifies end-to-end CLI execution.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/03-knowledge-graph-construction/03-RESEARCH.md
@.planning/phases/03-knowledge-graph-construction/03-02-SUMMARY.md
@.planning/phases/03-knowledge-graph-construction/03-03-SUMMARY.md
@.planning/phases/03-knowledge-graph-construction/03-04-SUMMARY.md

<interfaces>
<!-- src/embed/pipeline.py — embed_all_chunks() pattern to replicate exactly -->
```python
def embed_all_chunks(conn, chroma_client, model, openai_client=None, batch_size=8) -> dict:
    """Returns {"chunks_embedded": int, "batches": int}"""
    # 1. Create client if not provided
    # 2. Pending count for tqdm
    # 3. Loop: get batch -> call API -> upsert to store -> mark processed
    # 4. Return summary dict
```

<!-- src/main.py — cmd_embed() pattern for cmd_graph() -->
```python
def cmd_embed(args: argparse.Namespace) -> int:
    # 1. Validate paths
    # 2. Health check LM Studio
    # 3. Open connections
    # 4. Call pipeline function
    # 5. Print summary
    # 6. Close connections in finally block
    return 0
```

<!-- src/ingest/store.py — how to read all chunks for graph extraction -->
```python
# Chunks with embedding_flag=1 are ready for graph extraction
conn.execute("SELECT chunk_id, chunk_text FROM chunks WHERE embedding_flag = 1")
```

<!-- extraction_state.json schema (from RESEARCH.md) -->
{
  "last_chunk_id_processed": 0,
  "chunks_processed": 0,
  "total_entities": 0
}

<!-- Graph pipeline component signatures (from plans 02, 03, 04) -->
extract_entities_relationships(chunk_texts: list[str], client) -> dict
deduplicate_entities(entities: list[dict]) -> list[dict]
create_graph_schema(db) -> None
upsert_entity(db, entity: dict) -> None
insert_relationships(db, relationships: list[dict], entity_map: dict) -> None
query_entity(db, canonical_name: str, entity_type: str) -> dict | None
CitationStore(conn).init_schema() / .insert_citations(citations) / .get_chunks_for_entity(name, type)
check_entity_density(db, doc_count, chunk_count) -> dict
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create src/graph/pipeline.py with build_knowledge_graph()</name>
  <files>src/graph/pipeline.py</files>

  <read_first>
    - src/embed/pipeline.py (entire file — replicate the batch loop pattern, tqdm usage, return dict structure)
    - src/ingest/store.py (get_chunks_with_metadata_for_embedding() — adapt for graph: query embedding_flag=1 chunks)
    - src/graph/extractor.py (extract_entities_relationships signature)
    - src/graph/deduplicator.py (deduplicate_entities signature)
    - src/graph/db_manager.py (create_graph_schema, upsert_entity, insert_relationships signatures)
    - src/graph/citations.py (CitationStore class)
    - src/graph/monitor.py (check_entity_density signature)
    - .planning/phases/03-knowledge-graph-construction/03-RESEARCH.md (extraction_state.json schema, anti-patterns section)
  </read_first>

  <action>
Create src/graph/pipeline.py (new file — does not exist yet) with the following implementation:

```python
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
                print(f"\nWarning: extraction failed for batch ending chunk_id={max_chunk_id_seen}: {exc}", file=sys.stderr)
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
```

Verify file created and imports cleanly:
`python -c "from src.graph.pipeline import build_knowledge_graph; print('pipeline OK')"`
  </action>

  <verify>
    <automated>cd "C:\Users\2171176\Documents\Python\Knowledge_Graph_v2" && python -c "from src.graph.pipeline import build_knowledge_graph; print('pipeline OK')"</automated>
  </verify>

  <acceptance_criteria>
    - `python -c "from src.graph.pipeline import build_knowledge_graph; print('OK')"` exits 0
    - `grep "from src.graph.extractor import" src/graph/pipeline.py` exits 0
    - `grep "from src.graph.deduplicator import" src/graph/pipeline.py` exits 0
    - `grep "from src.graph.db_manager import" src/graph/pipeline.py` exits 0
    - `grep "from src.graph.citations import" src/graph/pipeline.py` exits 0
    - `grep "from src.graph.monitor import" src/graph/pipeline.py` exits 0
    - `grep "_save_state" src/graph/pipeline.py` exits 0 (incremental checkpoint)
    - `grep "last_chunk_id_processed" src/graph/pipeline.py` exits 0
    - `grep "graph explosion" src/graph/pipeline.py` exits 0 (alert surfaced to user)
  </acceptance_criteria>

  <done>build_knowledge_graph() implemented; wires all 5 graph modules; incremental via extraction_state.json; graph explosion warning printed to stderr; imports cleanly</done>
</task>

<task type="auto">
  <name>Task 2: Add graph subcommand to src/main.py</name>
  <files>src/main.py</files>

  <read_first>
    - src/main.py (entire file — must understand existing subcommand structure to add cmd_graph without breaking ingest/stats/embed)
    - src/graph/pipeline.py (build_knowledge_graph signature — match arg names to argparse)
  </read_first>

  <action>
Read src/main.py completely first. Then make the following targeted additions:

1. Add `cmd_graph()` function after `cmd_embed()` (line ~137):

```python
def cmd_graph(args: argparse.Namespace) -> int:
    """Run the knowledge graph construction pipeline on embedded chunks."""
    import kuzu
    from src.embed.pipeline import check_lm_studio
    from src.graph.pipeline import build_knowledge_graph

    db_path = Path(args.db)
    graph_path = Path(args.graph)
    state_path = Path(args.state)

    if not db_path.exists():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        return 1

    # Health check LM Studio before starting (LLM required for extraction)
    if not check_lm_studio():
        print(
            "Error: LM Studio is not running or not reachable at localhost:1234.\n"
            "Start LM Studio, load the LLM model (Qwen2.5-7B-Instruct), and retry.",
            file=sys.stderr,
        )
        return 1

    # Ensure KuzuDB directory exists
    graph_path.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    db = kuzu.Database(str(graph_path))

    try:
        start = time.perf_counter()
        result = build_knowledge_graph(
            conn=conn,
            db=db,
            model=args.model,
            state_path=str(state_path),
        )
        elapsed = time.perf_counter() - start
        print(
            f"\nKnowledge graph complete in {elapsed:.2f}s\n"
            f"  Chunks processed: {result['chunks_processed']}\n"
            f"  Entities extracted: {result['entities_extracted']}\n"
            f"  LLM batches: {result['batches']}\n"
            f"  Graph explosion alert: {'YES (see stderr)' if result['alert'] else 'No'}\n"
            f"  KuzuDB: {graph_path}\n"
            f"  State: {state_path}"
        )
    finally:
        conn.close()

    return 0
```

2. Add `graph` subcommand parser in `main()` after the `embed` subcommand block:

```python
    # graph subcommand
    p_graph = subparsers.add_parser("graph", help="Build knowledge graph from embedded chunks")
    p_graph.add_argument(
        "--db", default="data/chunks.db", help="SQLite database path (default: data/chunks.db)"
    )
    p_graph.add_argument(
        "--graph", default="data/kuzu_db", help="KuzuDB directory path (default: data/kuzu_db)"
    )
    p_graph.add_argument(
        "--model", default="Qwen2.5-7B-Instruct",
        help="LM Studio LLM model name (default: Qwen2.5-7B-Instruct)"
    )
    p_graph.add_argument(
        "--state", default="data/extraction_state.json",
        help="Extraction checkpoint file (default: data/extraction_state.json)"
    )
    p_graph.set_defaults(func=cmd_graph)
```

Verify after editing:
`python src/main.py --help` — must show: ingest, stats, embed, graph
`python src/main.py graph --help` — must show: --db, --graph, --model, --state
  </action>

  <verify>
    <automated>cd "C:\Users\2171176\Documents\Python\Knowledge_Graph_v2" && python src/main.py --help 2>&1 | grep -E "graph|ingest|embed" && python src/main.py graph --help 2>&1 | grep -E "\-\-db|\-\-graph|\-\-model|\-\-state"</automated>
  </verify>

  <acceptance_criteria>
    - `python src/main.py --help` output contains "graph"
    - `python src/main.py graph --help` output contains "--db", "--graph", "--model", "--state"
    - `grep "cmd_graph" src/main.py` exits 0
    - `grep "from src.graph.pipeline import build_knowledge_graph" src/main.py` exits 0
    - `grep "kuzu.Database" src/main.py` exits 0
    - `python src/main.py --help` still shows ingest, stats, embed (existing subcommands unbroken)
    - Full test suite still green: `pytest tests/ -x -q -k "not lm_studio and not integration"` exits 0
  </acceptance_criteria>

  <done>cmd_graph() added to main.py; graph subcommand parser added with --db, --graph, --model, --state args; python src/main.py --help shows all 4 subcommands</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>
    Complete Phase 3 knowledge graph pipeline:
    - src/graph/extractor.py — LM Studio entity extraction
    - src/graph/deduplicator.py — RapidFuzz fuzzy dedup
    - src/graph/db_manager.py — KuzuDB schema + upsert
    - src/graph/citations.py — SQLite citation bridge table
    - src/graph/monitor.py — graph explosion detection
    - src/graph/pipeline.py — end-to-end pipeline
    - src/main.py — graph CLI subcommand
    - All 23 graph stubs now GREEN across 4 test files
  </what-built>

  <how-to-verify>
1. Run the full test suite (must be all green):
   ```
   pytest tests/ -x -q -k "not lm_studio and not integration"
   ```
   Expected: All tests pass. Graph stubs are no longer xfail — they are GREEN.

2. Verify CLI help works:
   ```
   python src/main.py --help
   python src/main.py graph --help
   ```
   Expected: `--help` lists `graph` subcommand with --db, --graph, --model, --state.

3. Verify all 5 src/graph modules import cleanly:
   ```
   python -c "
   from src.graph.extractor import extract_entities_relationships, ENTITY_TYPES
   from src.graph.deduplicator import normalize_entity_name, deduplicate_entities
   from src.graph.db_manager import create_graph_schema, upsert_entity, query_entity
   from src.graph.citations import CitationStore
   from src.graph.monitor import check_entity_density
   from src.graph.pipeline import build_knowledge_graph
   print('All imports OK')
   "
   ```

4. (Optional — requires LM Studio with Qwen2.5-7B-Instruct loaded):
   If LM Studio is running, test real extraction on fixtures:
   ```
   python src/main.py ingest --path fixtures/ --db data/test_graph.db
   python src/main.py embed --db data/test_graph.db --chroma data/test_chroma
   python src/main.py graph --db data/test_graph.db --graph data/test_kuzu --state data/test_state.json
   ```
   Expected: Prints entity count, no graph explosion alert for small fixture corpus.
  </how-to-verify>

  <resume-signal>Type "approved" when all automated checks pass and imports are clean. Describe any failures if checks do not pass.</resume-signal>
</task>

</tasks>

<verification>
```bash
# All 23 graph tests pass
pytest tests/test_graph_extraction.py tests/test_deduplicator.py tests/test_kuzu_db.py tests/test_citations.py -v -k "not lm_studio" --tb=short

# Full suite green
pytest tests/ -x -q -k "not lm_studio and not integration" --tb=short

# CLI help
python src/main.py --help
python src/main.py graph --help

# All imports
python -c "from src.graph.pipeline import build_knowledge_graph; print('OK')"
```
</verification>

<success_criteria>
- build_knowledge_graph() reads embedded SQLite chunks, calls LM Studio LLM, deduplicates, writes to KuzuDB, inserts citations
- Incremental: extraction_state.json tracks last_chunk_id_processed; re-runs skip processed chunks
- Graph explosion warning printed to stderr when density_per_doc > 50 or total entities > 10K
- python src/main.py graph --help shows all 4 arguments
- python src/main.py --help still shows all 4 subcommands (ingest, stats, embed, graph)
- Full test suite green (all 4 graph test files GREEN, not xfail; all prior phases unaffected)
- Human checkpoint approved
</success_criteria>

<output>
After completion, create `.planning/phases/03-knowledge-graph-construction/03-05-SUMMARY.md`
</output>
