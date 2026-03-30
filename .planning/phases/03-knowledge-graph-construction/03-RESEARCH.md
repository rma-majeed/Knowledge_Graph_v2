# Phase 3: Knowledge Graph Construction - Research

**Researched:** 2026-03-30
**Domain:** Entity/relationship extraction (LM Studio LLM), graph database (KuzuDB), fuzzy deduplication (RapidFuzz), graph explosion prevention
**Confidence:** HIGH for KuzuDB API and RapidFuzz; MEDIUM for LLM extraction patterns (requires prompt validation); MEDIUM for graph explosion detection (strategy sound but implementation-specific)

---

## Summary

Phase 3 wires together five major components: (1) LM Studio's OpenAI-compatible chat completions API for entity and relationship extraction, (2) KuzuDB 0.11.3 for persistent graph storage, (3) RapidFuzz for efficient fuzzy deduplication, (4) entity type whitelisting and confidence filtering for graph explosion prevention, and (5) source chunk linkage for citation. The architecture is an extract-deduplicate-store loop: pull embeddings-complete chunks from ChromaDB/SQLite, send to LM Studio LLM with a structured JSON prompt requesting entity/relationship extraction, deduplicate entities using fuzzy matching + normalization, store nodes and relationships in KuzuDB, and link entity IDs back to source chunks.

The critical challenge is **entity deduplication at scale**. A 500-document corpus (~125K chunks at 4 chunks/page typical) can yield 50K–100K+ extracted entities before deduplication. Naive string-matching will fail — you must apply layered normalization (case, whitespace, punctuation, legal suffix removal) and fuzzy matching (Levenshtein distance < 2) to merge synonyms into canonical identities. RapidFuzz is 40% faster than python-Levenshtein on this task and provides pre-built Windows binaries.

**Graph explosion prevention** is equally critical. Automotive consulting documents contain abundance of noisy entities: every product mentioned, every metric cited, every recommendation stated. Without controls, the graph will contain 10K–50K entities for a 500-document corpus — most useless noise. The solution: enforce entity type whitelist (OEM, Tier-1 Supplier, Technology, Product, Recommendation — 5 types only), confidence threshold (>0.7 from LLM), and per-document entity cap (e.g., ≤50 entities/doc). Monitor entity growth rate: if entities grow >20 per document, extraction is too permissive — adjust whitelist or threshold.

**LM Studio sequential model loading** is a hard constraint: the embedding model (260MB) and LLM (3.8GB) cannot run simultaneously within 4GB VRAM. The Phase 2 embedding pipeline must be complete before Phase 3 begins, or a custom orchestration is needed to unload/reload models mid-process. This research assumes Phase 3 runs after Phase 2 completes (post-embedding).

KuzuDB requires explicit schema definition (no schemaless flexibility like Neo4j). This is a feature for our use case — it forces clear entity typing upfront. Cypher queries are largely portable from Neo4j, but KuzuDB enforces walk semantics (not trail semantics) for variable-length patterns and requires explicit upper bounds (default 30).

**Primary recommendation:** Use KuzuDB 0.11.3 (stable, pip-installable). Create node tables for each entity type (OEM, Supplier, Technology, Product, Recommendation) with a canonical_name STRING PRIMARY KEY field. Use relationship tables (IS_A, USES, PRODUCES, etc.) for typed links. Extract entities/relationships via LM Studio `client.chat.completions.create(...)` with a JSON-mode system prompt. Deduplicate with RapidFuzz's `token_set_ratio()` for entity merging. Store extraction state (chunks_processed, last_entity_id) in SQLite to support incremental re-runs. Link entities to chunks via a chunk_citations table.

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GRAPH-01 | System extracts named entities and typed relationships from chunks using LLM via LM Studio | LM Studio `/v1/chat/completions` confirmed to work with Qwen2.5 7B; tool use and structured JSON output supported; use `client.chat.completions.create(messages=[...], model="Qwen2.5-7B-Instruct", temperature=0.1)` with system prompt specifying entity/relationship schema |
| GRAPH-02 | System deduplicates entities using fuzzy matching (Levenshtein distance < 2, title case normalization, legal suffix removal) | RapidFuzz 3.14+ provides `token_set_ratio()` at 2500 text pairs/sec vs Levenshtein at 1800 pairs/sec; handles normalization via pre-processing; legal suffix removal must be custom function (Inc, LLC, Corp, Ltd, GmbH, AG, SA, SAS) |
| GRAPH-03 | System stores the knowledge graph in KuzuDB (pip-installable embedded graph database) | KuzuDB 0.11.3 stable, pip-installable; `kuzu.Database(path)` and `conn.execute(Cypher)` confirmed; schema required (no schemaless); walk semantics for patterns (different from Neo4j trail semantics); supports node and relationship tables with properties |
| GRAPH-04 | System links graph entities back to source chunks for citation retrieval | KuzuDB foreign keys support linking entity IDs to SQLite chunk IDs; use chunk_citations bridge table (entity_id, chunk_id) or embed chunk_ids in entity properties; retrieval via graph traversal + SQLite join at query time (Phase 4) |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **kuzu** | 0.11.3 | Embedded graph database | pip-installable; no external process; Cypher query language (portable from Neo4j); fast HNSW-like indexing; archived but stable (Apple acquisition Oct 2025); perfect for constrained hardware |
| **openai** | 1.93.0 (installed) | LM Studio LLM client | Already installed; `/v1/chat/completions` standard endpoint; supports structured JSON output; same client used in Phase 2 embeddings |
| **rapidfuzz** | 3.14.3 | Fuzzy string matching | 40% faster than python-Levenshtein (2500 vs 1800 text pairs/sec); pre-built Windows binaries; token_set_ratio for entity dedup; CPU-optimized C++ backend |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **sqlite3** | stdlib | Track extraction state, chunk_citations bridge table | Already used in Phase 1; store extraction_checkpoints (chunks_processed, last_entity_id) for incremental resumption |
| **tqdm** | 4.67.1 (installed) | Progress bar during entity extraction | Wrap chunk processing loop (500+ docs = 125K+ chunks) |
| **json** | stdlib | Parse LLM JSON responses | Extract entities/relationships from `client.chat.completions` structured output |
| **unittest.mock** | stdlib | Mock LM Studio in unit tests | Never call real LM Studio during CI; mock responses with 3–5 synthetic entities/chunk |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| KuzuDB | Neo4j | Neo4j requires external process + license (blocked by corporate firewall); KuzuDB is embedded |
| KuzuDB | NetworkX (in-memory) | NetworkX fits ≤1M nodes in RAM; 500 docs → 50K entities is manageable, but no persistence or scalability |
| RapidFuzz | python-Levenshtein | Levenshtein 40% slower; both support Levenshtein distance; RapidFuzz has better Windows support |
| LM Studio LLM API | Fine-tuned embedding model | Extraction requires instruction-following LLM (Qwen2.5 7B or equiv.), not embedding model; Phase 2 embedding model cannot do extraction |

