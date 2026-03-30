---
phase: 03-knowledge-graph-construction
plan: 03
type: execute
wave: 2
depends_on:
  - "03-01"
files_modified:
  - src/graph/deduplicator.py
  - src/graph/db_manager.py
autonomous: true
requirements:
  - GRAPH-02
  - GRAPH-03

must_haves:
  truths:
    - "normalize_entity_name() removes all legal suffixes (Inc., LLC, Corp., Ltd., GmbH, AG, SA, SARL, BV) from company names"
    - "deduplicate_entities() merges Toyota/Toyota Inc./Toyota Motor Corp. into one canonical entity (highest confidence kept)"
    - "deduplicate_entities() does NOT merge entities of different types even if names are identical"
    - "create_graph_schema() is idempotent — calling twice raises no exception"
    - "upsert_entity() inserts OEM and Supplier nodes; calling twice does not duplicate"
    - "query_entity() returns a dict for inserted entities and None for missing ones"
    - "All 5 deduplicator tests and all 7 kuzu_db tests pass"
  artifacts:
    - path: "src/graph/deduplicator.py"
      provides: "normalize_entity_name() and deduplicate_entities() implementations"
      exports: ["normalize_entity_name", "deduplicate_entities", "SIMILARITY_THRESHOLD"]
      min_lines: 70
    - path: "src/graph/db_manager.py"
      provides: "KuzuDB schema creation, upsert, query, relationship insertion"
      exports: ["create_graph_schema", "upsert_entity", "insert_relationships", "query_entity"]
      min_lines: 100
  key_links:
    - from: "src/graph/deduplicator.py"
      to: "rapidfuzz.fuzz"
      via: "fuzz.token_set_ratio()"
      pattern: "from rapidfuzz import fuzz"
    - from: "src/graph/db_manager.py"
      to: "kuzu"
      via: "kuzu.Database() and conn.execute(Cypher)"
      pattern: "import kuzu"
    - from: "tests/test_deduplicator.py"
      to: "src/graph/deduplicator.py"
      via: "from src.graph.deduplicator import normalize_entity_name, deduplicate_entities"
      pattern: "from src.graph.deduplicator import"
    - from: "tests/test_kuzu_db.py"
      to: "src/graph/db_manager.py"
      via: "from src.graph.db_manager import create_graph_schema, upsert_entity, query_entity"
      pattern: "from src.graph.db_manager import"
---

<objective>
Implement `src/graph/deduplicator.py` and `src/graph/db_manager.py` — entity deduplication and KuzuDB graph storage for Phase 3.

Purpose: Two independent implementations that can run in parallel with the extractor (Plan 02). Deduplicator uses RapidFuzz token_set_ratio + legal suffix normalization (GRAPH-02). DB manager creates KuzuDB schema and handles idempotent entity upsert and relationship insertion (GRAPH-03).

Output: Both modules fully implemented; 5 deduplicator tests and 7 KuzuDB tests all pass GREEN.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/03-knowledge-graph-construction/03-RESEARCH.md

<interfaces>
<!-- From RESEARCH.md Pattern 2 — deduplicator contract -->
```python
from rapidfuzz import fuzz
import re

SIMILARITY_THRESHOLD = 85  # token_set_ratio >= 85 to merge (not 90 — tune to 85 per RESEARCH note)

def normalize_entity_name(name: str) -> str:
    """Title case, strip legal suffixes, remove punctuation except hyphens."""
    # legal suffixes: Inc, Incorporated, LLC, Limited Liability Company, Corp, Corporation,
    #   Ltd, Limited, GmbH, AG, SA, SAS, SARL, BV, NV, Pty, Plc
    # Use regex with IGNORECASE: r'\s+(Inc|LLC|Corp|...)\.?\s*$'

def deduplicate_entities(extracted_entities: list[dict]) -> list[dict]:
    """Group by type, fuzzy match within type, keep highest confidence."""
    # fuzz.token_set_ratio(normalized_a, normalized_b) >= SIMILARITY_THRESHOLD -> merge
```

