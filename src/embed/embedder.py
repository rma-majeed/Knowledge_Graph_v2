"""Embedding generation via LM Studio OpenAI-compatible API.

Stub — implementation in Phase 2 Plan 02.
"""
from __future__ import annotations

from typing import Any


def embed_chunks(
    chunks: list[dict],
    client: Any,
    model: str,
    batch_size: int = 8,
) -> list[list[float]]:
    """Embed a list of chunk dicts using LM Studio embeddings API.

    Args:
        chunks: List of dicts with at minimum key 'chunk_text' (str).
        client: openai.OpenAI client configured for LM Studio.
        model: Model name string (e.g. 'nomic-embed-text-v1.5').
        batch_size: Chunks per API call (default 8, conservative for VRAM).

    Returns:
        List of embedding vectors (list[float]) in the same order as chunks.

    Raises:
        NotImplementedError: Until Plan 02 implements this function.
    """
    raise NotImplementedError("embed_chunks not yet implemented — see Plan 02")


def embed_query(query_text: str, client: Any, model: str) -> list[float]:
    """Embed a single query string for vector search.

    Args:
        query_text: The user query string to embed.
        client: openai.OpenAI client configured for LM Studio.
        model: Model name string.

    Returns:
        Single embedding vector as list[float].

    Raises:
        NotImplementedError: Until Plan 02 implements this function.
    """
    raise NotImplementedError("embed_query not yet implemented — see Plan 02")