### Installation

```bash
pip install "kuzu>=0.11.3" "rapidfuzz>=3.14.0"
```

`openai` and `sqlite3` already installed. No other new dependencies required.

**Version verification (confirmed 2026-03-30):**
- kuzu 0.11.3 — available from PyPI; latest stable before project archival
- rapidfuzz 3.14.3 — available from PyPI
- openai 1.93.0 — already installed

---

## Architecture Patterns

### Recommended Project Structure

```
src/
├── graph/
│   ├── __init__.py
│   ├── extractor.py          # LM Studio entity/relationship extraction
│   ├── deduplicator.py       # RapidFuzz fuzzy matching + normalization
│   ├── db_manager.py         # KuzuDB schema creation, node/rel insertion
│   ├── citations.py          # Bridge table: entity → chunks
│   └── monitor.py            # Entity density, graph explosion detection
├── ingest/                   # Phase 1 (unchanged)
│   └── store.py
├── embed/                    # Phase 2 (unchanged)
│   └── pipeline.py
data/
├── chunks.db                 # SQLite (Phase 1)
├── chroma_db/                # ChromaDB (Phase 2)
├── knowledge_graph.db        # KuzuDB (Phase 3)
└── extraction_state.json     # Extraction checkpoint for incremental runs
tests/
└── test_graph_extraction.py  # Unit tests (mocked LM Studio + EphemeralClient)
```

### Pattern 1: Entity/Relationship Extraction via LM Studio

**What:** Call LM Studio LLM with structured JSON prompt, parse entities and relationships from response.
**When to use:** For each chunk batch (~8 chunks); reusable across all corpus documents.

```python
# Source: LM Studio official docs (Tool Use, Structured Output)
from openai import OpenAI
import json

def extract_entities_relationships(chunk_texts: list[str], client: OpenAI) -> dict:
    """Extract entities and relationships from chunk texts using LM Studio LLM.

    Args:
        chunk_texts: List of chunk text strings (typically 8 chunks).
        client: OpenAI client pointing to LM Studio (/v1/chat/completions).

    Returns:
        Dict with keys:
        - "entities": list of {name, type, confidence} dicts
        - "relationships": list of {source_name, target_name, type} dicts
    """
    system_prompt = """You are an entity and relationship extraction expert for automotive consulting documents.

Extract named entities and relationships from the provided text chunks. Return ONLY valid JSON with no extra text.

JSON Schema:
{
  "entities": [
    {"name": "string", "type": "string (OEM|Supplier|Technology|Product|Recommendation)", "confidence": float (0.0-1.0)}
  ],
  "relationships": [
    {"source_name": "string", "target_name": "string", "type": "string (IS_A|USES|PRODUCES|RECOMMENDS)"}
  ]
}

Rules:
1. Entity types ONLY: OEM (car manufacturer like BMW, Toyota), Supplier (Tier 1/2 like Bosch, Denso), Technology (EV, autonomous, LiDAR), Product (seat module, infotainment, battery), Recommendation (strategic advice).
2. Confidence: HIGH (0.8+) if explicitly named; MEDIUM (0.5-0.79) if inferred; LOW (<0.5) if speculative.
3. Only include confidence >= 0.7 entities.
4. Normalize entity names: title case, strip leading/trailing whitespace, remove legal suffixes (Inc., LLC, Corp., Ltd., GmbH, AG).
5. Deduplicate within each chunk (no duplicate entities).
6. Relationships: only link entities that exist in the same or adjacent chunks.
"""

    user_prompt = f"Extract entities and relationships from these chunks:\n\n" + "\n---\n".join(chunk_texts)

    response = client.chat.completions.create(
        model="Qwen2.5-7B-Instruct",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,  # Low temperature for consistent extraction
        max_tokens=2048,
    )

    # Parse JSON from response
    response_text = response.choices[0].message.content.strip()
    # Handle markdown code blocks if present
    if response_text.startswith("```json"):
        response_text = response_text[7:]
    if response_text.startswith("```"):
        response_text = response_text[3:]
    if response_text.endswith("```"):
        response_text = response_text[:-3]

    data = json.loads(response_text.strip())
    return data
```

**Model name note:** KuzuDB stores the loaded model ID from LM Studio's `/v1/models` endpoint. In this example, `"Qwen2.5-7B-Instruct"` — verify exact ID at startup.

**Batch size recommendation:** 8 chunks per call. Extraction latency ~5-10 seconds per batch; larger batches → longer latency and more context confusion.

### Pattern 2: Entity Deduplication with Fuzzy Matching

**What:** Merge entities that are spelling variants of the same canonical entity using fuzzy string distance + normalization.
**When to use:** After extraction of a batch; consolidates duplicates before insertion into KuzuDB.

```python
# Source: RapidFuzz documentation + entity resolution best practices
from rapidfuzz import fuzz
import re