<!-- From RESEARCH.md Pattern 3 — KuzuDB contract -->
```python
import kuzu

def create_graph_schema(db: kuzu.Database) -> None:
    """CREATE NODE TABLE IF NOT EXISTS OEM(canonical_name STRING PRIMARY KEY, confidence FLOAT)
       CREATE NODE TABLE IF NOT EXISTS Supplier(canonical_name STRING PRIMARY KEY, tier INT8, confidence FLOAT)
       CREATE NODE TABLE IF NOT EXISTS Technology(canonical_name STRING PRIMARY KEY, domain STRING, confidence FLOAT)
       CREATE NODE TABLE IF NOT EXISTS Product(canonical_name STRING PRIMARY KEY, category STRING, confidence FLOAT)
       CREATE NODE TABLE IF NOT EXISTS Recommendation(canonical_name STRING PRIMARY KEY, priority INT8, confidence FLOAT)
       CREATE REL TABLE IF NOT EXISTS IS_A(FROM OEM|Supplier|Product TO OEM|Supplier|Technology|Product, strength FLOAT)
       CREATE REL TABLE IF NOT EXISTS USES(FROM OEM|Supplier TO Technology|Product, strength FLOAT)
       CREATE REL TABLE IF NOT EXISTS PRODUCES(FROM OEM|Supplier TO Product, strength FLOAT)
       CREATE REL TABLE IF NOT EXISTS RECOMMENDS(FROM Recommendation TO OEM|Supplier|Technology|Product, strength FLOAT)
    """

def upsert_entity(db: kuzu.Database, entity: dict) -> None:
    """Merge-or-insert: use MERGE pattern to avoid duplicates.
       entity = {"name": "Toyota", "type": "OEM", "confidence": 0.95}
    """

def query_entity(db: kuzu.Database, canonical_name: str, entity_type: str) -> dict | None:
    """MATCH (n:OEM {canonical_name: 'Toyota'}) RETURN n"""
```

<!-- KuzuDB MERGE pattern (avoids duplicate nodes) -->
```cypher
MERGE (n:OEM {canonical_name: 'Toyota'})
ON CREATE SET n.confidence = 0.95
ON MATCH SET n.confidence = CASE WHEN 0.95 > n.confidence THEN 0.95 ELSE n.confidence END
```

<!-- KuzuDB connection usage — db.execute() vs kuzu.Connection(db).execute() -->
KuzuDB requires: conn = kuzu.Connection(db); conn.execute("CYPHER")
NOT: db.execute() — db is kuzu.Database, not Connection
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement normalize_entity_name() and deduplicate_entities() in deduplicator.py</name>
  <files>src/graph/deduplicator.py</files>

  <read_first>
    - src/graph/deduplicator.py (current stub — understand existing constants)
    - tests/test_deduplicator.py (ALL 5 tests — understand exact normalization cases and merge behavior expected)
    - .planning/phases/03-knowledge-graph-construction/03-RESEARCH.md (Pattern 2: full normalize_entity_name and deduplicate_entities reference implementation)
  </read_first>

  <behavior>
    - Test 1 (test_normalize_name_title_case): "toyota motor corporation" -> "Toyota Motor Corporation"; "BOSCH" -> "Bosch"
    - Test 2 (test_normalize_name_removes_legal_suffixes): "Tesla Inc." -> "Tesla"; "Bosch GmbH" -> "Bosch"; "Continental AG" -> "Continental"; "Valeo SA" -> "Valeo"; "Aptiv LLC" -> "Aptiv"; "Toyota Motor Corp." -> "Toyota Motor"
    - Test 3 (test_normalize_name_strips_punctuation): "Tesla, Inc." -> "Tesla"; "Tier-1 Supplier" -> "Tier-1 Supplier" (hyphens preserved)
    - Test 4 (test_fuzzy_dedup_merges_variants): [Toyota, Toyota Inc., Toyota Motor Corp.] -> 1 entity with confidence=0.9 (highest)
    - Test 5 (test_fuzzy_dedup_preserves_different_entities): [Toyota/OEM, Honda/OEM, Bosch/Supplier] -> 3 entities
    - Test 6 (test_fuzzy_dedup_groups_by_type): [EV/Technology, EV/Product] -> 2 entities (different types, no merge)
    - Test 7 (test_fuzzy_dedup_empty_input): [] -> []
  </behavior>

  <action>
Replace the entire contents of src/graph/deduplicator.py with the following implementation:

