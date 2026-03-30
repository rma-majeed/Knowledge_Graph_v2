---
phase: 03-knowledge-graph-construction
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - requirements.txt
  - tests/test_graph_extraction.py
  - tests/test_deduplicator.py
  - tests/test_kuzu_db.py
  - tests/test_citations.py
  - src/graph/__init__.py
  - src/graph/extractor.py
  - src/graph/deduplicator.py
  - src/graph/db_manager.py
  - src/graph/citations.py
  - src/graph/monitor.py
  - data/kuzu_db/.gitkeep
  - .gitignore
autonomous: true
requirements:
  - GRAPH-01
  - GRAPH-02
  - GRAPH-03
  - GRAPH-04

must_haves:
  truths:
    - "pytest tests/test_graph_extraction.py tests/test_deduplicator.py tests/test_kuzu_db.py tests/test_citations.py -x -q collects all stubs and reports xfail (not errors)"
    - "All src/graph/*.py files exist and raise NotImplementedError when called"
    - "kuzu and rapidfuzz are in requirements.txt and importable"
    - "data/kuzu_db/ directory is created and .gitignored"
  artifacts:
    - path: "tests/test_graph_extraction.py"
      provides: "xfail stubs for GRAPH-01 (extraction, type validation, confidence threshold)"
    - path: "tests/test_deduplicator.py"
      provides: "xfail stubs for GRAPH-02 (fuzzy dedup, legal suffix removal, normalization)"
    - path: "tests/test_kuzu_db.py"
      provides: "xfail stubs for GRAPH-03 (schema idempotent, insert, query)"
    - path: "tests/test_citations.py"
      provides: "xfail stubs for GRAPH-04 (insert citation, get chunks for entity)"
    - path: "src/graph/extractor.py"
      provides: "NotImplementedError stub for EntityExtractor"
    - path: "src/graph/deduplicator.py"
      provides: "NotImplementedError stub for EntityDeduplicator"
    - path: "src/graph/db_manager.py"
      provides: "NotImplementedError stub for GraphDBManager"
    - path: "src/graph/citations.py"
      provides: "NotImplementedError stub for CitationStore"
    - path: "src/graph/monitor.py"
      provides: "NotImplementedError stub for GraphMonitor"
  key_links:
    - from: "tests/test_graph_extraction.py"
      to: "src/graph/extractor.py"
      via: "import from src.graph.extractor"
      pattern: "from src.graph.extractor import"
    - from: "tests/test_deduplicator.py"
      to: "src/graph/deduplicator.py"
      via: "import from src.graph.deduplicator"
      pattern: "from src.graph.deduplicator import"
    - from: "tests/test_kuzu_db.py"
      to: "src/graph/db_manager.py"
      via: "import from src.graph.db_manager"
      pattern: "from src.graph.db_manager import"
    - from: "tests/test_citations.py"
      to: "src/graph/citations.py"
      via: "import from src.graph.citations"
      pattern: "from src.graph.citations import"
---

<objective>
Create the Wave 0 test scaffold and src/graph package stubs for Phase 3 Knowledge Graph Construction.

Purpose: Establish Nyquist-compliant test stubs (xfail) and NotImplementedError source stubs before implementation begins. This pattern matches Phase 1 and Phase 2 Wave 0 plans exactly. Stubs auto-pass once implementations land.

Output: 4 test files with xfail stubs, 5 src/graph module stubs, requirements.txt updated with kuzu + rapidfuzz, data/kuzu_db directory created and gitignored.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/03-knowledge-graph-construction/03-VALIDATION.md

<interfaces>
<!-- Established patterns to replicate from Phase 2 Wave 0 -->
<!-- tests/test_embedding.py (Phase 2 xfail pattern) -->

xfail stub pattern:
```python
@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_example() -> None:
    """Docstring describing what will be tested."""
    from unittest.mock import MagicMock
    # import from src.graph.extractor import ExtractEntities  (causes ImportError -> xfail)
    raise NotImplementedError
```

NotImplementedError stub pattern (src/graph/extractor.py):
```python
"""Stub — Phase 3 plan 02 implements this."""
def extract_entities_relationships(chunk_texts, client):
    raise NotImplementedError
```

