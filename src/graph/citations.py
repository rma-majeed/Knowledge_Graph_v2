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