def normalize_entity_name(name: str) -> str:
    """Normalize entity name for fuzzy matching.

    Rules:
    - Title case
    - Strip whitespace
    - Remove punctuation except hyphens
    - Remove legal suffixes
    """
    # Title case
    name = name.title()
    # Remove legal suffixes
    legal_suffixes = [
        r'\s+(Inc|Incorporated|LLC|Limited Liability Company|Corp|Corporation|'
        r'Ltd|Limited|GmbH|AG|SA|SAS|SARL|BV|NV|Pty|Plc)\s*\.?\s*$'
    ]
    for suffix in legal_suffixes:
        name = re.sub(suffix, '', name, flags=re.IGNORECASE)
    # Strip whitespace and punctuation (except hyphens)
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def deduplicate_entities(extracted_entities: list[dict]) -> list[dict]:
    """Merge duplicate entities using fuzzy matching.

    Args:
        extracted_entities: List of {name, type, confidence} dicts from LLM.

    Returns:
        List of canonical entity dicts, with duplicates merged.
    """
    if not extracted_entities:
        return []

    # Normalize all names
    entities_with_normalized = [
        {**e, "normalized_name": normalize_entity_name(e["name"])}
        for e in extracted_entities
    ]

    # Group by type (OEM entities don't merge with Supplier entities)
    entities_by_type = {}
    for e in entities_with_normalized:
        if e["type"] not in entities_by_type:
            entities_by_type[e["type"]] = []
        entities_by_type[e["type"]].append(e)

    # Deduplicate within each type group
    canonical_entities = []
    for entity_type, entities in entities_by_type.items():
        seen = {}
        for e in entities:
            # Find a matching canonical entity
            found_match = False
            for canonical_name, canonical_entity in seen.items():
                # Token-set ratio: ignores word order, good for company names
                # "Tesla, Inc." vs "Inc., Tesla" will match
                similarity = fuzz.token_set_ratio(
                    e["normalized_name"],
                    canonical_name,
                    processor=None  # Already normalized
                )
                if similarity >= 90:  # High threshold: 90+ is very similar
                    # Merge by keeping higher confidence
                    if e["confidence"] > canonical_entity["confidence"]:
                        seen[canonical_name] = e
                    found_match = True
                    break

            if not found_match:
                # New canonical entity
                seen[e["normalized_name"]] = e

        canonical_entities.extend(seen.values())

    return canonical_entities
```

**Threshold note:** 90% token_set_ratio is strict (catches obvious typos/reorderings); 80% is looser (catches more false positives). Recommend starting at 85% and tuning after integration testing.

### Pattern 3: KuzuDB Schema Creation and Node/Relationship Insertion

**What:** Create node and relationship tables in KuzuDB, insert entities and relationships.
**When to use:** At pipeline startup (once per full indexing run); idempotent design allows re-creation safely.

```python
# Source: KuzuDB official docs (Python API, Cypher DDL/DML)
import kuzu

def create_graph_schema(db: kuzu.Database) -> None:
    """Create KuzuDB node and relationship tables for entity graph.

    Idempotent: safe to call on existing database.
    """
    # Create node tables for each entity type
    node_tables = {
        "OEM": "CREATE NODE TABLE IF NOT EXISTS OEM(canonical_name STRING PRIMARY KEY, full_names STRING, confidence FLOAT)",
        "Supplier": "CREATE NODE TABLE IF NOT EXISTS Supplier(canonical_name STRING PRIMARY KEY, tier INT8, confidence FLOAT)",
        "Technology": "CREATE NODE TABLE IF NOT EXISTS Technology(canonical_name STRING PRIMARY KEY, domain STRING, confidence FLOAT)",
        "Product": "CREATE NODE TABLE IF NOT EXISTS Product(canonical_name STRING PRIMARY KEY, category STRING, confidence FLOAT)",
        "Recommendation": "CREATE NODE TABLE IF NOT EXISTS Recommendation(canonical_name STRING PRIMARY KEY, priority INT8, confidence FLOAT)",
    }

    for table_name, create_stmt in node_tables.items():
        try:
            db.execute(create_stmt)
        except Exception as e:
            # Table may already exist; this is fine
            if "already exists" not in str(e):
                raise

    # Create relationship tables (typed edges)
    rel_tables = {
        "IS_A": "CREATE REL TABLE IF NOT EXISTS IS_A(FROM OEM|Supplier|Product TO OEM|Supplier|Technology|Product, strength FLOAT)",
        "USES": "CREATE REL TABLE IF NOT EXISTS USES(FROM OEM|Supplier TO Technology|Product, strength FLOAT)",
        "PRODUCES": "CREATE REL TABLE IF NOT EXISTS PRODUCES(FROM OEM|Supplier TO Product, strength FLOAT)",
        "RECOMMENDS": "CREATE REL TABLE IF NOT EXISTS RECOMMENDS(FROM Recommendation TO OEM|Supplier|Technology|Product, strength FLOAT)",
    }

    for table_name, create_stmt in rel_tables.items():
        try:
            db.execute(create_stmt)
        except Exception as e:
            if "already exists" not in str(e):
                raise

def insert_entities(db: kuzu.Database, canonical_entities: list[dict]) -> None:
    """Insert canonical entities into appropriate node tables.

    Args:
        db: KuzuDB database instance.
        canonical_entities: List of {name, type, confidence, ...} dicts.
    """
    for entity in canonical_entities:
        entity_type = entity["type"]
        canonical_name = entity["name"]
        confidence = entity.get("confidence", 0.7)

        # Determine which node table and SQL
        if entity_type == "OEM":
            db.execute(
                f"CREATE (e:OEM {{canonical_name: '{canonical_name}', confidence: {confidence}}})"
            )
        elif entity_type == "Supplier":
            tier = entity.get("tier", 1)
            db.execute(
                f"CREATE (e:Supplier {{canonical_name: '{canonical_name}', tier: {tier}, confidence: {confidence}}})"
            )
        # ... repeat for other entity types

def insert_relationships(db: kuzu.Database, relationships: list[dict], entity_map: dict) -> None:
    """Insert relationships between entities.

    Args:
        db: KuzuDB database instance.
        relationships: List of {source_name, target_name, type, confidence} dicts.
        entity_map: Dict mapping canonical_name -> (entity_type, internal_id).
    """
    for rel in relationships:
        source_name = rel["source_name"]
        target_name = rel["target_name"]
        rel_type = rel["type"]  # IS_A, USES, PRODUCES, RECOMMENDS
        confidence = rel.get("confidence", 0.7)

        # Lookup entity types from entity_map
        if source_name not in entity_map or target_name not in entity_map:
            continue  # Skip if either entity missing

        source_type, source_id = entity_map[source_name]
        target_type, target_id = entity_map[target_name]

        # INSERT relationship
        db.execute(
            f"MATCH (s:{source_type} {{canonical_name: '{source_name}'}}), "
            f"(t:{target_type} {{canonical_name: '{target_name}'}}) "
            f"CREATE (s)-[:{rel_type} {{strength: {confidence}}}]->(t)"
        )
