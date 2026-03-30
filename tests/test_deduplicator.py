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
