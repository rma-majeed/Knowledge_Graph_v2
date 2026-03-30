"""Embedding generation via LM Studio OpenAI-compatible API."""
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
        RuntimeError: When the LM Studio server is unreachable.
    """
    if not chunks:
        return []

    import httpx

    results: list[list[float]] = []

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c["chunk_text"].strip() for c in batch]

        # If all texts in the batch are empty/whitespace, use zero vectors
        if all(t == "" for t in texts):
            results.extend([[0.0] * 768 for _ in batch])
            continue

        try:
            import openai

            response = client.embeddings.create(model=model, input=texts)
            vectors = [item.embedding for item in response.data]
            results.extend(vectors)
        except (openai.APIConnectionError, httpx.ConnectError, httpx.TimeoutException) as e:
            raise RuntimeError(
                f"LM Studio server unavailable at localhost:1234 — {e!r}"
            ) from e

    return results


def embed_query(query_text: str, client: Any, model: str) -> list[float]:
    """Embed a single query string for vector search.

    Args:
        query_text: The user query string to embed.
        client: openai.OpenAI client configured for LM Studio.
        model: Model name string.

    Returns:
        Single embedding vector as list[float].
    """
    return embed_chunks([{"chunk_text": query_text}], client, model)[0]