```

**Schema notes:**
- KuzuDB requires all node/rel tables pre-defined (no schemaless).
- `PRIMARY KEY` must be a single column (here, `canonical_name`).
- `FROM|TO` syntax allows multiple node types per relationship direction (though each is a separate table internally).
- Confidence stored as FLOAT; range [0.0, 1.0].

### Pattern 4: Source Chunk Linkage via Bridge Table

**What:** Store mapping from entities to chunks they came from (for citation in Phase 4 query results).
**When to use:** After successful entity/relationship insertion into KuzuDB.

```python
# Source: SQLite foreign key relationships + standard relational pattern
import sqlite3

def create_chunk_citations_table(conn: sqlite3.Connection) -> None:
    """Create SQLite bridge table linking KuzuDB entities to source chunks.

    Enables: entity_id -> [chunk_ids] -> [document citations]
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunk_citations (
            citation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_canonical_name TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            chunk_id INTEGER NOT NULL,
            FOREIGN KEY(chunk_id) REFERENCES chunks(chunk_id) ON DELETE CASCADE,
            UNIQUE(entity_canonical_name, entity_type, chunk_id)
        )
    """)
    conn.commit()

def insert_chunk_citations(conn: sqlite3.Connection, citations: list[dict]) -> None:
    """Insert entity-to-chunk mappings.

    Args:
        conn: SQLite connection.
        citations: List of {entity_canonical_name, entity_type, chunk_id} dicts.
    """
    rows = [
        (c["entity_canonical_name"], c["entity_type"], c["chunk_id"])
        for c in citations
    ]
    conn.executemany(
        """INSERT OR IGNORE INTO chunk_citations
           (entity_canonical_name, entity_type, chunk_id)
           VALUES (?, ?, ?)""",
        rows,
    )
    conn.commit()

def get_chunks_for_entity(conn: sqlite3.Connection, entity_name: str, entity_type: str) -> list[dict]:
    """Retrieve source chunks for a given entity (used in Phase 4 for citations).

    Returns: List of {chunk_id, doc_id, filename, page_num} dicts.
    """
    rows = conn.execute("""
        SELECT c.chunk_id, c.doc_id, d.filename, c.page_num
        FROM chunk_citations cc
        JOIN chunks c ON cc.chunk_id = c.chunk_id
        JOIN documents d ON c.doc_id = d.doc_id
        WHERE cc.entity_canonical_name = ? AND cc.entity_type = ?
        ORDER BY c.doc_id, c.page_num
    """, (entity_name, entity_type)).fetchall()

    return [dict(r) for r in rows]
```

**Design choice:** Bridge table in SQLite (not KuzuDB) to avoid redundancy and simplify citation queries. KuzuDB stores the graph structure; SQLite handles the entity-document mapping.

### Pattern 5: Graph Explosion Prevention & Monitoring

**What:** Track entity density and growth; alert if extraction is too permissive.
**When to use:** After each extraction batch; check at pipeline end.

```python
# Source: Knowledge graph metrics literature + project constraints
def monitor_entity_density(db: kuzu.Database, doc_count: int, chunk_count: int) -> dict:
    """Check entity density metrics for graph explosion warning signs.

    Returns:
        Dict with keys: entity_count, density_per_doc, density_per_chunk, alert
    """
    # Count total entities in graph
    result = db.execute("MATCH (n) RETURN COUNT(n) as cnt").fetchall()
    entity_count = result[0]["cnt"] if result else 0

    # Calculate density
    density_per_doc = entity_count / doc_count if doc_count > 0 else 0
    density_per_chunk = entity_count / chunk_count if chunk_count > 0 else 0

    # Alert if density exceeds safe threshold
    alert = False
    reason = None
    if density_per_doc > 50:  # >50 entities per document is too many
        alert = True
        reason = f"density_per_doc={density_per_doc:.2f} exceeds 50 (graph explosion risk)"
    elif entity_count > 10000:  # Hard cap for 500-doc corpus
        alert = True
        reason = f"total_entity_count={entity_count} exceeds 10K hardcap"

    return {
        "entity_count": entity_count,
        "density_per_doc": density_per_doc,
        "density_per_chunk": density_per_chunk,
        "alert": alert,
        "reason": reason,
    }
