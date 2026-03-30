---
phase: 03-knowledge-graph-construction
plan: 04
type: execute
wave: 3
depends_on:
  - "03-02"
  - "03-03"
files_modified:
  - src/graph/citations.py
  - src/graph/monitor.py
autonomous: true
requirements:
  - GRAPH-04

must_haves:
  truths:
    - "CitationStore.init_schema() creates chunk_citations table with UNIQUE(entity_canonical_name, entity_type, chunk_id) constraint"
    - "CitationStore.insert_citations() uses INSERT OR IGNORE — duplicate citations are silently skipped"
    - "CitationStore.get_chunks_for_entity() returns list of {chunk_id, doc_id, filename, page_num} dicts joining chunk_citations + chunks + documents"
    - "check_entity_density() alerts when density_per_doc > 50 OR total entities > 10000"
    - "All 5 citation tests pass GREEN"
  artifacts:
    - path: "src/graph/citations.py"
      provides: "CitationStore class with init_schema, insert_citations, get_chunks_for_entity"
      exports: ["CitationStore"]
      min_lines: 70
    - path: "src/graph/monitor.py"
      provides: "check_entity_density() graph explosion detection"
      exports: ["check_entity_density", "MAX_ENTITIES_PER_DOC", "MAX_TOTAL_ENTITIES"]
      min_lines: 40
  key_links:
    - from: "src/graph/citations.py"
      to: "chunks table (SQLite)"
      via: "JOIN chunks c ON cc.chunk_id = c.chunk_id"
      pattern: "JOIN chunks"
    - from: "src/graph/citations.py"
      to: "documents table (SQLite)"
      via: "JOIN documents d ON c.doc_id = d.doc_id"
      pattern: "JOIN documents"
    - from: "src/graph/monitor.py"
      to: "KuzuDB"
      via: "conn.execute('MATCH (n) RETURN COUNT(n)')"
      pattern: "MATCH.*COUNT"
    - from: "tests/test_citations.py"
      to: "src/graph/citations.py"
      via: "from src.graph.citations import CitationStore"
      pattern: "from src.graph.citations import CitationStore"
---

<objective>
Implement `src/graph/citations.py` (GRAPH-04) and `src/graph/monitor.py` (graph explosion guard).

Purpose: Citations bridge the KuzuDB entity graph back to SQLite chunks — without this, Phase 4 cannot cite answers. Monitor detects when extraction produces too many entities (density > 50/doc or total > 10K), enabling the pipeline to warn the user before the graph becomes useless noise.

Output: CitationStore fully implemented; check_entity_density() implemented; all 5 citation tests pass GREEN.
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

<interfaces>
<!-- From RESEARCH.md Pattern 4 — CitationStore contract -->
```python
import sqlite3

def create_chunk_citations_table(conn: sqlite3.Connection) -> None:
    """CREATE TABLE IF NOT EXISTS chunk_citations (
        citation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_canonical_name TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        chunk_id INTEGER NOT NULL,
        FOREIGN KEY(chunk_id) REFERENCES chunks(chunk_id) ON DELETE CASCADE,
        UNIQUE(entity_canonical_name, entity_type, chunk_id)
    )"""

def insert_chunk_citations(conn, citations: list[dict]) -> None:
    """INSERT OR IGNORE INTO chunk_citations (entity_canonical_name, entity_type, chunk_id)
       VALUES (?, ?, ?)"""

def get_chunks_for_entity(conn, entity_name: str, entity_type: str) -> list[dict]:
    """SELECT c.chunk_id, c.doc_id, d.filename, c.page_num
       FROM chunk_citations cc
       JOIN chunks c ON cc.chunk_id = c.chunk_id
       JOIN documents d ON c.doc_id = d.doc_id
       WHERE cc.entity_canonical_name = ? AND cc.entity_type = ?
       ORDER BY c.doc_id, c.page_num"""
```

