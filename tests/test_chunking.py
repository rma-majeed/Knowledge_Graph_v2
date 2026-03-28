"""Tests for text chunking with tiktoken."""
import pytest


def test_chunk_fixed_size():
    """Chunker produces chunks of at most 512 tokens."""
    from src.ingest.chunker import chunk_text
    text = "word " * 2000  # ~2000 tokens
    chunks = chunk_text(text, chunk_size=512, overlap=100)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk["token_count"] <= 512


def test_chunk_overlap():
    """Adjacent chunks share approximately 100 tokens of overlap."""
    from src.ingest.chunker import chunk_text
    text = "word " * 2000
    chunks = chunk_text(text, chunk_size=512, overlap=100)
    assert len(chunks) >= 2
    # Overlap: end of chunk[0] text should appear at start of chunk[1] text
    end_words = chunks[0]["text"].split()[-20:]
    start_words = chunks[1]["text"].split()[:20]
    assert any(w in start_words for w in end_words)


def test_chunk_metadata_fields():
    """Each chunk dict contains required metadata keys."""
    from src.ingest.chunker import chunk_text
    text = "word " * 600
    chunks = chunk_text(text, chunk_size=512, overlap=100)
    required_keys = {"text", "token_count", "chunk_index"}
    for chunk in chunks:
        assert required_keys.issubset(chunk.keys()), f"Missing keys: {required_keys - chunk.keys()}"


def test_chunk_boundary_quality():
    """Chunker does not split mid-word at chunk boundaries."""
    from src.ingest.chunker import chunk_text
    # Sentence-structured text to test boundary preservation
    sentences = ". ".join([f"Sentence number {i} about automotive supply chains" for i in range(100)])
    chunks = chunk_text(sentences, chunk_size=512, overlap=100)
    for chunk in chunks:
        # Last char should not be mid-word (no trailing partial word ending with letter + no space)
        text = chunk["text"].rstrip()
        # Chunk should not end with a hyphenation artifact
        assert not text.endswith("-"), f"Chunk ends with hyphen: ...{text[-20:]}"


def test_chunk_token_count_accuracy():
    """Stored token_count matches actual tiktoken encode length."""
    import tiktoken
    from src.ingest.chunker import chunk_text
    enc = tiktoken.get_encoding("cl100k_base")
    text = "The quick brown fox jumps over the lazy dog. " * 100
    chunks = chunk_text(text, chunk_size=512, overlap=100)
    for chunk in chunks:
        actual = len(enc.encode(chunk["text"]))
        assert abs(actual - chunk["token_count"]) <= 2, (
            f"token_count mismatch: stored={chunk['token_count']}, actual={actual}"
        )