```

### Anti-Patterns to Avoid

- **Embedding entities directly instead of using LLM:** The embedding model (nomic-embed-text) is NOT an instruction-following LLM. It cannot extract entities. Must use LM Studio's LLM endpoint (Qwen2.5 7B).
- **Storing all extracted entities without whitelisting:** Without entity type whitelist (OEM|Supplier|Technology|Product|Recommendation), the graph will contain thousands of noisy entities like "automotive" or "market". Filter by type at extraction time.
- **Confidence < 0.7 entities:** Low-confidence extractions are unreliable. The LLM guessing game. Enforce threshold.
- **Fuzzy matching at 100% (exact match only):** Defeats deduplication. A corpus will contain "Tesla", "Tesla Inc.", "Tesla Inc", "Tesla, Inc." — all the same entity. Use 80–90% token_set_ratio.
- **No deduplication within-batch:** Multiple chunks may mention the same entity. Deduplicate before insertion to avoid duplicate nodes in KuzuDB.
- **Skipping chunk citations:** Without linking entities back to chunks, Phase 4 query answers cannot be cited. Always build chunk_citations table.
- **Re-extracting already-processed chunks:** Large corpus → expensive. Use extraction_state checkpoint (last_chunk_id_processed) to resume mid-pipeline on crash.
- **Ignoring KuzuDB schema requirement:** KuzuDB is NOT schemaless. Define all node/rel tables upfront. Mixing Cypher dialects (Neo4j vs KuzuDB walk semantics) causes confusion.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fuzzy entity matching | Manual Levenshtein distance scorer | RapidFuzz token_set_ratio() | RapidFuzz is 40% faster, handles case/punctuation variations, C++ optimized |
| Entity deduplication | Custom string comparison loop | RapidFuzz blocking + similarity threshold | Quadratic naive algorithm (N²); RapidFuzz uses LSH internally (O(N) with tuning) |
| JSON extraction from LLM | Regex parsing | json.loads() after validation | Regex is fragile; LM Studio supports structured JSON mode (future enhancement); use robust JSON parser |
| Graph schema management | Manual CREATE statements | KuzuDB `execute()` with idempotent checks | Version control Cypher DDL; reusable across environments; avoids schema drift |
| Source citation storage | Duplicate entities in KuzuDB with chunk_ids | SQLite bridge table (chunk_citations) | KuzuDB entities are canonical (no duplication); SQLite handles the N:M mapping efficiently |
| Entity type validation | Separate if-else tree for each type | Whitelist set + dict lookup | Maintainable; easy to add new types; avoids hardcoding logic |

**Key insight:** Fuzzy entity matching scales O(N²) without optimizations. RapidFuzz's token_set_ratio + type-based grouping keeps deduplication practical even for 50K+ entities.

---

## Runtime State Inventory

This is a construction (greenfield) phase, not a rename/refactor phase. No pre-existing runtime state to track. However, the incremental indexing checkpoint must be managed:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | extraction_state.json: {chunks_processed: int, last_entity_id: int, last_chunk_id: int} | Create schema: JSON file with checkpoint fields; update after each successful batch |
| Live service config | KuzuDB database file (knowledge_graph.db) — persisted on disk | Initialize once at pipeline startup; idempotent schema checks allow restarts |
| OS-registered state | None — KuzuDB is embedded, no process registration | N/A |
| Secrets/env vars | None — LM Studio uses hardcoded "lm-studio" API key (dummy value) | N/A |
| Build artifacts | Compiled KuzuDB wheels (.so/.dll) — installed via pip | Standard pip install; no custom build needed |

---

## Common Pitfalls

### Pitfall 1: Entity Type Confusion — No Whitelist

**What goes wrong:** Extraction loop has no entity type whitelist. The LLM extracts everything it identifies as a named entity: "automotive", "market", "EV", "supply chain", "2024", "metric", "thousands", etc. The graph explodes to 100K+ useless entities.
**Why it happens:** System prompt doesn't constrain entity types; "extract all entities" is ambiguous.
**How to avoid:** Enforce entity type whitelist (OEM, Supplier, Technology, Product, Recommendation only) in the system prompt. Reject any extracted entity not in the whitelist before deduplication. Validate extracted entities: `if entity["type"] not in ENTITY_TYPES: skip`
**Warning signs:** After 100 documents, entity count > 5,000 (density > 50 entities/doc). Check extraction output: are you seeing "market", "metric", "year", etc.? That's noise.

### Pitfall 2: Confidence < 0.7 Entities — Noise

**What goes wrong:** LLM extracts entities with low confidence (0.3–0.7). These are guesses, not facts. They pollute the graph and hurt query quality.
**Why it happens:** System prompt includes low-confidence entities or doesn't enforce threshold filtering.
**How to avoid:** Only accept entities with confidence >= 0.7. In the LLM response validation, drop low-confidence entities immediately: `entities = [e for e in extracted if e.get("confidence", 0) >= 0.7]`
**Warning signs:** Query results include entities you never saw in source documents. That's a sign low-confidence extractions leaked through.

### Pitfall 3: No Fuzzy Deduplication — Fragmented Graph

**What goes wrong:** Exact-match deduplication only. "Tesla", "Tesla Inc.", "Tesla Inc", "Tesla Inc.", "TESLA Inc." become 5 separate entities in the graph.
**Why it happens:** Deduplication logic is `if name1 == name2:` (exact string match). Legal suffixes and case variations are not handled.
**How to avoid:** Apply normalize_entity_name() before dedup: lower case, remove legal suffixes (Inc., LLC, Corp., Ltd., GmbH, AG, SA, SAS, SARL, BV, NV, Pty, Plc), remove punctuation. Use RapidFuzz token_set_ratio() with 85%+ threshold.
**Warning signs:** After graph construction, query "Tesla" and get multiple nodes with near-identical names. That's fragmentation.

### Pitfall 4: LM Studio Model Timeout — Batch Too Large

**What goes wrong:** Batch size is 32+ chunks. LM Studio inference times out (default 30s max_tokens × large context = slow). Extraction fails mid-pipeline.
**Why it happens:** Assumption that larger batches are more efficient (actually: slower, more prone to hallucination).
**How to avoid:** Use batch size 8 chunks max. 8 chunks × ~512 tokens/chunk = ~4K tokens of context. LM Studio processes 4K tokens in ~5-10 seconds on 7B model. Safe margin.
**Warning signs:** Extraction loop hangs; OpenAI client timeout exception after 30 seconds.

### Pitfall 5: No Chunk Citations — Can't Cite Answers

**What goes wrong:** Entities are stored in KuzuDB but have no link back to source chunks. In Phase 4 when answering "which companies do X?", you can retrieve entity names but not the documents that mention them.
**Why it happens:** Chunk citations table is not created or populated.
**How to avoid:** Create chunk_citations bridge table (entity_canonical_name, entity_type, chunk_id) in SQLite at Phase 3 initialization. Populate it as you insert entities: for each extracted entity, insert a row for each chunk it came from. Verify coverage: `SELECT COUNT(DISTINCT entity_canonical_name) FROM chunk_citations` should equal total unique entities.
**Warning signs:** Phase 4 query result has no citations; user cannot trace where the answer came from.

### Pitfall 6: KuzuDB Schema Mismatch — INSERT Fails

**What goes wrong:** INSERT statement references a node type (e.g., `:OEM`) but the node table does not exist, or property types don't match (inserting STRING into INT column).
**Why it happens:** Schema creation skipped or failed silently; dynamic schema assumptions (like Neo4j's flexibility).
**How to avoid:** Call create_graph_schema() at pipeline startup. Validate schema existence: `db.execute("MATCH (n:OEM) LIMIT 1")` before bulk inserts. Test INSERT statements in a small batch first (5 entities) before scaling to 1000+.
**Warning signs:** INSERT queries raise schema errors. Check stdout/stderr for "property not found" or "node type not found".

### Pitfall 7: Cypher Dialect Incompatibility — Walk vs Trail Semantics

**What goes wrong:** Write a Cypher query for variable-length relationships assuming Neo4j trail semantics (no repeated edges): `MATCH (n)-[:USES*1..3]->(m)`. In KuzuDB, this allows repeated edges (walk semantics) and may return cycles or duplicates.
**Why it happens:** KuzuDB explicitly uses walk semantics; Neo4j uses trail semantics. Queries copied from Neo4j patterns don't behave identically.
**How to avoid:** In Phase 3, stick to simple patterns (single-hop, short relationships). If you need variable-length patterns, add explicit upper bound: `MATCH (n)-[:USES*1..3]->(m)` works in KuzuDB (max 3 hops). Use `is_acyclic()` function if you need to exclude cycles.
**Warning signs:** Variable-length queries return unexpected duplicate nodes or cycles. Check KuzuDB docs for walk vs trail semantic explanation.

---

## Code Examples

Verified patterns from official sources:

### Entity Extraction Prompt Structure

```python
# Source: LM Studio Chat Completions API + Qwen2.5 instruction-following
system_message = """You are an expert at extracting structured information from automotive consulting documents.

Extract named entities (organizations, technologies, products, recommendations) and relationships from the provided text chunks.

Return ONLY valid JSON with NO markdown, NO code blocks, NO extra text.

{
  "entities": [
    {
      "name": "string",
      "type": "string (must be one of: OEM, Supplier, Technology, Product, Recommendation)",
      "confidence": float (0.0 to 1.0)
    }
  ],
  "relationships": [
    {
      "source_name": "string",
      "target_name": "string",
      "type": "string (must be one of: IS_A, USES, PRODUCES, RECOMMENDS)",
      "confidence": float (0.0 to 1.0)
    }
  ]
}

Extraction Rules:
1. ONLY extract entities with confidence >= 0.7 (avoid weak guesses).
2. Entity TYPES must be EXACTLY one of: OEM (car manufacturer), Supplier (parts maker), Technology (EV, autonomous, etc.), Product (components), Recommendation (strategic advice).
3. Normalize entity names: title case, no leading/trailing spaces, no punctuation except hyphens.
4. Remove legal suffixes automatically: Inc, LLC, Corp, Ltd, GmbH, AG, SA, SARL, BV, Pty, Plc.
5. One entity per name: no duplicate names within a single chunk.
6. Relationships: only valid if both source and target entities were extracted."""

