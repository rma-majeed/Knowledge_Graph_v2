---
phase: 03-knowledge-graph-construction
plan: 02
type: execute
wave: 2
depends_on:
  - "03-01"
files_modified:
  - src/graph/extractor.py
autonomous: true
requirements:
  - GRAPH-01

must_haves:
  truths:
    - "extract_entities_relationships() calls client.chat.completions.create() with system prompt enforcing 5 entity types and confidence >= 0.7"
    - "Entities with type not in {OEM, Supplier, Technology, Product, Recommendation} are silently dropped"
    - "Entities with confidence < 0.7 are silently dropped"
    - "LLM response with markdown code fences (```json...```) is parsed correctly"
    - "All 6 non-lm_studio extraction tests pass"
  artifacts:
    - path: "src/graph/extractor.py"
      provides: "extract_entities_relationships() implementation"
      exports: ["extract_entities_relationships", "ENTITY_TYPES", "CONFIDENCE_THRESHOLD", "BATCH_SIZE"]
      min_lines: 60
  key_links:
    - from: "tests/test_graph_extraction.py"
      to: "src/graph/extractor.py"
      via: "from src.graph.extractor import extract_entities_relationships"
      pattern: "from src.graph.extractor import"
    - from: "src/graph/extractor.py"
      to: "openai.OpenAI"
      via: "client.chat.completions.create()"
      pattern: "client.chat.completions.create"
---

<objective>
Implement `src/graph/extractor.py` — the LM Studio LLM entity and relationship extraction module for Phase 3.

Purpose: Replace the NotImplementedError stubs with working extraction logic that calls LM Studio's `/v1/chat/completions` endpoint via the openai client, parses structured JSON responses, enforces the entity type whitelist (OEM|Supplier|Technology|Product|Recommendation), and filters by confidence threshold (>= 0.7). Turns the 6 extraction xfail stubs green.

Output: `src/graph/extractor.py` with `extract_entities_relationships()` fully implemented. All 6 unit stubs in `test_graph_extraction.py` pass (lm_studio integration test remains xfail until LM Studio is running).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/03-knowledge-graph-construction/03-RESEARCH.md

<interfaces>
<!-- From src/embed/embedder.py — LM Studio client pattern Phase 2 established -->
```python
# Phase 2 pattern: client passed in, not constructed internally
def embed_chunks(chunks: list[dict], client, model: str, batch_size: int = 8) -> list[list[float]]:
    # client.embeddings.create(model=model, input=[...])
```

<!-- From Phase 3 RESEARCH.md Pattern 1 — exact function signature to implement -->
```python
ENTITY_TYPES = {"OEM", "Supplier", "Technology", "Product", "Recommendation"}
CONFIDENCE_THRESHOLD = 0.7
BATCH_SIZE = 8

def extract_entities_relationships(chunk_texts: list[str], client) -> dict:
    """Returns {"entities": [...], "relationships": [...]}"""
    # client.chat.completions.create(
    #     model="Qwen2.5-7B-Instruct",
    #     messages=[{"role": "system", "content": system_prompt},
    #               {"role": "user", "content": user_prompt}],
    #     temperature=0.1,
    #     max_tokens=2048,
    # )
```

<!-- LLM response parse pattern (from RESEARCH.md) -->
```python
response_text = response.choices[0].message.content.strip()
if response_text.startswith("```json"):
    response_text = response_text[7:]
if response_text.startswith("```"):
    response_text = response_text[3:]
if response_text.endswith("```"):
    response_text = response_text[:-3]
data = json.loads(response_text.strip())
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement extract_entities_relationships() in extractor.py</name>
  <files>src/graph/extractor.py</files>

  <read_first>
    - src/graph/extractor.py (current stub — understand existing constants and function signature)
    - tests/test_graph_extraction.py (ALL 6 unit tests — understand exact contract: mock shape, assertion targets, edge cases)
    - src/embed/embedder.py (LM Studio client usage pattern to replicate)
    - .planning/phases/03-knowledge-graph-construction/03-RESEARCH.md (Pattern 1: full system prompt text, JSON schema, rules)
  </read_first>

  <behavior>
    - Test 1 (test_extract_entities_from_chunk): mock client returns valid JSON string; result["entities"][0] has name="Toyota", type="OEM", confidence=0.95
    - Test 2 (test_entity_type_validation): mock returns entity with type="Person" (invalid) + type="Supplier" (valid); result contains only Supplier
    - Test 3 (test_confidence_threshold): mock returns confidence=0.9 and confidence=0.5; only confidence=0.9 entity survives
    - Test 4 (test_extract_relationships_from_chunk): mock returns relationship with source_name, target_name, type; result["relationships"][0] has all 3 keys
    - Test 5 (test_extract_returns_empty_on_no_entities): mock returns `{"entities": [], "relationships": []}`; result has both empty
    - Test 6 (test_batch_size_8_chunks_max): 8 chunks passed in; client.chat.completions.create called exactly once
  </behavior>

  <action>
Replace the entire contents of src/graph/extractor.py with the following implementation:

```python
"""Entity/relationship extraction via LM Studio LLM.

Calls LM Studio's /v1/chat/completions endpoint (OpenAI-compatible) with a structured
JSON prompt to extract named entities and typed relationships from automotive consulting
document chunks.

Public API:
    ENTITY_TYPES: frozenset — whitelisted entity types
    CONFIDENCE_THRESHOLD: float — minimum confidence to accept (0.7)
    BATCH_SIZE: int — maximum chunks per API call (8)
    extract_entities_relationships(chunk_texts, client) -> dict
        Returns {"entities": [...], "relationships": [...]}
"""
from __future__ import annotations

import json

ENTITY_TYPES: frozenset[str] = frozenset({"OEM", "Supplier", "Technology", "Product", "Recommendation"})
CONFIDENCE_THRESHOLD: float = 0.7
BATCH_SIZE: int = 8

# System prompt enforces entity type whitelist, confidence rules, and JSON schema
_SYSTEM_PROMPT = """You are an entity and relationship extraction expert for automotive consulting documents.

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
6. Relationships: only link entities present in the extracted entities list."""


def extract_entities_relationships(chunk_texts: list[str], client) -> dict:
    """Extract entities and relationships from chunk texts using LM Studio LLM.

    Calls LM Studio's /v1/chat/completions endpoint with a structured JSON system prompt.
    Filters extracted entities by type whitelist and confidence threshold before returning.

    Args:
        chunk_texts: List of chunk text strings (max BATCH_SIZE=8 chunks per call).
        client: openai.OpenAI client pointing to LM Studio (/v1/chat/completions).
            Must have a `chat.completions.create()` method (standard OpenAI client API).

    Returns:
        Dict with keys:
        - "entities": list of {name, type, confidence} dicts (filtered by whitelist + threshold)
        - "relationships": list of {source_name, target_name, type} dicts

    Raises:
        json.JSONDecodeError: If LLM returns malformed JSON that cannot be parsed.
        Exception: Propagates any openai client exceptions (timeout, connection error).
    """
    user_prompt = "Extract entities and relationships from these chunks:\n\n" + "\n---\n".join(chunk_texts)

    response = client.chat.completions.create(
        model="Qwen2.5-7B-Instruct",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=2048,
    )

    response_text = response.choices[0].message.content.strip()

    # Strip markdown code fences if present
    if response_text.startswith("```json"):
        response_text = response_text[7:]
    if response_text.startswith("```"):
        response_text = response_text[3:]
    if response_text.endswith("```"):
        response_text = response_text[:-3]

    data = json.loads(response_text.strip())

    # Validate and filter entities
    raw_entities = data.get("entities", [])
    filtered_entities = [
        e for e in raw_entities
        if e.get("type") in ENTITY_TYPES and e.get("confidence", 0.0) >= CONFIDENCE_THRESHOLD
    ]

    relationships = data.get("relationships", [])

    return {
        "entities": filtered_entities,
        "relationships": relationships,
    }
```

Run the extraction tests immediately after writing the file to verify RED -> GREEN transition:
`pytest tests/test_graph_extraction.py -x -q -k "not lm_studio" --tb=short`

All 6 unit tests must now pass (not xfail — they should be fully GREEN).
  </action>

  <verify>
    <automated>cd "C:\Users\2171176\Documents\Python\Knowledge_Graph_v2" && python -m pytest tests/test_graph_extraction.py -v -k "not lm_studio" --tb=short 2>&1 | tail -15</automated>
  </verify>

  <acceptance_criteria>
    - `pytest tests/test_graph_extraction.py -k "not lm_studio" -v` shows 6 PASSED (not xfail, not failed)
    - `grep "ENTITY_TYPES" src/graph/extractor.py` exits 0
    - `grep "CONFIDENCE_THRESHOLD" src/graph/extractor.py` exits 0
    - `grep "chat.completions.create" src/graph/extractor.py` exits 0
    - `grep "ENTITY_TYPES" src/graph/extractor.py` returns the frozenset definition
    - `python -c "from src.graph.extractor import extract_entities_relationships, ENTITY_TYPES, CONFIDENCE_THRESHOLD, BATCH_SIZE; print('OK')"` exits 0
    - `grep "startswith.*\`\`\`json" src/graph/extractor.py` exits 0 (markdown fence stripping present)
    - Full test suite still green: `pytest tests/ -x -q -k "not lm_studio and not integration"` exits 0
  </acceptance_criteria>

  <done>extract_entities_relationships() implemented; entity type whitelist and confidence threshold enforced; LLM response JSON parsing handles markdown code fences; all 6 unit extraction tests pass</done>
</task>

</tasks>

<verification>
```bash
# Unit tests pass (6 green, lm_studio xfail)
pytest tests/test_graph_extraction.py -v --tb=short

# Full suite unaffected
pytest tests/ -x -q -k "not lm_studio and not integration" --tb=short
```
</verification>

<success_criteria>
- 6 extraction unit tests pass (GREEN, not xfail)
- lm_studio integration test remains xfail (expected — LM Studio not required for unit tests)
- src/graph/extractor.py exports ENTITY_TYPES, CONFIDENCE_THRESHOLD, BATCH_SIZE, extract_entities_relationships
- extract_entities_relationships() filters invalid types and low-confidence entities
- All prior Phase 1+2 tests still green
</success_criteria>

<output>
After completion, create `.planning/phases/03-knowledge-graph-construction/03-02-SUMMARY.md`
</output>