```python
"""Entity deduplication via RapidFuzz fuzzy matching.

Normalizes entity names (title case, legal suffix removal, punctuation strip) and
merges surface form variants of the same entity using token_set_ratio >= 85.
Deduplication is scoped within entity type (OEM entities cannot merge with Supplier entities).

Public API:
    SIMILARITY_THRESHOLD: int — token_set_ratio threshold for merging (85)
    normalize_entity_name(name: str) -> str
    deduplicate_entities(extracted_entities: list[dict]) -> list[dict]
"""
from __future__ import annotations

import re

from rapidfuzz import fuzz

SIMILARITY_THRESHOLD: int = 85  # token_set_ratio >= 85 to merge variants

# Legal suffix pattern — order matters: longer suffixes before shorter to avoid partial matches
_LEGAL_SUFFIX_RE = re.compile(
    r"\s+(?:Incorporated|Limited\s+Liability\s+Company|Corporation|Limited|"
    r"Inc|LLC|Corp|Ltd|GmbH|AG|SA|SARL|SAS|BV|NV|Pty|Plc)\.?\s*$",
    flags=re.IGNORECASE,
)


def normalize_entity_name(name: str) -> str:
    """Normalize entity name for fuzzy matching.

    Applies in order:
    1. Title case
    2. Remove legal suffixes (Inc., LLC, Corp., Ltd., GmbH, AG, SA, SARL, BV, etc.)
    3. Remove punctuation except hyphens
    4. Collapse whitespace and strip

    Args:
        name: Raw entity name string.

    Returns:
        Normalized string suitable for fuzzy comparison.

    Examples:
        >>> normalize_entity_name("tesla inc.")
        'Tesla'
        >>> normalize_entity_name("TOYOTA MOTOR CORP.")
        'Toyota Motor'
        >>> normalize_entity_name("Tier-1 Supplier")
        'Tier-1 Supplier'
    """
    # Title case first
    name = name.title()
    # Remove legal suffixes (iteratively — handles "Corp., Ltd." edge cases)
    name = _LEGAL_SUFFIX_RE.sub("", name)
    # Remove punctuation except hyphens and alphanumeric (including accented chars)
    name = re.sub(r"[^\w\s-]", "", name)
    # Collapse multiple spaces
    name = re.sub(r"\s+", " ", name).strip()
    return name


def deduplicate_entities(extracted_entities: list[dict]) -> list[dict]:
    """Merge duplicate entities using fuzzy matching within the same entity type.

    Algorithm:
    1. Group entities by type (OEM, Supplier, Technology, Product, Recommendation)
    2. Within each type, normalize names and compare pairwise using token_set_ratio
    3. Entities with token_set_ratio >= SIMILARITY_THRESHOLD are merged
    4. The canonical form keeps the highest-confidence occurrence

    Args:
        extracted_entities: List of {name, type, confidence} dicts from LLM extraction.

    Returns:
        List of deduplicated canonical entity dicts. Each has the highest confidence
        among merged variants.

    Notes:
        - Empty input returns empty list (no error).
        - Entities of different types are never merged, even with identical names.
    """
    if not extracted_entities:
        return []

    # Normalize names for comparison
    entities_with_normalized = [
        {**e, "_normalized": normalize_entity_name(e["name"])}
        for e in extracted_entities
    ]

    # Group by type to avoid cross-type merging
    by_type: dict[str, list[dict]] = {}
    for e in entities_with_normalized:
        entity_type = e["type"]
        by_type.setdefault(entity_type, []).append(e)

    canonical_entities: list[dict] = []

    for entity_type, entities in by_type.items():
        # seen: normalized_name -> canonical entity dict
        seen: dict[str, dict] = {}

        for entity in entities:
            normalized = entity["_normalized"]
            matched_key = None

            # Check against all existing canonical entities
            for canonical_key in seen:
                similarity = fuzz.token_set_ratio(normalized, canonical_key)
                if similarity >= SIMILARITY_THRESHOLD:
                    matched_key = canonical_key
                    break

            if matched_key is not None:
                # Merge: keep higher confidence
                existing = seen[matched_key]
                if entity["confidence"] > existing["confidence"]:
                    # Replace with higher-confidence version, keep same key
                    seen[matched_key] = {**entity}
            else:
                # New canonical entity
                seen[normalized] = {**entity}

        # Strip internal _normalized key before returning
        for canonical in seen.values():
            canonical_copy = {k: v for k, v in canonical.items() if k != "_normalized"}
            canonical_entities.append(canonical_copy)

    return canonical_entities
```

Run deduplicator tests immediately:
`pytest tests/test_deduplicator.py -x -q --tb=short`