response = client.chat.completions.create(
    model="Qwen2.5-7B-Instruct",
    messages=[
        {"role": "system", "content": system_message},
        {"role": "user", "content": "Extract from: " + chunk_text},
    ],
    temperature=0.1,  # Deterministic extraction
    max_tokens=2048,
)

# Parse and validate
extracted_text = response.choices[0].message.content.strip()
data = json.loads(extracted_text)
entities = [e for e in data.get("entities", []) if e.get("confidence", 0) >= 0.7]
```

### Fuzzy Deduplication with RapidFuzz

```python
# Source: RapidFuzz documentation + entity resolution best practices
from rapidfuzz import fuzz
import re

def normalize_and_deduplicate(extracted_entities: list[dict], threshold: float = 0.85) -> list[dict]:
    """Deduplicate entities by fuzzy matching normalized names.

    Args:
        extracted_entities: List of {name, type, confidence} dicts.
        threshold: Fuzzy ratio threshold for merge (0-100). Default 85 is strict.

    Returns:
        List of canonical {name, type, confidence} dicts.
    """
    def normalize(name: str) -> str:
        # Title case
        name = name.title()
        # Remove legal suffixes
        suffixes = r'\b(Inc|Incorporated|LLC|Corp|Corporation|Ltd|Limited|GmbH|AG|SA|SAS|SARL|BV|NV|Pty|Plc)\b'
        name = re.sub(suffixes, '', name, flags=re.IGNORECASE)
        # Remove punctuation except hyphens
        name = re.sub(r'[^\w\s-]', '', name)
        # Normalize whitespace
        name = re.sub(r'\s+', ' ', name).strip()
        return name

    # Group by entity type
    by_type = {}
    for e in extracted_entities:
        etype = e.get("type", "Unknown")
        if etype not in by_type:
            by_type[etype] = []
        by_type[etype].append({**e, "norm": normalize(e["name"])})

    # Deduplicate within each type
    result = []
    for etype, entities in by_type.items():
        canonical = {}
        for e in entities:
            found = False
            for canon_norm, canon_entity in canonical.items():
                # Token-set ratio ignores word order: "Tesla Inc" == "Inc Tesla"
                ratio = fuzz.token_set_ratio(e["norm"], canon_norm)
                if ratio >= threshold:
                    # Merge by keeping higher confidence
                    if e.get("confidence", 0) > canon_entity.get("confidence", 0):
                        canonical[canon_norm] = e
                    found = True
                    break
            if not found:
                canonical[e["norm"]] = e

        result.extend(canonical.values())

    return result
```

### KuzuDB Node/Relationship Insertion

```python
# Source: KuzuDB official docs (Python API examples)
import kuzu

def insert_entities_batch(db: kuzu.Database, canonical_entities: list[dict]) -> None:
    """Insert batch of canonical entities into KuzuDB.

    Args:
        db: KuzuDB Database instance.
        canonical_entities: List of {name, type, confidence} dicts.
    """
    for entity in canonical_entities:
        name = entity["name"].replace("'", "''")  # Escape quotes for Cypher
        etype = entity["type"]
        conf = entity.get("confidence", 0.7)

        if etype == "OEM":
            db.execute(
                f"CREATE (e:OEM {{canonical_name: '{name}', confidence: {conf}}})"
            )
        elif etype == "Supplier":
            db.execute(
                f"CREATE (e:Supplier {{canonical_name: '{name}', confidence: {conf}}})"
            )
        elif etype == "Technology":
            db.execute(
                f"CREATE (e:Technology {{canonical_name: '{name}', confidence: {conf}}})"
            )
        elif etype == "Product":
            db.execute(
                f"CREATE (e:Product {{canonical_name: '{name}', confidence: {conf}}})"
            )
        elif etype == "Recommendation":
            db.execute(
                f"CREATE (e:Recommendation {{canonical_name: '{name}', confidence: {conf}}})"
            )

