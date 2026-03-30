"""Graph explosion detection and entity density monitoring.

Tracks entity count and density relative to document and chunk counts.
Alerts when extraction is too permissive (density_per_doc > 50 or total > 10K).

Public API:
    MAX_ENTITIES_PER_DOC: int — alert threshold (50 entities/doc)
    MAX_TOTAL_ENTITIES: int — hard cap alert threshold (10000 total)
    check_entity_density(db, doc_count: int, chunk_count: int) -> dict
"""
from __future__ import annotations

import kuzu

MAX_ENTITIES_PER_DOC: int = 50
MAX_TOTAL_ENTITIES: int = 10_000


def check_entity_density(db: kuzu.Database, doc_count: int, chunk_count: int) -> dict:
    """Check entity density metrics for graph explosion warning signs.

    Queries KuzuDB for total entity count across all node tables, calculates
    density per document and per chunk, and sets alert=True if thresholds exceeded.

    Args:
        db: An open kuzu.Database instance with schema created.
        doc_count: Number of documents processed (denominator for density_per_doc).
        chunk_count: Number of chunks processed (denominator for density_per_chunk).

    Returns:
        Dict with keys:
        - entity_count (int): Total entity nodes across all 5 node tables
        - density_per_doc (float): entity_count / doc_count (0.0 if doc_count == 0)
        - density_per_chunk (float): entity_count / chunk_count (0.0 if chunk_count == 0)
        - alert (bool): True if density_per_doc > MAX_ENTITIES_PER_DOC or entity_count > MAX_TOTAL_ENTITIES
        - reason (str | None): Human-readable explanation when alert=True, else None
    """
    conn = kuzu.Connection(db)

    # Count entities across all 5 node tables
    entity_count = 0
    for table in ("OEM", "Supplier", "Technology", "Product", "Recommendation"):
        try:
            result = conn.execute(
                f"MATCH (n:{table}) RETURN COUNT(n) AS cnt"
            ).get_all()
            if result:
                entity_count += result[0][0]
        except Exception:
            # Table may not exist yet in early pipeline stages
            pass

    density_per_doc = entity_count / doc_count if doc_count > 0 else 0.0
    density_per_chunk = entity_count / chunk_count if chunk_count > 0 else 0.0

    alert = False
    reason: str | None = None

    if entity_count > MAX_TOTAL_ENTITIES:
        alert = True
        reason = (
            f"total entity_count={entity_count} exceeds {MAX_TOTAL_ENTITIES} hardcap "
            f"(graph explosion risk — tighten confidence threshold or entity whitelist)"
        )
    elif density_per_doc > MAX_ENTITIES_PER_DOC:
        alert = True
        reason = (
            f"density_per_doc={density_per_doc:.1f} exceeds {MAX_ENTITIES_PER_DOC} "
            f"(graph explosion risk — reduce confidence threshold from current level)"
        )

    return {
        "entity_count": entity_count,
        "density_per_doc": density_per_doc,
        "density_per_chunk": density_per_chunk,
        "alert": alert,
        "reason": reason,
    }
