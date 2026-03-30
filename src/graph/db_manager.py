"""KuzuDB graph schema and node/relationship management — Phase 3 plan 03 implements this.

Public API (stubs):
    create_graph_schema(db) -> None
    upsert_entity(db, entity: dict) -> None
    insert_relationships(db, relationships: list[dict], entity_map: dict) -> None
    query_entity(db, canonical_name: str, entity_type: str) -> dict | None
"""
from __future__ import annotations


def create_graph_schema(db) -> None:
    """Create KuzuDB node and relationship tables. Idempotent."""
    raise NotImplementedError


def upsert_entity(db, entity: dict) -> None:
    """Insert or skip entity node in KuzuDB. No-op if canonical_name already exists."""
    raise NotImplementedError


def insert_relationships(db, relationships: list[dict], entity_map: dict) -> None:
    """Insert typed relationships between entities in KuzuDB."""
    raise NotImplementedError


def query_entity(db, canonical_name: str, entity_type: str) -> "dict | None":
    """Return entity dict from KuzuDB or None if not found."""
    raise NotImplementedError