All 5 tests must pass GREEN.
  </action>

  <verify>
    <automated>cd "C:\Users\2171176\Documents\Python\Knowledge_Graph_v2" && python -m pytest tests/test_deduplicator.py -v --tb=short 2>&1 | tail -15</automated>
  </verify>

  <acceptance_criteria>
    - `pytest tests/test_deduplicator.py -v` shows 5 PASSED (not xfail)
    - `grep "from rapidfuzz import fuzz" src/graph/deduplicator.py` exits 0
    - `grep "SIMILARITY_THRESHOLD" src/graph/deduplicator.py` exits 0
    - `grep "_LEGAL_SUFFIX_RE" src/graph/deduplicator.py` exits 0
    - `python -c "from src.graph.deduplicator import normalize_entity_name; print(normalize_entity_name('Tesla Inc.'))"` prints "Tesla"
    - `python -c "from src.graph.deduplicator import normalize_entity_name; print(normalize_entity_name('Bosch GmbH'))"` prints "Bosch"
  </acceptance_criteria>

  <done>normalize_entity_name() handles legal suffix removal, title case, punctuation strip; deduplicate_entities() merges variants by type using token_set_ratio >= 85; all 5 deduplicator tests green</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement create_graph_schema(), upsert_entity(), insert_relationships(), query_entity() in db_manager.py</name>
  <files>src/graph/db_manager.py</files>

  <read_first>
    - src/graph/db_manager.py (current stub — understand function signatures)
    - tests/test_kuzu_db.py (ALL 7 tests — understand KuzuDB instantiation pattern, tmp_path usage, upsert idempotency)
    - .planning/phases/03-knowledge-graph-construction/03-RESEARCH.md (Pattern 3: full KuzuDB schema DDL, node/rel table definitions, MERGE pattern, Pitfall 6 and 7 notes)
  </read_first>

  <behavior>
    - Test 1 (test_create_schema_idempotent): kuzu.Database(tmp_path/"test.db"); create_graph_schema twice; no exception
    - Test 2 (test_insert_entity_oem): upsert_entity(db, {"name": "Toyota", "type": "OEM", "confidence": 0.95}); no exception
    - Test 3 (test_insert_entity_supplier): upsert_entity(db, {"name": "Bosch", "type": "Supplier", "confidence": 0.9}); no exception
    - Test 4 (test_query_entity_returns_dict): after upsert BMW/OEM; query_entity(db, "BMW", "OEM") returns dict with canonical_name="BMW"
    - Test 5 (test_query_entity_missing_returns_none): query_entity(db, "NonExistentCorp", "OEM") returns None
    - Test 6 (test_upsert_entity_no_duplicate): upsert BMW/OEM twice; kuzu.Connection(db).execute("MATCH (n:OEM {canonical_name: 'Tesla'}) RETURN COUNT(n)") returns 1
    - Test 7 (test_insert_relationship_uses): upsert BMW/OEM and LiDAR/Technology; insert_relationships with USES; no exception
  </behavior>

  <action>
Replace the entire contents of src/graph/db_manager.py with the following implementation:

```python
"""KuzuDB graph schema creation and entity/relationship management.

Creates node and relationship tables for the automotive knowledge graph. All operations
use kuzu.Connection (not db.execute directly). Schema creation is idempotent. Entity
upsert uses CREATE OR REPLACE to prevent duplicate nodes.

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
_REL_TYPE_MAP: dict[str, str] = {
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
            - confidence (float): Confidence score 0.0–1.0

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
    ).fetchall()

    if not result:
        return None

    row = result[0]
    return {"canonical_name": row["canonical_name"], "confidence": row["confidence"]}
```

Run KuzuDB tests immediately after writing:
`pytest tests/test_kuzu_db.py -x -q --tb=short`

All 7 tests must pass GREEN.
  </action>

  <verify>
    <automated>cd "C:\Users\2171176\Documents\Python\Knowledge_Graph_v2" && python -m pytest tests/test_kuzu_db.py -v --tb=short 2>&1 | tail -20</automated>
  </verify>

  <acceptance_criteria>
    - `pytest tests/test_kuzu_db.py -v` shows 7 PASSED (not xfail)
    - `grep "import kuzu" src/graph/db_manager.py` exits 0
    - `grep "kuzu.Connection" src/graph/db_manager.py` exits 0
    - `grep "IF NOT EXISTS" src/graph/db_manager.py` exits 0
    - `grep "MERGE" src/graph/db_manager.py` exits 0
    - `python -c "from src.graph.db_manager import create_graph_schema, upsert_entity, insert_relationships, query_entity; print('OK')"` exits 0
    - Full test suite still green: `pytest tests/ -x -q -k "not lm_studio and not integration"` exits 0
  </acceptance_criteria>

  <done>create_graph_schema() creates all 5 node tables and relationship tables idempotently; upsert_entity() uses MERGE to prevent duplicates; query_entity() returns dict or None; all 7 kuzu_db tests green</done>
</task>

</tasks>

<verification>
```bash
# Deduplicator tests (5 green)
pytest tests/test_deduplicator.py -v --tb=short

# KuzuDB tests (7 green)
pytest tests/test_kuzu_db.py -v --tb=short

# Full suite still green
pytest tests/ -x -q -k "not lm_studio and not integration" --tb=short
```
</verification>

<success_criteria>
- 5 deduplicator tests pass GREEN
- 7 KuzuDB tests pass GREEN
- normalize_entity_name() removes legal suffixes, converts to title case, strips punctuation except hyphens
- deduplicate_entities() merges by type using token_set_ratio >= 85; empty input returns []
- create_graph_schema() is idempotent; upsert_entity() uses MERGE; query_entity() returns None for missing
- All prior Phase 1+2 tests still green
</success_criteria>

<output>
After completion, create `.planning/phases/03-knowledge-graph-construction/03-03-SUMMARY.md`
</output>
