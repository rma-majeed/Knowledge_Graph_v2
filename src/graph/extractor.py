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
