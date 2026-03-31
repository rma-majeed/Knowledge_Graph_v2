"""Feature flags for RAG retrieval quality improvements (RAG-05).

All flags default to conservative values:
- BM25 and reranker are enabled by default (additive improvements).
- Parent-doc retrieval and contextual enrichment are opt-in (require more resources).

Override via environment variables: RAG_ENABLE_BM25=false, etc.

Full implementation in plan 07-05.
"""
from __future__ import annotations

import os


def _bool_env(var: str, default: bool) -> bool:
    """Read a boolean environment variable with a default."""
    val = os.getenv(var)
    if val is None:
        return default
    return val.lower() not in ("false", "0", "no", "off")


RAG_ENABLE_BM25: bool = _bool_env("RAG_ENABLE_BM25", True)
RAG_ENABLE_RERANKER: bool = _bool_env("RAG_ENABLE_RERANKER", True)
RAG_ENABLE_PARENT_DOC: bool = _bool_env("RAG_ENABLE_PARENT_DOC", False)
RAG_ENABLE_ENRICHMENT: bool = _bool_env("RAG_ENABLE_ENRICHMENT", False)