lm_studio marker: tests requiring LM Studio get @pytest.mark.lm_studio
conftest.py already registers "integration" marker — lm_studio must also be registered
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Install kuzu + rapidfuzz and create src/graph package stubs</name>
  <files>requirements.txt, src/graph/__init__.py, src/graph/extractor.py, src/graph/deduplicator.py, src/graph/db_manager.py, src/graph/citations.py, src/graph/monitor.py, data/kuzu_db/.gitkeep, .gitignore</files>

  <read_first>
    - requirements.txt (append to existing, do not overwrite existing entries)
    - src/embed/embedder.py (see existing stub pattern to replicate in extractor.py)
    - tests/conftest.py (see existing marker registration — add lm_studio marker here)
  </read_first>

  <action>
1. Append to requirements.txt (do not remove existing lines):
   ```
   # Knowledge graph
   kuzu>=0.11.3
   rapidfuzz>=3.14.0
   ```

2. Run: `pip install "kuzu>=0.11.3" "rapidfuzz>=3.14.0"`

3. Verify install: `python -c "import kuzu; import rapidfuzz; print('kuzu', kuzu.__version__, 'rapidfuzz', rapidfuzz.__version__)"`

4. Create src/graph/__init__.py (empty package marker, one line only):
   ```python
   """Knowledge graph construction package — Phase 3."""
   ```

5. Create src/graph/extractor.py stub:
   ```python
   """Entity/relationship extraction via LM Studio LLM — Phase 3 plan 02 implements this.

   Public API (stubs):
       extract_entities_relationships(chunk_texts: list[str], client) -> dict
           Returns {"entities": [...], "relationships": [...]}
   """
   from __future__ import annotations

   ENTITY_TYPES = {"OEM", "Supplier", "Technology", "Product", "Recommendation"}
   CONFIDENCE_THRESHOLD = 0.7
   BATCH_SIZE = 8


   def extract_entities_relationships(chunk_texts: list[str], client) -> dict:
       """Extract entities and relationships from chunk texts via LM Studio LLM."""
       raise NotImplementedError
   ```

6. Create src/graph/deduplicator.py stub:
   ```python
   """Entity deduplication via RapidFuzz fuzzy matching — Phase 3 plan 03 implements this.

   Public API (stubs):
       normalize_entity_name(name: str) -> str
       deduplicate_entities(extracted_entities: list[dict]) -> list[dict]
   """
   from __future__ import annotations

   SIMILARITY_THRESHOLD = 85  # token_set_ratio >= 85 to merge


   def normalize_entity_name(name: str) -> str:
       """Normalize entity name: title case, strip legal suffixes, remove punctuation."""
       raise NotImplementedError


   def deduplicate_entities(extracted_entities: list[dict]) -> list[dict]:
       """Merge duplicate entities by type using fuzzy matching."""
       raise NotImplementedError
   ```

7. Create src/graph/db_manager.py stub:
   ```python
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
   ```

8. Create src/graph/citations.py stub:
   ```python
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
   ```

9. Create src/graph/monitor.py stub:
   ```python
   """Graph explosion detection and entity density monitoring — Phase 3 plan 04 implements this.

   Public API (stubs):
       check_entity_density(db, doc_count: int, chunk_count: int) -> dict
           Returns {"entity_count": int, "density_per_doc": float, "alert": bool, "reason": str|None}
   """
   from __future__ import annotations


   MAX_ENTITIES_PER_DOC = 50
   MAX_TOTAL_ENTITIES = 10_000


   def check_entity_density(db, doc_count: int, chunk_count: int) -> dict:
       """Check entity density metrics for graph explosion warning signs."""
       raise NotImplementedError
   ```

10. Create data/kuzu_db/.gitkeep:
    ```
    ```
    (empty file — creates directory placeholder)

11. Append to .gitignore (read first to avoid duplicates):
    ```
    # KuzuDB graph data
    data/kuzu_db/
    ```
    Only add if `data/kuzu_db/` is not already present in .gitignore.