<!-- From RESEARCH.md Pattern 5 — monitor contract -->
```python
def monitor_entity_density(db: kuzu.Database, doc_count: int, chunk_count: int) -> dict:
    """Returns {"entity_count": int, "density_per_doc": float, "density_per_chunk": float,
                "alert": bool, "reason": str|None}
    Alert triggers when density_per_doc > 50 OR entity_count > 10000."""
```

<!-- src/ingest/store.py — ChunkStore pattern (same conn-wrapping pattern for CitationStore) -->
class ChunkStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
    def init_schema(self) -> None: ...
    def insert_chunks(self, doc_id, chunks) -> None: ...
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement CitationStore in citations.py</name>
  <files>src/graph/citations.py</files>

  <read_first>
    - src/graph/citations.py (current stub with class structure already defined)
    - tests/test_citations.py (ALL 5 tests — understand SQLite setup pattern, fixture table creation, assertions)
    - src/ingest/store.py (ChunkStore pattern — replicate connection wrapping, executescript, executemany style)
    - .planning/phases/03-knowledge-graph-construction/03-RESEARCH.md (Pattern 4: exact SQL for chunk_citations table and queries)
  </read_first>

  <behavior>
    - Test 1 (test_init_schema_creates_table): init_schema() creates chunk_citations table; sqlite_master query finds it
    - Test 2 (test_insert_chunk_citation): insert_citations([{entity_canonical_name: "Toyota", entity_type: "OEM", chunk_id: 1}]); chunk_citations row exists
    - Test 3 (test_insert_duplicate_citation_ignored): insert same citation twice; COUNT returns 1 (not 2, no IntegrityError)
    - Test 4 (test_get_chunks_for_entity): after insert; get_chunks_for_entity("Toyota", "OEM") returns [{chunk_id: 1, filename: "report.pdf", page_num: 2}]
    - Test 5 (test_get_chunks_for_entity_empty): get_chunks_for_entity("NonExistentEntity", "OEM") returns []
  </behavior>

  <action>
Replace the entire contents of src/graph/citations.py with the following implementation:

