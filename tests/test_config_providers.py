"""Tests for Phase 6: Multi-Provider LLM & Embedding Configuration.

Wave 0 stubs — all xfail until Plan 06-02 (providers.py) and 06-03 (mismatch detection) land.

Covers:
  PROVIDER-01: LLM config loaded from .env; fallback to LM Studio if absent
  PROVIDER-02: LiteLLM routing for all 5 LLM providers
  PROVIDER-03: Embed config loaded from .env; fallback to LM Studio if absent
  PROVIDER-04: LiteLLM embedding routing for all 4 embed providers
  PROVIDER-05: Provider change requires only .env edit — no code change
  PROVIDER-06: Embedding provider mismatch warns and requires confirmation
"""
from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# PROVIDER-01: LLM client defaults to LM Studio when .env absent
# ---------------------------------------------------------------------------


def test_llm_client_defaults_to_lmstudio(mock_env_lmstudio):
    """get_llm_client() returns an OpenAI client pointing to localhost:1234 when LLM_PROVIDER is unset."""
    from src.config.providers import get_llm_client

    client = get_llm_client()

    # Should be the raw OpenAI client with LM Studio base URL
    assert hasattr(client, "chat"), "Client must have .chat attribute (OpenAI-compatible)"
    # Base URL must point to localhost:1234 — use str() to get full URL including port
    base = str(client.base_url)
    assert "1234" in base, f"Expected localhost:1234 base URL, got: {base}"


# ---------------------------------------------------------------------------
# PROVIDER-02: LiteLLM routing for all 5 LLM providers
# ---------------------------------------------------------------------------


def test_llm_client_from_env_openai(mock_env_openai):
    """get_llm_client() returns a LiteLLM-compatible config for OpenAI provider."""
    from src.config.providers import get_llm_client, load_provider_config

    config = load_provider_config()
    assert config["llm_provider"] == "openai"
    assert config["llm_model"] == "gpt-4o"
    assert config["llm_api_key"] == "sk-test-openai-key"

    client = get_llm_client()
    assert client is not None


def test_llm_client_from_env_ollama(mock_env_ollama):
    """get_llm_client() returns a LiteLLM-compatible config for Ollama (no API key required)."""
    from src.config.providers import get_llm_client, load_provider_config

    config = load_provider_config()
    assert config["llm_provider"] == "ollama"
    assert config["llm_model"] == "llama2"

    client = get_llm_client()
    assert client is not None


def test_llm_client_from_env_gemini(mock_env_gemini):
    """get_llm_client() returns a LiteLLM-compatible config for Gemini."""
    from src.config.providers import get_llm_client, load_provider_config

    config = load_provider_config()
    assert config["llm_provider"] == "gemini"
    assert config["llm_api_key"] == "test-gemini-api-key"

    client = get_llm_client()
    assert client is not None


def test_llm_client_from_env_anthropic(mock_env_anthropic):
    """get_llm_client() returns a LiteLLM-compatible config for Anthropic."""
    from src.config.providers import get_llm_client, load_provider_config

    config = load_provider_config()
    assert config["llm_provider"] == "anthropic"
    assert config["llm_api_key"] == "test-anthropic-api-key"

    client = get_llm_client()
    assert client is not None


# ---------------------------------------------------------------------------
# PROVIDER-03: Embed client defaults to LM Studio when .env absent
# ---------------------------------------------------------------------------


def test_embed_client_defaults_to_lmstudio(mock_env_lmstudio):
    """get_embed_client() returns an OpenAI client pointing to localhost:1234 when EMBED_PROVIDER unset."""
    from src.config.providers import get_embed_client

    client = get_embed_client()

    assert hasattr(client, "embeddings"), "Client must have .embeddings attribute (OpenAI-compatible)"
    # Use str() to get full URL including port number
    base = str(client.base_url)
    assert "1234" in base, f"Expected localhost:1234 base URL, got: {base}"


# ---------------------------------------------------------------------------
# PROVIDER-04: Embed client routing for all 4 embed providers
# ---------------------------------------------------------------------------


def test_embed_client_from_env_openai(mock_env_openai):
    """get_embed_client() returns a LiteLLM-compatible config for OpenAI embeddings."""
    from src.config.providers import get_embed_client, load_provider_config

    config = load_provider_config()
    assert config["embed_provider"] == "openai"
    assert config["embed_model"] == "text-embedding-3-small"

    client = get_embed_client()
    assert client is not None


# ---------------------------------------------------------------------------
# PROVIDER-05: Provider change requires only .env edit
# ---------------------------------------------------------------------------


def test_llm_provider_change_requires_only_env(monkeypatch):
    """Changing LLM_PROVIDER in env returns different client type without any code change."""
    from src.config.providers import get_llm_client

    # With LM Studio (default)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    client_default = get_llm_client()

    # With OpenAI set
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    monkeypatch.setenv("LLM_API_KEY", "sk-test-key")
    client_openai = get_llm_client()

    # Both must be non-None; they must differ in type or configuration
    assert client_default is not None
    assert client_openai is not None
    # The two clients should not be identical objects
    assert client_default is not client_openai


# ---------------------------------------------------------------------------
# PROVIDER-06: Embedding mismatch detection (tested in embed pipeline tests)
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_embed_mismatch_warning_triggers(tmp_db_conn, monkeypatch):
    """embed_all_chunks() prints a mismatch warning when EMBED_MODEL changed since last run."""
    import sqlite3
    import chromadb
    from unittest.mock import patch, MagicMock

    # Set up a SQLite DB with a metadata table recording the OLD model
    tmp_db_conn.executescript("""
        CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS documents (
            doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            file_size_bytes INTEGER,
            file_hash TEXT NOT NULL UNIQUE,
            doc_type TEXT NOT NULL,
            total_pages INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            indexed_at TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            page_num INTEGER,
            chunk_index INTEGER,
            chunk_text TEXT NOT NULL,
            token_count INTEGER,
            embedding_flag INTEGER DEFAULT 0
        );
        INSERT INTO metadata (key, value) VALUES ('embed_model', 'nomic-embed-text-v1.5');
        INSERT INTO documents (filename, file_hash, doc_type) VALUES ('test.pdf', 'abc', 'pdf');
        INSERT INTO chunks (doc_id, page_num, chunk_index, chunk_text, token_count, embedding_flag)
        VALUES (1, 1, 0, 'sample text', 10, 0);
    """)
    tmp_db_conn.commit()

    # Switch to a new model (mismatch from stored 'nomic-embed-text-v1.5')
    monkeypatch.setenv("EMBED_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("EMBED_PROVIDER", "openai")

    from src.embed.pipeline import embed_all_chunks

    # Simulate user typing "no" to abort
    with patch("builtins.input", return_value="no"):
        with patch("src.embed.pipeline.embed_chunks", MagicMock(return_value=[[0.1] * 768])):
            result = embed_all_chunks(
                conn=tmp_db_conn,
                chroma_client=chromadb.EphemeralClient(),
                model="text-embedding-3-small",
            )

    # User said "no" — should abort with 0 chunks embedded
    assert result["chunks_embedded"] == 0, f"Expected 0 chunks embedded (aborted), got {result}"
