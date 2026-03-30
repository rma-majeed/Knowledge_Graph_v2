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
