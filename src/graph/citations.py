"""SQLite bridge table for entity->chunk citations — Phase 3 plan 04 implements this.

Public API (stubs):
    CitationStore: wraps sqlite3.Connection
        .init_schema() -> None
        .insert_citations(citations: list[dict]) -> None
        .get_chunks_for_entity(entity_name: str, entity_type: str) -> list[dict]
"""
from __future__ import annotations

import sqlite3


class CitationStore:
    """Bridge table: entity_canonical_name + entity_type -> chunk_ids."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def init_schema(self) -> None:
        """Create chunk_citations table if not exists."""
        raise NotImplementedError

    def insert_citations(self, citations: list[dict]) -> None:
        """Insert {entity_canonical_name, entity_type, chunk_id} rows."""
        raise NotImplementedError

    def get_chunks_for_entity(self, entity_name: str, entity_type: str) -> list[dict]:
        """Return list of {chunk_id, doc_id, filename, page_num} dicts."""
        raise NotImplementedError
