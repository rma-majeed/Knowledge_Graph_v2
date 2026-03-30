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