```python
"""SQLite bridge table for entity-to-chunk citations.

Links KuzuDB entity canonical names to the source SQLite chunks they were extracted from.
Enables Phase 4 query answers to include source document citations.

The chunk_citations table lives in the same SQLite database as chunks and documents,
enabling direct JOIN queries at citation retrieval time.

Public API:
    CitationStore: wraps sqlite3.Connection
        .init_schema() -> None
        .insert_citations(citations: list[dict]) -> None
        .get_chunks_for_entity(entity_name: str, entity_type: str) -> list[dict]
"""
from __future__ import annotations

import sqlite3

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS chunk_citations (
    citation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_canonical_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    chunk_id INTEGER NOT NULL,
    FOREIGN KEY(chunk_id) REFERENCES chunks(chunk_id) ON DELETE CASCADE,
    UNIQUE(entity_canonical_name, entity_type, chunk_id)
);
CREATE INDEX IF NOT EXISTS idx_citations_entity ON chunk_citations(entity_canonical_name, entity_type);
CREATE INDEX IF NOT EXISTS idx_citations_chunk ON chunk_citations(chunk_id);
"""

_INSERT_SQL = """
INSERT OR IGNORE INTO chunk_citations (entity_canonical_name, entity_type, chunk_id)
VALUES (?, ?, ?)
"""

_GET_CHUNKS_SQL = """
SELECT c.chunk_id, c.doc_id, d.filename, c.page_num
FROM chunk_citations cc
JOIN chunks c ON cc.chunk_id = c.chunk_id
JOIN documents d ON c.doc_id = d.doc_id
WHERE cc.entity_canonical_name = ? AND cc.entity_type = ?
ORDER BY c.doc_id, c.page_num
"""


class CitationStore:
    """Bridge table: entity_canonical_name + entity_type -> source chunk_ids.

    The caller is responsible for creating and closing the SQLite connection.
    init_schema() must be called before any insert or query operations.
    All write operations commit immediately.

    Usage:
        conn = sqlite3.connect("data/chunks.db")
        conn.row_factory = sqlite3.Row
        store = CitationStore(conn)
        store.init_schema()

        store.insert_citations([
            {"entity_canonical_name": "Toyota", "entity_type": "OEM", "chunk_id": 42},
        ])

        chunks = store.get_chunks_for_entity("Toyota", "OEM")
        # [{"chunk_id": 42, "doc_id": 1, "filename": "report.pdf", "page_num": 3}]
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialise with an open SQLite connection.

        Args:
            conn: An open sqlite3.Connection. The caller manages lifecycle.
        """
        self.conn = conn

    def init_schema(self) -> None:
        """Create chunk_citations table and indexes if they do not exist.

        Idempotent: safe to call on an existing database with existing tables.
        """
        self.conn.executescript(_CREATE_TABLE_SQL)
        self.conn.commit()

    def insert_citations(self, citations: list[dict]) -> None:
        """Insert entity-to-chunk citation mappings.

        Uses INSERT OR IGNORE — duplicate (entity_canonical_name, entity_type, chunk_id)
        tuples are silently skipped. Safe to call with same citations multiple times.

        Args:
            citations: List of dicts with keys:
                - entity_canonical_name (str): Canonical entity name from KuzuDB
                - entity_type (str): Entity type (OEM|Supplier|Technology|Product|Recommendation)
                - chunk_id (int): chunk_id from SQLite chunks table
        """
        rows = [
            (c["entity_canonical_name"], c["entity_type"], c["chunk_id"])
            for c in citations
        ]
        self.conn.executemany(_INSERT_SQL, rows)
        self.conn.commit()

    def get_chunks_for_entity(
        self,
        entity_name: str,
        entity_type: str,
    ) -> list[dict]:
        """Retrieve source chunks for a given entity (used for citations in Phase 4).

        JOINs chunk_citations with chunks and documents to return full citation context.

        Args:
            entity_name: Canonical entity name to look up.
            entity_type: Entity type filter (OEM|Supplier|Technology|Product|Recommendation).

        Returns:
            List of dicts with keys: chunk_id, doc_id, filename, page_num.
            Returns empty list if no citations found.
        """
        rows = self.conn.execute(_GET_CHUNKS_SQL, (entity_name, entity_type)).fetchall()
        # Support both sqlite3.Row and plain tuple rows
        if rows and hasattr(rows[0], "keys"):
            return [dict(row) for row in rows]
        return [
            {"chunk_id": r[0], "doc_id": r[1], "filename": r[2], "page_num": r[3]}
            for r in rows
        ]
```

Run citation tests immediately:
`pytest tests/test_citations.py -x -q --tb=short`

All 5 tests must pass GREEN.
  </action>

  <verify>
    <automated>cd "C:\Users\2171176\Documents\Python\Knowledge_Graph_v2" && python -m pytest tests/test_citations.py -v --tb=short 2>&1 | tail -15</automated>
  </verify>

  <acceptance_criteria>
    - `pytest tests/test_citations.py -v` shows 5 PASSED (not xfail)
    - `grep "INSERT OR IGNORE" src/graph/citations.py` exits 0
    - `grep "UNIQUE(entity_canonical_name" src/graph/citations.py` exits 0
    - `grep "JOIN chunks" src/graph/citations.py` exits 0
    - `grep "JOIN documents" src/graph/citations.py` exits 0
    - `python -c "from src.graph.citations import CitationStore; print('OK')"` exits 0
  </acceptance_criteria>

  <done>CitationStore implemented with init_schema, insert_citations (INSERT OR IGNORE), get_chunks_for_entity (3-table JOIN); all 5 citation tests green</done>
</task>

