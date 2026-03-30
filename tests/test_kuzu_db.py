"""Tests for Phase 3: KuzuDB Graph Storage (GRAPH-03).

Wave 0 stubs — all xfail until plan 03-03 fills them in.

Unit tests (tmp_path KuzuDB — no data persistence):
  - test_create_schema_idempotent
  - test_insert_entity_oem
  - test_insert_entity_supplier
  - test_query_entity_returns_dict
  - test_query_entity_missing_returns_none
  - test_upsert_entity_no_duplicate
  - test_insert_relationship_uses
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# GRAPH-03: KuzuDB schema and entity management
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_create_schema_idempotent(tmp_path) -> None:
    """create_graph_schema() can be called twice without raising an exception."""
    import kuzu
    from src.graph.db_manager import create_graph_schema

    db = kuzu.Database(str(tmp_path / "test_graph.db"))
    create_graph_schema(db)  # First call
    create_graph_schema(db)  # Second call — must not raise


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_insert_entity_oem(tmp_path) -> None:
    """upsert_entity() inserts an OEM entity node into KuzuDB."""
    import kuzu
    from src.graph.db_manager import create_graph_schema, upsert_entity

    db = kuzu.Database(str(tmp_path / "test_graph.db"))
    create_graph_schema(db)

    entity = {"name": "Toyota", "type": "OEM", "confidence": 0.95}
    upsert_entity(db, entity)  # Must not raise


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_insert_entity_supplier(tmp_path) -> None:
    """upsert_entity() inserts a Supplier entity node into KuzuDB."""
    import kuzu
    from src.graph.db_manager import create_graph_schema, upsert_entity

    db = kuzu.Database(str(tmp_path / "test_graph.db"))
    create_graph_schema(db)

    entity = {"name": "Bosch", "type": "Supplier", "confidence": 0.9}
    upsert_entity(db, entity)  # Must not raise


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_query_entity_returns_dict(tmp_path) -> None:
    """query_entity() returns a dict for an entity that was inserted."""
    import kuzu
    from src.graph.db_manager import create_graph_schema, upsert_entity, query_entity

    db = kuzu.Database(str(tmp_path / "test_graph.db"))
    create_graph_schema(db)
    upsert_entity(db, {"name": "BMW", "type": "OEM", "confidence": 0.9})

    result = query_entity(db, "BMW", "OEM")

    assert result is not None
    assert result["canonical_name"] == "BMW"


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_query_entity_missing_returns_none(tmp_path) -> None:
    """query_entity() returns None for an entity that does not exist."""
    import kuzu
    from src.graph.db_manager import create_graph_schema, query_entity

    db = kuzu.Database(str(tmp_path / "test_graph.db"))
    create_graph_schema(db)

    result = query_entity(db, "NonExistentCorp", "OEM")
    assert result is None


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_upsert_entity_no_duplicate(tmp_path) -> None:
    """upsert_entity() inserting the same entity twice does not create duplicates."""
    import kuzu
    from src.graph.db_manager import create_graph_schema, upsert_entity

    db = kuzu.Database(str(tmp_path / "test_graph.db"))
    create_graph_schema(db)

    entity = {"name": "Tesla", "type": "OEM", "confidence": 0.95}
    upsert_entity(db, entity)
    upsert_entity(db, entity)  # Second upsert must not raise or duplicate

    conn = kuzu.Connection(db)
    # kuzu 0.11+ uses get_all() returning list of lists, not fetchall() returning list of dicts
    result = conn.execute("MATCH (n:OEM {canonical_name: 'Tesla'}) RETURN COUNT(n) AS cnt").get_all()
    assert result[0][0] == 1


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_insert_relationship_uses(tmp_path) -> None:
    """insert_relationships() inserts a USES relationship between OEM and Technology."""
    import kuzu
    from src.graph.db_manager import create_graph_schema, upsert_entity, insert_relationships

    db = kuzu.Database(str(tmp_path / "test_graph.db"))
    create_graph_schema(db)
    upsert_entity(db, {"name": "BMW", "type": "OEM", "confidence": 0.9})
    upsert_entity(db, {"name": "LiDAR", "type": "Technology", "confidence": 0.85})

    entity_map = {
        "BMW": ("OEM", "BMW"),
        "LiDAR": ("Technology", "LiDAR"),
    }
    relationships = [{"source_name": "BMW", "target_name": "LiDAR", "type": "USES"}]
    insert_relationships(db, relationships, entity_map)  # Must not raise