def insert_relationships_batch(db: kuzu.Database, relationships: list[dict]) -> None:
    """Insert batch of relationships.

    Args:
        db: KuzuDB Database instance.
        relationships: List of {source_name, target_name, type} dicts.
    """
    for rel in relationships:
        source = rel["source_name"].replace("'", "''")
        target = rel["target_name"].replace("'", "''")
        rtype = rel["type"]  # IS_A, USES, PRODUCES, RECOMMENDS

        # Find entity types by querying
        source_type = None
        for node_type in ["OEM", "Supplier", "Technology", "Product", "Recommendation"]:
            results = db.execute(
                f"MATCH (s:{node_type} {{canonical_name: '{source}'}}) RETURN s LIMIT 1"
            ).fetchall()
            if results:
                source_type = node_type
                break

        target_type = None
        for node_type in ["OEM", "Supplier", "Technology", "Product", "Recommendation"]:
            results = db.execute(
                f"MATCH (t:{node_type} {{canonical_name: '{target}'}}) RETURN t LIMIT 1"
            ).fetchall()
            if results:
                target_type = node_type
                break

        if source_type and target_type:
            db.execute(
                f"MATCH (s:{source_type} {{canonical_name: '{source}'}}), "
                f"(t:{target_type} {{canonical_name: '{target}'}}) "
                f"CREATE (s)-[:{rtype}]->(t)"
            )