12. Add lm_studio marker to tests/conftest.py in the pytest_configure() function — append after the existing "integration" marker line:
    ```python
    config.addinivalue_line(
        "markers", "lm_studio: marks tests that require LM Studio running locally"
    )
    ```
  </action>

  <verify>
    <automated>python -c "import kuzu; import rapidfuzz; print('OK')" && grep "kuzu>=0.11.3" requirements.txt && grep "rapidfuzz>=3.14.0" requirements.txt && python -c "from src.graph.extractor import extract_entities_relationships; print('extractor OK')" && python -c "from src.graph.deduplicator import normalize_entity_name; print('dedup OK')" && python -c "from src.graph.db_manager import create_graph_schema; print('db_manager OK')" && python -c "from src.graph.citations import CitationStore; print('citations OK')" && python -c "from src.graph.monitor import check_entity_density; print('monitor OK')"</automated>
  </verify>

  <acceptance_criteria>
    - `grep "kuzu>=0.11.3" requirements.txt` exits 0
    - `grep "rapidfuzz>=3.14.0" requirements.txt` exits 0
    - `python -c "import kuzu"` exits 0 without ImportError
    - `python -c "import rapidfuzz"` exits 0 without ImportError
    - `python -c "from src.graph.extractor import ENTITY_TYPES, CONFIDENCE_THRESHOLD"` exits 0
    - `python -c "from src.graph.deduplicator import SIMILARITY_THRESHOLD"` exits 0
    - `python -c "from src.graph.citations import CitationStore"` exits 0
    - All 5 src/graph/*.py files exist (ls src/graph/ shows extractor.py, deduplicator.py, db_manager.py, citations.py, monitor.py)
    - `grep "data/kuzu_db/" .gitignore` exits 0
    - `grep "lm_studio" tests/conftest.py` exits 0
  </acceptance_criteria>

  <done>kuzu and rapidfuzz installed and in requirements.txt; all 5 src/graph modules exist with NotImplementedError stubs; data/kuzu_db directory created and gitignored; lm_studio marker registered in conftest.py</done>
</task>

<task type="auto">
  <name>Task 2: Create xfail test stubs for all graph test files</name>
  <files>tests/test_graph_extraction.py, tests/test_deduplicator.py, tests/test_kuzu_db.py, tests/test_citations.py</files>

  <read_first>
    - tests/test_embedding.py (exact xfail stub pattern to replicate — every stub follows this format)
    - tests/conftest.py (available fixtures: tmp_db_conn, tmp_db_path, tmp_path)
    - .planning/phases/03-knowledge-graph-construction/03-VALIDATION.md (complete list of required test names and their requirement mapping)
    - src/graph/extractor.py (imports the test will use)
    - src/graph/deduplicator.py (imports the test will use)
    - src/graph/db_manager.py (imports the test will use)
    - src/graph/citations.py (imports the test will use)
  </read_first>

  <action>
Create 4 test files. All stubs use `@pytest.mark.xfail(strict=False, reason="not implemented yet")`.
All imports are inside the test body (not module level) so ImportError triggers xfail, not collection error.

**tests/test_graph_extraction.py:**
```python
"""Tests for Phase 3: Entity/Relationship Extraction (GRAPH-01).

Wave 0 stubs — all xfail until plan 03-02 fills them in.

Unit tests (no LM Studio required — mock client):
  - test_extract_entities_from_chunk
  - test_entity_type_validation
  - test_confidence_threshold
  - test_extract_relationships_from_chunk
  - test_extract_returns_empty_on_no_entities
  - test_batch_size_8_chunks_max

Integration tests (requires LM Studio running):
  - test_real_lm_studio_extraction
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# GRAPH-01: extract_entities_relationships() via LM Studio
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_extract_entities_from_chunk() -> None:
    """extract_entities_relationships() returns entities list with name/type/confidence."""
    from unittest.mock import MagicMock
    from src.graph.extractor import extract_entities_relationships

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = (
        '{"entities": [{"name": "Toyota", "type": "OEM", "confidence": 0.95}], "relationships": []}'
    )
    mock_client.chat.completions.create.return_value = mock_response

    result = extract_entities_relationships(["Toyota announced new EV lineup."], mock_client)

    assert "entities" in result
    assert "relationships" in result
    assert len(result["entities"]) >= 1
    assert result["entities"][0]["name"] == "Toyota"
    assert result["entities"][0]["type"] == "OEM"
    assert result["entities"][0]["confidence"] >= 0.7


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_entity_type_validation() -> None:
    """extract_entities_relationships() drops entities not in ENTITY_TYPES whitelist."""
    from unittest.mock import MagicMock
    from src.graph.extractor import extract_entities_relationships, ENTITY_TYPES

    mock_client = MagicMock()
    mock_response = MagicMock()
    # LLM returns an invalid type "Person" — should be filtered out
    mock_response.choices[0].message.content = (
        '{"entities": ['
        '{"name": "John Smith", "type": "Person", "confidence": 0.9},'
        '{"name": "Bosch", "type": "Supplier", "confidence": 0.85}'
        '], "relationships": []}'
    )
    mock_client.chat.completions.create.return_value = mock_response

    result = extract_entities_relationships(["John Smith from Bosch presented."], mock_client)

    entity_types = {e["type"] for e in result["entities"]}
    assert entity_types.issubset(ENTITY_TYPES), f"Invalid types found: {entity_types - ENTITY_TYPES}"
    assert any(e["name"] == "Bosch" for e in result["entities"])


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_confidence_threshold() -> None:
    """extract_entities_relationships() drops entities with confidence < 0.7."""
    from unittest.mock import MagicMock
    from src.graph.extractor import extract_entities_relationships, CONFIDENCE_THRESHOLD

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = (
        '{"entities": ['
        '{"name": "Tesla", "type": "OEM", "confidence": 0.9},'
        '{"name": "Unknown Corp", "type": "OEM", "confidence": 0.5}'
        '], "relationships": []}'
    )
    mock_client.chat.completions.create.return_value = mock_response

    result = extract_entities_relationships(["Tesla and Unknown Corp discussed EVs."], mock_client)

    low_conf = [e for e in result["entities"] if e["confidence"] < CONFIDENCE_THRESHOLD]
    assert low_conf == [], f"Low-confidence entities leaked through: {low_conf}"


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_extract_relationships_from_chunk() -> None:
    """extract_entities_relationships() returns relationships list with source/target/type."""
    from unittest.mock import MagicMock
    from src.graph.extractor import extract_entities_relationships

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = (
        '{"entities": ['
        '{"name": "BMW", "type": "OEM", "confidence": 0.95},'
        '{"name": "LiDAR", "type": "Technology", "confidence": 0.88}'
        '], "relationships": ['
        '{"source_name": "BMW", "target_name": "LiDAR", "type": "USES"}'
        ']}'
    )
    mock_client.chat.completions.create.return_value = mock_response

    result = extract_entities_relationships(["BMW uses LiDAR for autonomous driving."], mock_client)

    assert len(result["relationships"]) >= 1
    rel = result["relationships"][0]
    assert "source_name" in rel
    assert "target_name" in rel
    assert "type" in rel


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_extract_returns_empty_on_no_entities() -> None:
    """extract_entities_relationships() returns empty lists when LLM finds no entities."""
    from unittest.mock import MagicMock
    from src.graph.extractor import extract_entities_relationships

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = '{"entities": [], "relationships": []}'
    mock_client.chat.completions.create.return_value = mock_response

    result = extract_entities_relationships(["This is a generic text with no named entities."], mock_client)

    assert result["entities"] == []
    assert result["relationships"] == []


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_batch_size_8_chunks_max() -> None:
    """extract_entities_relationships() accepts up to 8 chunks in a single call."""
    from unittest.mock import MagicMock
    from src.graph.extractor import extract_entities_relationships

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = '{"entities": [], "relationships": []}'
    mock_client.chat.completions.create.return_value = mock_response

    chunks = [f"Chunk {i} about automotive industry." for i in range(8)]
    result = extract_entities_relationships(chunks, mock_client)

    mock_client.chat.completions.create.assert_called_once()
    assert "entities" in result


@pytest.mark.lm_studio
@pytest.mark.xfail(strict=False, reason="requires LM Studio running")
def test_real_lm_studio_extraction() -> None:
    """Integration: extract_entities_relationships() calls real LM Studio and returns valid JSON."""
    from openai import OpenAI
    from src.graph.extractor import extract_entities_relationships

    client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
    result = extract_entities_relationships(
        ["Toyota and Bosch are collaborating on battery technology for next-generation EVs."],
        client,
    )

    assert "entities" in result
    assert "relationships" in result
    assert all("name" in e and "type" in e and "confidence" in e for e in result["entities"])
```

**tests/test_deduplicator.py:**
```python
"""Tests for Phase 3: Entity Deduplication (GRAPH-02).

Wave 0 stubs — all xfail until plan 03-03 fills them in.

Unit tests:
  - test_normalize_name_title_case
  - test_normalize_name_removes_legal_suffixes
  - test_normalize_name_strips_punctuation
  - test_fuzzy_dedup_merges_variants
  - test_fuzzy_dedup_preserves_different_entities
  - test_fuzzy_dedup_groups_by_type
  - test_fuzzy_dedup_empty_input
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# GRAPH-02: normalize_entity_name() normalization
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_normalize_name_title_case() -> None:
    """normalize_entity_name() converts to title case."""
    from src.graph.deduplicator import normalize_entity_name

    assert normalize_entity_name("toyota motor corporation") == "Toyota Motor Corporation"
    assert normalize_entity_name("BOSCH") == "Bosch"


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_normalize_name_removes_legal_suffixes() -> None:
    """normalize_entity_name() strips Inc., LLC, Corp., Ltd., GmbH, AG, SA, SARL, BV."""
    from src.graph.deduplicator import normalize_entity_name

    cases = [
        ("Tesla Inc.", "Tesla"),
        ("Toyota Motor Corp.", "Toyota Motor"),
        ("Bosch GmbH", "Bosch"),
        ("Continental AG", "Continental"),
        ("Valeo SA", "Valeo"),
        ("Aptiv LLC", "Aptiv"),
    ]
    for input_name, expected in cases:
        result = normalize_entity_name(input_name)
        assert result == expected, f"normalize_entity_name({input_name!r}) = {result!r}, expected {expected!r}"


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_normalize_name_strips_punctuation() -> None:
    """normalize_entity_name() removes punctuation except hyphens."""
    from src.graph.deduplicator import normalize_entity_name

    assert normalize_entity_name("Tesla, Inc.") == "Tesla"
    assert normalize_entity_name("Tier-1 Supplier") == "Tier-1 Supplier"


# ---------------------------------------------------------------------------
# GRAPH-02: deduplicate_entities() fuzzy merging
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_fuzzy_dedup_merges_variants() -> None:
    """deduplicate_entities() merges surface form variants of the same entity."""
    from src.graph.deduplicator import deduplicate_entities

    entities = [
        {"name": "Toyota", "type": "OEM", "confidence": 0.9},
        {"name": "Toyota Inc.", "type": "OEM", "confidence": 0.85},
        {"name": "Toyota Motor Corp.", "type": "OEM", "confidence": 0.8},
    ]
    result = deduplicate_entities(entities)

    assert len(result) == 1, f"Expected 1 canonical entity, got {len(result)}: {result}"
    assert result[0]["confidence"] == 0.9  # Highest confidence kept


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_fuzzy_dedup_preserves_different_entities() -> None:
    """deduplicate_entities() does NOT merge genuinely different entities."""
    from src.graph.deduplicator import deduplicate_entities

    entities = [
        {"name": "Toyota", "type": "OEM", "confidence": 0.9},
        {"name": "Honda", "type": "OEM", "confidence": 0.88},
        {"name": "Bosch", "type": "Supplier", "confidence": 0.85},
    ]
    result = deduplicate_entities(entities)

    names = {e["name"] for e in result}
    assert len(result) == 3, f"Expected 3 entities, got {len(result)}: {result}"


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_fuzzy_dedup_groups_by_type() -> None:
    """deduplicate_entities() does NOT merge same-name entities of different types."""
    from src.graph.deduplicator import deduplicate_entities

    # "EV" as Technology vs "EV" as Product — should NOT merge
    entities = [
        {"name": "EV", "type": "Technology", "confidence": 0.9},
        {"name": "EV", "type": "Product", "confidence": 0.85},
    ]
    result = deduplicate_entities(entities)

    assert len(result) == 2, f"Expected 2 entities (different types), got {len(result)}"


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_fuzzy_dedup_empty_input() -> None:
    """deduplicate_entities() returns empty list for empty input."""
    from src.graph.deduplicator import deduplicate_entities

    result = deduplicate_entities([])
    assert result == []
```

**tests/test_kuzu_db.py:**
```python
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
    result = conn.execute("MATCH (n:OEM {canonical_name: 'Tesla'}) RETURN COUNT(n) AS cnt").fetchall()
    assert result[0]["cnt"] == 1


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
```

**tests/test_citations.py:**
```python
"""Tests for Phase 3: Entity-Chunk Citations (GRAPH-04).

Wave 0 stubs — all xfail until plan 03-04 fills them in.

Unit tests (tmp_db_conn SQLite fixture):
  - test_init_schema_creates_table
  - test_insert_chunk_citation
  - test_insert_duplicate_citation_ignored
  - test_get_chunks_for_entity
  - test_get_chunks_for_entity_empty
"""
from __future__ import annotations

import sqlite3
import pytest


# ---------------------------------------------------------------------------
# GRAPH-04: CitationStore bridge table
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_init_schema_creates_table(tmp_db_conn) -> None:
    """CitationStore.init_schema() creates the chunk_citations table."""
    from src.graph.citations import CitationStore

    # First need the chunks and documents tables for FK constraint
    tmp_db_conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            file_hash TEXT NOT NULL UNIQUE,
            doc_type TEXT NOT NULL,
            total_pages INTEGER
        );
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            page_num INTEGER,
            chunk_index INTEGER,
            chunk_text TEXT NOT NULL,
            token_count INTEGER,
            embedding_flag INTEGER DEFAULT 0
        );
    """)
    store = CitationStore(tmp_db_conn)
    store.init_schema()

    tables = tmp_db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='chunk_citations'"
    ).fetchone()
    assert tables is not None, "chunk_citations table was not created"


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_insert_chunk_citation(tmp_db_conn) -> None:
    """CitationStore.insert_citations() inserts entity-chunk mapping rows."""
    from src.graph.citations import CitationStore

    tmp_db_conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            file_hash TEXT NOT NULL UNIQUE,
            doc_type TEXT NOT NULL,
            total_pages INTEGER
        );
        INSERT INTO documents (filename, file_hash, doc_type, total_pages)
            VALUES ('report.pdf', 'abc123', 'pdf', 5);
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            page_num INTEGER,
            chunk_index INTEGER,
            chunk_text TEXT NOT NULL,
            token_count INTEGER,
            embedding_flag INTEGER DEFAULT 0
        );
        INSERT INTO chunks (doc_id, page_num, chunk_index, chunk_text, token_count)
            VALUES (1, 1, 0, 'Toyota announced EV plans.', 10);
    """)

    store = CitationStore(tmp_db_conn)
    store.init_schema()
    store.insert_citations([
        {"entity_canonical_name": "Toyota", "entity_type": "OEM", "chunk_id": 1}
    ])

    row = tmp_db_conn.execute(
        "SELECT * FROM chunk_citations WHERE entity_canonical_name = 'Toyota'"
    ).fetchone()
    assert row is not None


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_insert_duplicate_citation_ignored(tmp_db_conn) -> None:
    """CitationStore.insert_citations() uses INSERT OR IGNORE — no duplicate error."""
    from src.graph.citations import CitationStore

    tmp_db_conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            file_hash TEXT NOT NULL UNIQUE,
            doc_type TEXT NOT NULL,
            total_pages INTEGER
        );
        INSERT INTO documents (filename, file_hash, doc_type, total_pages)
            VALUES ('report.pdf', 'abc123', 'pdf', 5);
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            page_num INTEGER,
            chunk_index INTEGER,
            chunk_text TEXT NOT NULL,
            token_count INTEGER,
            embedding_flag INTEGER DEFAULT 0
        );
        INSERT INTO chunks (doc_id, page_num, chunk_index, chunk_text, token_count)
            VALUES (1, 1, 0, 'Toyota EV.', 5);
    """)

    store = CitationStore(tmp_db_conn)
    store.init_schema()
    citation = {"entity_canonical_name": "Toyota", "entity_type": "OEM", "chunk_id": 1}
    store.insert_citations([citation])
    store.insert_citations([citation])  # Second insert — must not raise

    count = tmp_db_conn.execute(
        "SELECT COUNT(*) FROM chunk_citations WHERE entity_canonical_name = 'Toyota'"
    ).fetchone()[0]
    assert count == 1


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_get_chunks_for_entity(tmp_db_conn) -> None:
    """CitationStore.get_chunks_for_entity() returns list of chunk dicts with doc metadata."""
    from src.graph.citations import CitationStore

    tmp_db_conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            file_hash TEXT NOT NULL UNIQUE,
            doc_type TEXT NOT NULL,
            total_pages INTEGER
        );
        INSERT INTO documents (filename, file_hash, doc_type, total_pages)
            VALUES ('report.pdf', 'abc123', 'pdf', 5);
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            page_num INTEGER,
            chunk_index INTEGER,
            chunk_text TEXT NOT NULL,
            token_count INTEGER,
            embedding_flag INTEGER DEFAULT 0
        );
        INSERT INTO chunks (doc_id, page_num, chunk_index, chunk_text, token_count)
            VALUES (1, 2, 0, 'Toyota announced new battery tech.', 8);
    """)

    store = CitationStore(tmp_db_conn)
    store.init_schema()
    store.insert_citations([
        {"entity_canonical_name": "Toyota", "entity_type": "OEM", "chunk_id": 1}
    ])

    results = store.get_chunks_for_entity("Toyota", "OEM")

    assert len(results) == 1
    assert results[0]["chunk_id"] == 1
    assert results[0]["filename"] == "report.pdf"
    assert results[0]["page_num"] == 2


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_get_chunks_for_entity_empty(tmp_db_conn) -> None:
    """CitationStore.get_chunks_for_entity() returns empty list for unknown entity."""
    from src.graph.citations import CitationStore

    tmp_db_conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            file_hash TEXT NOT NULL UNIQUE,
            doc_type TEXT NOT NULL,
            total_pages INTEGER
        );
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            page_num INTEGER,
            chunk_index INTEGER,
            chunk_text TEXT NOT NULL,
            token_count INTEGER,
            embedding_flag INTEGER DEFAULT 0
        );
    """)

    store = CitationStore(tmp_db_conn)
    store.init_schema()

    results = store.get_chunks_for_entity("NonExistentEntity", "OEM")
    assert results == []
```
  </action>

  <verify>
    <automated>cd "C:\Users\2171176\Documents\Python\Knowledge_Graph_v2" && python -m pytest tests/test_graph_extraction.py tests/test_deduplicator.py tests/test_kuzu_db.py tests/test_citations.py -v --tb=short -k "not lm_studio" 2>&1 | tail -20</automated>
  </verify>

  <acceptance_criteria>
    - pytest collects all 4 test files without collection errors (ImportError in test body causes xfail, not error)
    - All tests report as XFAIL (not ERROR or FAILED)
    - `pytest tests/test_graph_extraction.py tests/test_deduplicator.py tests/test_kuzu_db.py tests/test_citations.py -q -k "not lm_studio"` exits 0
    - Test count: at least 22 tests collected (6 extraction + 5 dedup + 7 kuzu + 5 citations = 23)
    - No test marked as ERROR in the output (errors = broken stubs)
    - `grep "xfail" tests/test_graph_extraction.py` exits 0
    - `grep "xfail" tests/test_deduplicator.py` exits 0
    - `grep "xfail" tests/test_kuzu_db.py` exits 0
    - `grep "xfail" tests/test_citations.py` exits 0
  </acceptance_criteria>

  <done>All 4 test files created with xfail stubs; pytest collects and reports all stubs as xfail (not error); test scaffold is ready for Wave 2 implementations to turn green</done>
</task>

</tasks>

<verification>
After both tasks complete:

```bash
# Verify package structure
ls src/graph/

# Verify install
python -c "import kuzu; import rapidfuzz; print('deps OK')"

# Verify all stubs xfail (no errors)
pytest tests/test_graph_extraction.py tests/test_deduplicator.py tests/test_kuzu_db.py tests/test_citations.py -v -k "not lm_studio" --tb=short

# Verify existing tests still pass
pytest tests/ -x -q -k "not lm_studio and not integration" --tb=short
```

Expected result: All 23 graph stubs xfail, 0 errors, all prior Phase 1+2 tests still green.
</verification>

<success_criteria>
- kuzu>=0.11.3 and rapidfuzz>=3.14.0 in requirements.txt and importable
- src/graph/ package exists with 5 stub modules (extractor, deduplicator, db_manager, citations, monitor)
- 4 test files (test_graph_extraction.py, test_deduplicator.py, test_kuzu_db.py, test_citations.py) collected by pytest
- All graph stubs report xfail — zero errors, zero unexpected failures
- data/kuzu_db/ created; data/kuzu_db/ in .gitignore
- lm_studio marker registered in conftest.py
- Full test suite still green (prior phases unaffected)
</success_criteria>

<output>
After completion, create `.planning/phases/03-knowledge-graph-construction/03-01-SUMMARY.md`
</output>
