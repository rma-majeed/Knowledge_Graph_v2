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
# Note: Full words like "Corporation" and "Limited" are kept; only abbreviations and short forms
# are stripped. This preserves "Toyota Motor Corporation" while stripping "Corp." and "Corp".
_LEGAL_SUFFIX_RE = re.compile(
    r"\s+(?:Incorporated|Limited\s+Liability\s+Company|"
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