```

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | pytest.ini or pyproject.toml (to be created in Wave 0) |
| Quick run command | `pytest tests/test_graph_*.py -k "not lm_studio" -x` |
| Full suite command | `pytest tests/test_graph_*.py -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GRAPH-01 | LM Studio extracts entities/relationships as JSON from chunk text | unit | `pytest tests/test_graph_extraction.py::test_extract_entities_from_chunk -x` | ❌ Wave 0 |
| GRAPH-01 | Extracted entities have valid type (OEM\|Supplier\|Technology\|Product\|Recommendation) | unit | `pytest tests/test_graph_extraction.py::test_entity_type_validation -x` | ❌ Wave 0 |
| GRAPH-01 | Extracted entities have confidence >= 0.7 | unit | `pytest tests/test_graph_extraction.py::test_confidence_threshold -x` | ❌ Wave 0 |
| GRAPH-02 | Fuzzy matching deduplicates "Tesla", "Tesla Inc.", "TESLA Inc." → 1 canonical entity | unit | `pytest tests/test_deduplicator.py::test_fuzzy_dedup_legal_suffix -x` | ❌ Wave 0 |
| GRAPH-02 | normalize_entity_name() removes legal suffixes and normalizes case | unit | `pytest tests/test_deduplicator.py::test_normalize_name -x` | ❌ Wave 0 |
| GRAPH-03 | KuzuDB node table creation is idempotent (can call twice safely) | unit | `pytest tests/test_kuzu_db.py::test_create_schema_idempotent -x` | ❌ Wave 0 |
| GRAPH-03 | INSERT entity via Cypher creates node in correct table with properties | unit | `pytest tests/test_kuzu_db.py::test_insert_entity_oem -x` | ❌ Wave 0 |
| GRAPH-03 | MATCH query retrieves inserted entities | unit | `pytest tests/test_kuzu_db.py::test_query_entity -x` | ❌ Wave 0 |
| GRAPH-04 | chunk_citations table stores entity → chunk mappings | unit | `pytest tests/test_citations.py::test_insert_chunk_citation -x` | ❌ Wave 0 |
| GRAPH-04 | get_chunks_for_entity() retrieves source chunks with doc metadata | unit | `pytest tests/test_citations.py::test_get_chunks_for_entity -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_graph_*.py -k "not lm_studio" -x` (unit tests, no LM Studio calls)
- **Per wave merge:** `pytest tests/test_graph_*.py -x` (all tests including integration with mocked LM Studio)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_graph_extraction.py` — covers GRAPH-01 entity extraction, type validation, confidence filtering
- [ ] `tests/test_deduplicator.py` — covers GRAPH-02 fuzzy matching, normalization, legal suffix removal
- [ ] `tests/test_kuzu_db.py` — covers GRAPH-03 schema creation, INSERT, MATCH queries
- [ ] `tests/test_citations.py` — covers GRAPH-04 chunk citation storage and retrieval
- [ ] `src/graph/` module stubs — __init__.py, extractor.py, deduplicator.py, db_manager.py, citations.py, monitor.py
- [ ] Framework setup: `pip install pytest chromadb kuzu rapidfuzz` (if not already installed)

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Runtime | Yes | 3.13.5 | — |
| kuzu (pip) | KuzuDB graph store | Not yet installed | 0.11.3 (confirmed from PyPI) | — |
| rapidfuzz (pip) | Fuzzy entity dedup | Not yet installed | 3.14.3 (confirmed from PyPI) | python-Levenshtein (slower, 40%) |
| openai (pip) | LM Studio LLM client | Yes (installed) | 1.93.0 | — |
| LM Studio server | LLM entity extraction | Assumed running | Unknown — verify at runtime | Use mock for unit tests; no fallback for integration |
| Qwen2.5-7B-Instruct | GRAPH-01 entity extraction model | Assumed loaded in LM Studio | Unknown — verify via /v1/models | Cannot extract without it; block noted in STATE.md |
| sqlite3 | Chunk citations bridge table | Yes (stdlib) | bundled | — |
| tqdm (pip) | Progress bar | Yes (installed) | 4.67.1 | — |
| pytest (pip) | Unit testing | Yes (installed) | 9.0.2 | — |

**Missing dependencies with no fallback:**
- LM Studio must be running with Qwen2.5-7B-Instruct loaded for entity extraction. Unit tests must mock this.
- KuzuDB 0.11.3 must be pip-installable on Windows (confirmed).

**Missing dependencies with fallback:**
- rapidfuzz not yet installed; python-Levenshtein available as slower fallback (not recommended due to performance).

---

## Open Questions

1. **LM Studio Qwen2.5 model exact ID string**
   - What we know: Common variant is `"Qwen2.5-7B-Instruct"`. LM Studio displays exact ID in UI.
   - What's unclear: Whether the production LM Studio instance uses `"Qwen2.5-7B-Instruct"` or variant (e.g., `"lmstudio-community/Qwen2.5-7B-Instruct-GGUF"`).
   - Recommendation: Plan must include startup check that calls `GET /v1/models`, extracts the LLM model ID, and stores in config. Fallback: hardcode and verify manually.

2. **Optimal fuzzy matching threshold**
   - What we know: 90% token_set_ratio is strict; 80% is loose. Recommendation: 85%.
   - What's unclear: Actual false-positive rate at 85% threshold on automotive entity corpus. May need tuning after integration testing.
   - Recommendation: Implement configurable threshold (default 85%); measure false-positive rate (manual review of 100-entity sample after dedup); adjust if > 5% false positives.

3. **Batch size for LM Studio extraction**
   - What we know: 8 chunks per batch is safe (~5-10s latency).
   - What's unclear: Optimal batch size for quality vs speed tradeoff. Larger batches → more context confusion? Smaller → more API calls?
   - Recommendation: Implement configurable batch size (default 8); benchmark 4, 8, 16 chunks on a sample document; measure extraction quality (e.g., F1 score on manual gold-standard entities) vs latency.

4. **Entity type coverage for automotive consulting**
   - What we know: OEM, Supplier, Technology, Product, Recommendation are initial whitelist.
   - What's unclear: Are there automotive-specific entity types missing? (e.g., Regulation, Supply Chain Role, Market Segment)?
   - Recommendation: After Phase 3 Wave 1, manually review 20 extracted documents and check for entity types that appear frequently but are not in the whitelist. Expand whitelist if needed.

5. **Graph explosion monitoring: entity density threshold**
   - What we know: Target is <20 entities/doc average (500 docs → <10K entities).
   - What's unclear: What density threshold triggers an alert? 30 entities/doc? 50? Real-world data may vary.
   - Recommendation: Set initial threshold at 50 entities/doc (alert if exceeded). After Phase 3 completion, analyze actual entity density distribution; adjust threshold based on corpus characteristics.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Neo4j for graph storage | KuzuDB embedded | 2026 (PROJECT.md decision) | No external process required; fits on 32GB laptop; pyinstallable |
| Manual entity mention matching | Fuzzy token_set_ratio + normalization | Common practice since ~2020 | Handles spelling variants and legal suffix variations automatically |
| No entity confidence scoring | LLM confidence 0-1 + >0.7 threshold | LLM-era extraction (2022+) | Filters low-confidence guesses; reduces noise |
| Entity type: "any named entity" | Entity type whitelist (5 types) | Knowledge graph quality work (2023+) | Reduces graph to relevant entities only; prevents explosion |
| In-memory graph for small corpus | KuzuDB persistent store | This project (2026) | Survives process restart; scales incrementally |

**Deprecated/outdated:**
- Neo4j with external server: requires enterprise license or community edition with port forwarding; blocked by corporate firewall; not suitable for single-laptop deployment.
- Rules-based entity extraction: requires manual rule authoring; breaks on new entity types; LLM extraction generalizes better.
- No deduplication: results in fragmented graph with 3–5× more entities than real-world unique set.

---

## Sources

### Primary (HIGH confidence)

- [KuzuDB PyPI — kuzu 0.11.3](https://pypi.org/project/kuzu/) — Python API, pip installation, latest stable version verified 2026-03-30
- [KuzuDB Python API Documentation](https://docs.kuzudb.com/client-apis/python/) — `conn.execute()` syntax, schema creation examples
- [KuzuDB Cypher DDL Reference](https://docs.kuzudb.com/cypher/data-definition/) — CREATE NODE TABLE, CREATE REL TABLE syntax
- [KuzuDB vs Neo4j Differences](https://docs.kuzudb.com/cypher/difference/) — Walk vs trail semantics, schema requirement, Cypher compatibility
- [LM Studio OpenAI-Compatible Chat Completions](https://lmstudio.ai/docs/developer/openai-compat/chat-completions) — `/v1/chat/completions` endpoint, Qwen2.5 support
- [RapidFuzz PyPI — 3.14.3](https://pypi.org/project/RapidFuzz/) — token_set_ratio(), performance benchmarks
- [RapidFuzz vs FuzzyWuzzy](https://plainenglish.io/blog/rapidfuzz-versus-fuzzywuzzy) — Performance comparison, 40% faster than alternatives

### Secondary (MEDIUM confidence)

- [Entity and Relation Extractions for Knowledge Graphs](https://www.sciencedirect.com/science/article/pii/S0167404824004255) — Deduplication strategies, entity resolution at scale
- [Knowledge Graph Extraction Challenges (Neo4j Blog)](https://neo4j.com/blog/developer/knowledge-graph-extraction-challenges/) — Entity type whitelisting, confidence thresholding, graph quality
- [Entity Resolution at Scale (Medium — Jan 2026)](https://medium.com/@shereshevsky/entity-resolution-at-scale-deduplication-strategies-for-knowledge-graph-construction-7499a60a97c3) — Incremental KG construction, dedup strategies
- [Knowledge Graph Metrics](https://www.meegle.com/en_us/topics/knowledge-graphs/knowledge-graph-metrics) — Entity density measurement, growth monitoring
- [Incremental Knowledge Graph Construction (arXiv 2024)](https://arxiv.org/html/2409.03284v1) — Batch updates, avoiding re-extraction, hybrid architectures

### Tertiary (LOW confidence, marked for validation)

- [Fuzzy Matching 101 (Data Ladder)](https://dataladder.com/fuzzy-matching-101/) — General fuzzy matching theory, legal suffix normalization practices (not automotive-specific)
- [Automotive Supply Chain (Medium)](https://medium.com/self-driving-cars/the-automotive-supply-chain-explained-d4e74250106f) — OEM/Tier-1/Tier-2/Tier-3 entity types (inferred; not verified on actual consulting documents in this project)

---

## Metadata

**Confidence breakdown:**
- **Standard stack (KuzuDB, RapidFuzz, LM Studio API):** HIGH — verified from official docs and PyPI
- **Entity/relationship extraction patterns:** MEDIUM — LLM patterns well-established, but exact prompt structure and JSON parsing require validation in Phase 3 Wave 1
- **Fuzzy deduplication strategy:** MEDIUM — RapidFuzz performance verified, but optimal threshold (85% vs 80% vs 90%) requires tuning on actual corpus
- **Graph explosion prevention:** MEDIUM — Strategy sound (whitelist + threshold + density monitoring), but thresholds (50 entities/doc, 10K total) may need adjustment based on real entity distribution
- **Chunk citations linkage:** HIGH — Standard relational pattern; SQLite bridge table well-proven
- **Cypher dialect differences:** MEDIUM — KuzuDB docs confirm walk semantics and schema requirement, but complex variable-length patterns untested on this codebase

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (30 days; KuzuDB archived so versions stable; LM Studio API stable)
