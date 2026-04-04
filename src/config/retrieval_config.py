"""RAG feature flags — configurable via environment variables (RAG-05).

All flags default to sensible values. Set env vars to override:
    RAG_ENABLE_BM25=false          # disable BM25 hybrid search
    RAG_ENABLE_RERANKER=false      # disable BGE cross-encoder reranking
    RAG_ENABLE_PARENT_DOC=true     # enable parent-document retrieval (opt-in)
    RAG_ENABLE_ENRICHMENT=true     # enable contextual chunk enrichment (opt-in)

Imports: os only — no heavy dependencies, safe to import at module level.
"""
from __future__ import annotations

import os


def _bool_env(name: str, default: bool) -> bool:
    """Read a boolean environment variable. Accepts 'true'/'false' (case-insensitive)."""
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() not in ("false", "0", "no", "off")


# RAG-01: BM25 hybrid search + Reciprocal Rank Fusion (default: enabled)
RAG_ENABLE_BM25: bool = _bool_env("RAG_ENABLE_BM25", True)

# RAG-02: BGE cross-encoder reranking (default: enabled)
RAG_ENABLE_RERANKER: bool = _bool_env("RAG_ENABLE_RERANKER", True)

# RAG-04: Parent-document retrieval — 3-chunk sliding window (default: enabled)
RAG_ENABLE_PARENT_DOC: bool = _bool_env("RAG_ENABLE_PARENT_DOC", True)

# RAG-03: Contextual chunk enrichment — LLM summary prepended at ingest time (default: enabled)
RAG_ENABLE_ENRICHMENT: bool = _bool_env("RAG_ENABLE_ENRICHMENT", True)
