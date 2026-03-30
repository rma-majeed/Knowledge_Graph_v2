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
