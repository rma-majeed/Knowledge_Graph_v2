"""Fixed-size text chunking with overlap using tiktoken.

Algorithm:
1. Encode entire text to token list using tiktoken cl100k_base
2. Slide a window of `chunk_size` tokens across the list, stepping by (chunk_size - overlap)
3. Decode each window back to a string
4. Return list of chunk dicts with text, token_count, and chunk_index

Defaults match RESEARCH.md recommendation:
- chunk_size = 512 tokens (~2000 chars, fits nomic-embed-text-1.5 8192-token window)
- overlap = 100 tokens (~400 chars, preserves cross-boundary context)
- encoding = cl100k_base (GPT-4 / OpenAI API compatible, same family as LM Studio models)

Usage:
    from src.ingest.chunker import chunk_text
    chunks = chunk_text(page_text, chunk_size=512, overlap=100)
    # chunks[0] == {"text": "...", "token_count": 512, "chunk_index": 0}
"""
from __future__ import annotations

import tiktoken

# Module-level encoder singleton — avoids reloading on every call (vocab load is ~100ms)
_ENCODER: tiktoken.Encoding | None = None


def _get_encoder(encoding_name: str = "cl100k_base") -> tiktoken.Encoding:
    """Return cached tiktoken encoder, loading on first call."""
    global _ENCODER
    if _ENCODER is None or _ENCODER.name != encoding_name:
        _ENCODER = tiktoken.get_encoding(encoding_name)
    return _ENCODER


def chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 100,
    encoding_name: str = "cl100k_base",
) -> list[dict]:
    """Split text into fixed-size overlapping chunks using tiktoken tokenization.

    The algorithm tokenizes the full text once, then slides a window of `chunk_size`
    tokens with a step of (chunk_size - overlap). Each window is decoded back to a
    string to produce the chunk text.

    Args:
        text: Raw text to chunk (from PDF page or PPTX slide).
        chunk_size: Maximum tokens per chunk (default: 512).
        overlap: Tokens shared between adjacent chunks (default: 100).
        encoding_name: tiktoken encoding to use (default: 'cl100k_base').

    Returns:
        List of chunk dicts in document order:
        [
            {"text": str, "token_count": int, "chunk_index": int},
            ...
        ]
        Returns empty list if text is empty or whitespace-only.

    Raises:
        ValueError: If chunk_size <= overlap (step would be 0 or negative).
    """
    if not text or not text.strip():
        return []

    if chunk_size <= overlap:
        raise ValueError(
            f"chunk_size ({chunk_size}) must be greater than overlap ({overlap}). "
            f"Step = chunk_size - overlap = {chunk_size - overlap} (must be > 0)"
        )

    enc = _get_encoder(encoding_name)
    tokens: list[int] = enc.encode(text)
    total_tokens = len(tokens)

    if total_tokens == 0:
        return []

    step = chunk_size - overlap  # Tokens to advance per chunk
    chunks: list[dict] = []
    chunk_index = 0
    start = 0

    while start < total_tokens:
        end = min(start + chunk_size, total_tokens)
        window_tokens = tokens[start:end]

        # Decode window back to string
        chunk_text_str = enc.decode(window_tokens)

        # Strip leading/trailing whitespace without removing internal whitespace
        chunk_text_str = chunk_text_str.strip()

        if chunk_text_str:  # Skip empty decoded windows (can occur at document end)
            chunks.append(
                {
                    "text": chunk_text_str,
                    "token_count": len(window_tokens),
                    "chunk_index": chunk_index,
                }
            )
            chunk_index += 1

        # If we've reached the end, stop
        if end == total_tokens:
            break

        start += step

    return chunks