<task type="auto">
  <name>Task 2: Implement check_entity_density() in monitor.py</name>
  <files>src/graph/monitor.py</files>

  <read_first>
    - src/graph/monitor.py (current stub with MAX_ENTITIES_PER_DOC and MAX_TOTAL_ENTITIES constants)
    - .planning/phases/03-knowledge-graph-construction/03-RESEARCH.md (Pattern 5: full monitor_entity_density reference implementation with alert thresholds)
    - src/graph/db_manager.py (understand kuzu.Connection pattern already established in plan 03-03)
  </read_first>

  <action>
Replace the entire contents of src/graph/monitor.py with the following implementation:

```python
"""Graph explosion detection and entity density monitoring.

Tracks entity count and density relative to document and chunk counts.
Alerts when extraction is too permissive (density_per_doc > 50 or total > 10K).

Public API:
    MAX_ENTITIES_PER_DOC: int — alert threshold (50 entities/doc)
    MAX_TOTAL_ENTITIES: int — hard cap alert threshold (10000 total)
    check_entity_density(db, doc_count: int, chunk_count: int) -> dict
"""
from __future__ import annotations

import kuzu

MAX_ENTITIES_PER_DOC: int = 50
MAX_TOTAL_ENTITIES: int = 10_000


def check_entity_density(db: kuzu.Database, doc_count: int, chunk_count: int) -> dict:
    """Check entity density metrics for graph explosion warning signs.

    Queries KuzuDB for total entity count across all node tables, calculates
    density per document and per chunk, and sets alert=True if thresholds exceeded.

    Args:
        db: An open kuzu.Database instance with schema created.
        doc_count: Number of documents processed (denominator for density_per_doc).
        chunk_count: Number of chunks processed (denominator for density_per_chunk).

    Returns:
        Dict with keys:
        - entity_count (int): Total entity nodes across all 5 node tables
        - density_per_doc (float): entity_count / doc_count (0.0 if doc_count == 0)
        - density_per_chunk (float): entity_count / chunk_count (0.0 if chunk_count == 0)
        - alert (bool): True if density_per_doc > MAX_ENTITIES_PER_DOC or entity_count > MAX_TOTAL_ENTITIES
        - reason (str | None): Human-readable explanation when alert=True, else None
    """
    conn = kuzu.Connection(db)

    # Count entities across all 5 node tables
    entity_count = 0
    for table in ("OEM", "Supplier", "Technology", "Product", "Recommendation"):
        try:
            result = conn.execute(
                f"MATCH (n:{table}) RETURN COUNT(n) AS cnt"
            ).fetchall()
            if result:
                entity_count += result[0]["cnt"]
        except Exception:
            # Table may not exist yet in early pipeline stages
            pass

    density_per_doc = entity_count / doc_count if doc_count > 0 else 0.0
    density_per_chunk = entity_count / chunk_count if chunk_count > 0 else 0.0

    alert = False
    reason: "str | None" = None

    if entity_count > MAX_TOTAL_ENTITIES:
        alert = True
        reason = (
            f"total entity_count={entity_count} exceeds {MAX_TOTAL_ENTITIES} hardcap "
            f"(graph explosion risk — tighten confidence threshold or entity whitelist)"
        )
    elif density_per_doc > MAX_ENTITIES_PER_DOC:
        alert = True
        reason = (
            f"density_per_doc={density_per_doc:.1f} exceeds {MAX_ENTITIES_PER_DOC} "
            f"(graph explosion risk — reduce confidence threshold from current level)"
        )

    return {
        "entity_count": entity_count,
        "density_per_doc": density_per_doc,
        "density_per_chunk": density_per_chunk,
        "alert": alert,
        "reason": reason,
    }
```

Verify the module imports cleanly:
`python -c "from src.graph.monitor import check_entity_density, MAX_ENTITIES_PER_DOC, MAX_TOTAL_ENTITIES; print('OK')"`

