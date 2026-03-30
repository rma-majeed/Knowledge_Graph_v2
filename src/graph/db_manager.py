"""KuzuDB graph schema creation and entity/relationship management.

Creates node and relationship tables for the automotive knowledge graph. All operations
use kuzu.Connection (not db.execute directly). Schema creation is idempotent. Entity
upsert uses MERGE to prevent duplicate nodes.

Public API:
    create_graph_schema(db: kuzu.Database) -> None
    upsert_entity(db: kuzu.Database, entity: dict) -> None
    insert_relationships(db: kuzu.Database, relationships: list[dict], entity_map: dict) -> None
    query_entity(db: kuzu.Database, canonical_name: str, entity_type: str) -> dict | None
"""
from __future__ import annotations

import kuzu

# Node table DDL — each entity type is a separate KuzuDB node table
_NODE_TABLE_DDL = {
    "OEM": (
        "CREATE NODE TABLE IF NOT EXISTS OEM("
        "canonical_name STRING PRIMARY KEY, confidence DOUBLE)"
    ),
    "Supplier": (
        "CREATE NODE TABLE IF NOT EXISTS Supplier("
        "canonical_name STRING PRIMARY KEY, confidence DOUBLE)"
    ),
    "Technology": (
        "CREATE NODE TABLE IF NOT EXISTS Technology("
        "canonical_name STRING PRIMARY KEY, confidence DOUBLE)"
    ),
    "Product": (
        "CREATE NODE TABLE IF NOT EXISTS Product("
        "canonical_name STRING PRIMARY KEY, confidence DOUBLE)"
    ),
    "Recommendation": (
        "CREATE NODE TABLE IF NOT EXISTS Recommendation("
        "canonical_name STRING PRIMARY KEY, confidence DOUBLE)"
    ),
}

# Relationship table DDL — typed edges between entity nodes
_REL_TABLE_DDL = [
    "CREATE REL TABLE IF NOT EXISTS IS_A(FROM OEM TO OEM, strength DOUBLE)",
    "CREATE REL TABLE IF NOT EXISTS USES(FROM OEM TO Technology, strength DOUBLE)",
    "CREATE REL TABLE IF NOT EXISTS USES_SUP(FROM Supplier TO Technology, strength DOUBLE)",
    "CREATE REL TABLE IF NOT EXISTS USES_PROD(FROM OEM TO Product, strength DOUBLE)",
    "CREATE REL TABLE IF NOT EXISTS PRODUCES(FROM OEM TO Product, strength DOUBLE)",
    "CREATE REL TABLE IF NOT EXISTS PRODUCES_SUP(FROM Supplier TO Product, strength DOUBLE)",
    "CREATE REL TABLE IF NOT EXISTS RECOMMENDS(FROM Recommendation TO OEM, strength DOUBLE)",
    "CREATE REL TABLE IF NOT EXISTS RECOMMENDS_SUP(FROM Recommendation TO Supplier, strength DOUBLE)",
    "CREATE REL TABLE IF NOT EXISTS RECOMMENDS_TECH(FROM Recommendation TO Technology, strength DOUBLE)",
    "CREATE REL TABLE IF NOT EXISTS RECOMMENDS_PROD(FROM Recommendation TO Product, strength DOUBLE)",
]

# Valid relationship type -> rel table name lookup
_REL_TYPE_MAP: dict[tuple[str, str, str], str] = {
    ("OEM", "OEM", "IS_A"): "IS_A",
    ("OEM", "Technology", "USES"): "USES",
    ("Supplier", "Technology", "USES"): "USES_SUP",
    ("OEM", "Product", "USES"): "USES_PROD",
    ("OEM", "Product", "PRODUCES"): "PRODUCES",
    ("Supplier", "Product", "PRODUCES"): "PRODUCES_SUP",
    ("Recommendation", "OEM", "RECOMMENDS"): "RECOMMENDS",
    ("Recommendation", "Supplier", "RECOMMENDS"): "RECOMMENDS_SUP",
    ("Recommendation", "Technology", "RECOMMENDS"): "RECOMMENDS_TECH",
    ("Recommendation", "Product", "RECOMMENDS"): "RECOMMENDS_PROD",
}


