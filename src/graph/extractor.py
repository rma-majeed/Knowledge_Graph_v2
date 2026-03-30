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

    # Validate and filter entities by type whitelist and confidence threshold
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