Note: There are no dedicated unit tests for monitor.py in Wave 0 (the VALIDATION.md does not list monitor tests). The function is tested indirectly through the pipeline in plan 03-05. Smoke test manually:
```python
python -c "
import kuzu, tempfile, os
from src.graph.db_manager import create_graph_schema, upsert_entity
from src.graph.monitor import check_entity_density
with tempfile.TemporaryDirectory() as d:
    db = kuzu.Database(os.path.join(d, 'test.db'))
    create_graph_schema(db)
    upsert_entity(db, {'name': 'Toyota', 'type': 'OEM', 'confidence': 0.9})
    result = check_entity_density(db, doc_count=1, chunk_count=4)
    assert result['entity_count'] == 1
    assert result['alert'] == False
    print('monitor smoke test OK:', result)
"
```
  </action>

  <verify>
    <automated>cd "C:\Users\2171176\Documents\Python\Knowledge_Graph_v2" && python -c "
import kuzu, tempfile, os
from src.graph.db_manager import create_graph_schema, upsert_entity
from src.graph.monitor import check_entity_density, MAX_ENTITIES_PER_DOC, MAX_TOTAL_ENTITIES
with tempfile.TemporaryDirectory() as d:
    db = kuzu.Database(os.path.join(d, 'test.db'))
    create_graph_schema(db)
    upsert_entity(db, {'name': 'Toyota', 'type': 'OEM', 'confidence': 0.9})
    result = check_entity_density(db, doc_count=1, chunk_count=4)
    assert result['entity_count'] == 1, result
    assert result['alert'] == False, result
    assert result['density_per_doc'] == 1.0, result
    print('monitor OK:', result)
"</automated>
  </verify>

  <acceptance_criteria>
    - `python -c "from src.graph.monitor import check_entity_density, MAX_ENTITIES_PER_DOC, MAX_TOTAL_ENTITIES; print('OK')"` exits 0
    - `grep "MAX_ENTITIES_PER_DOC" src/graph/monitor.py` exits 0 and shows value 50
    - `grep "MAX_TOTAL_ENTITIES" src/graph/monitor.py` exits 0 and shows value 10_000
    - `grep "density_per_doc" src/graph/monitor.py` exits 0
    - Smoke test (see verify command) runs without assertion errors
    - `grep "import kuzu" src/graph/monitor.py` exits 0
    - Full test suite still green: `pytest tests/ -x -q -k "not lm_studio and not integration"` exits 0
  </acceptance_criteria>

  <done>check_entity_density() queries KuzuDB for entity counts across all 5 node tables; alerts when density_per_doc > 50 or total > 10K; smoke test passes; all prior tests still green</done>
</task>

</tasks>

<verification>
```bash
# Citation tests (5 green)
pytest tests/test_citations.py -v --tb=short

# Monitor smoke test
python -c "
import kuzu, tempfile, os
from src.graph.db_manager import create_graph_schema, upsert_entity
from src.graph.monitor import check_entity_density
with tempfile.TemporaryDirectory() as d:
    db = kuzu.Database(os.path.join(d, 'g.db'))
    create_graph_schema(db)
    upsert_entity(db, {'name': 'BMW', 'type': 'OEM', 'confidence': 0.9})
    r = check_entity_density(db, 1, 4)
    print('alert:', r['alert'], 'count:', r['entity_count'])
"

# Full suite green
pytest tests/ -x -q -k "not lm_studio and not integration" --tb=short
```
</verification>

<success_criteria>
- 5 citation tests pass GREEN
- CitationStore.init_schema() creates chunk_citations with UNIQUE constraint
- CitationStore.insert_citations() uses INSERT OR IGNORE
- CitationStore.get_chunks_for_entity() JOINs chunk_citations + chunks + documents
- check_entity_density() queries all 5 node tables; alerts correctly on threshold violations
- Full test suite green (all prior phases unaffected)
</success_criteria>

<output>
After completion, create `.planning/phases/03-knowledge-graph-construction/03-04-SUMMARY.md`
</output>