def create_graph_schema(db: kuzu.Database) -> None:
    """Create KuzuDB node and relationship tables for the entity graph.

    Idempotent: safe to call on an existing database. Uses IF NOT EXISTS DDL.
    Creates 5 node tables (OEM, Supplier, Technology, Product, Recommendation)
    and relationship tables for typed edges.

    Args:
        db: An open kuzu.Database instance.
    """
    conn = kuzu.Connection(db)
    for ddl in _NODE_TABLE_DDL.values():
        conn.execute(ddl)
    for ddl in _REL_TABLE_DDL:
        conn.execute(ddl)


def upsert_entity(db: kuzu.Database, entity: dict) -> None:
    """Insert entity node into KuzuDB. No-op (skip) if canonical_name already exists.

    Uses MERGE semantics: if a node with the same canonical_name exists, keeps it
    without modification. If new, creates with provided confidence.

    Args:
        db: An open kuzu.Database instance (schema must already exist).
        entity: Dict with keys:
            - name (str): Entity canonical name
            - type (str): One of OEM|Supplier|Technology|Product|Recommendation
            - confidence (float): Confidence score 0.0-1.0

    Raises:
        ValueError: If entity["type"] is not a valid node table name.
    """
    entity_type = entity["type"]
    if entity_type not in _NODE_TABLE_DDL:
        raise ValueError(f"Unknown entity type: {entity_type!r}")

    canonical_name = entity["name"].replace("'", "\\'")
    confidence = float(entity.get("confidence", 0.7))

    conn = kuzu.Connection(db)
    # MERGE: create only if not exists (idempotent upsert)
    conn.execute(
        f"MERGE (n:{entity_type} {{canonical_name: '{canonical_name}'}}) "
        f"ON CREATE SET n.confidence = {confidence}"
    )


def insert_relationships(
    db: kuzu.Database,
    relationships: list[dict],
    entity_map: dict,
) -> None:
    """Insert typed relationships between entities in KuzuDB.

    Skips any relationship where source or target entity is not in entity_map,
    or where the relationship type combination is not in _REL_TYPE_MAP.

    Args:
        db: An open kuzu.Database instance (schema must already exist).
        relationships: List of {source_name, target_name, type} dicts.
        entity_map: Dict mapping canonical_name -> (entity_type, canonical_name).
            e.g. {"Toyota": ("OEM", "Toyota"), "LiDAR": ("Technology", "LiDAR")}
    """
    conn = kuzu.Connection(db)

    for rel in relationships:
        source_name = rel.get("source_name", "")
        target_name = rel.get("target_name", "")
        rel_type = rel.get("type", "")

        if source_name not in entity_map or target_name not in entity_map:
            continue  # Skip — entity not in graph

        source_type, _ = entity_map[source_name]
        target_type, _ = entity_map[target_name]

        rel_table = _REL_TYPE_MAP.get((source_type, target_type, rel_type))
        if rel_table is None:
            continue  # Skip unsupported relationship combination

        src = source_name.replace("'", "\\'")
        tgt = target_name.replace("'", "\\'")

        try:
            conn.execute(
                f"MATCH (s:{source_type} {{canonical_name: '{src}'}}), "
                f"(t:{target_type} {{canonical_name: '{tgt}'}}) "
                f"CREATE (s)-[:{rel_table} {{strength: 1.0}}]->(t)"
            )
        except Exception:
            # Skip if relationship already exists or schema mismatch
            pass


def query_entity(
    db: kuzu.Database,
    canonical_name: str,
    entity_type: str,
) -> "dict | None":
    """Return entity dict from KuzuDB or None if not found.

    Args:
        db: An open kuzu.Database instance.
        canonical_name: Exact canonical name to look up.
        entity_type: Node table to search in (OEM|Supplier|Technology|Product|Recommendation).

    Returns:
        Dict with {"canonical_name": str, "confidence": float} or None if not found.
    """
    if entity_type not in _NODE_TABLE_DDL:
        return None

    name = canonical_name.replace("'", "\\'")
    conn = kuzu.Connection(db)
    result = conn.execute(
        f"MATCH (n:{entity_type} {{canonical_name: '{name}'}}) "
        f"RETURN n.canonical_name AS canonical_name, n.confidence AS confidence"
    ).get_all()

    if not result:
        return None

    row = result[0]
    # get_all() returns list of lists: [[canonical_name, confidence], ...]
    return {"canonical_name": row[0], "confidence": row[1]}
