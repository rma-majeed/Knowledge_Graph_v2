"""Shared pytest fixtures for Phase 1 tests."""
import pytest
import sqlite3
from pathlib import Path


def pytest_configure(config):
    """Register custom marks to suppress PytestUnknownMarkWarning."""
    config.addinivalue_line(
        "markers", "integration: marks tests that require external services (e.g. LM Studio)"
    )
    config.addinivalue_line(
        "markers", "lm_studio: marks tests that require LM Studio running locally"
    )


@pytest.fixture(autouse=True)
def reset_chromadb_state():
    """Reset ChromaDB EphemeralClient in-process state before each test.

    ChromaDB's EphemeralClient shares module-level in-memory state across
    instances in the same process. Without this reset, tests that use
    EphemeralClient with the same collection name bleed data into each other.
    Uses SharedSystemClient.clear_system_cache() to flush the shared singleton.
    """
    try:
        from chromadb.api.shared_system_client import SharedSystemClient
        SharedSystemClient.clear_system_cache()
    except Exception:
        pass  # ChromaDB not installed or API changed — no-op
    yield

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def sample_pdf_path() -> Path:
    """Path to synthetic sample PDF fixture."""
    path = FIXTURES_DIR / "sample.pdf"
    assert path.exists(), f"Fixture not found: {path}. Run: python tests/fixtures/make_fixtures.py"
    return path


@pytest.fixture(scope="session")
def sample_pptx_path() -> Path:
    """Path to synthetic sample PPTX fixture."""
    path = FIXTURES_DIR / "sample.pptx"
    assert path.exists(), f"Fixture not found: {path}. Run: python tests/fixtures/make_fixtures.py"
    return path


@pytest.fixture
def tmp_db_path(tmp_path) -> Path:
    """Fresh SQLite database path for each test (auto-cleaned by pytest)."""
    return tmp_path / "test_chunks.db"


@pytest.fixture
def tmp_db_conn(tmp_db_path):
    """Open SQLite connection to a fresh temp database. Closes after test."""
    conn = sqlite3.connect(str(tmp_db_path))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Phase 6: Provider configuration fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_env_lmstudio(monkeypatch):
    """Simulate .env with LM Studio as both LLM and embed provider (the default)."""
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("EMBED_PROVIDER", raising=False)
    monkeypatch.delenv("EMBED_MODEL", raising=False)
    monkeypatch.delenv("EMBED_API_KEY", raising=False)


@pytest.fixture
def mock_env_openai(monkeypatch):
    """Simulate .env configured for OpenAI as both LLM and embed provider."""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    monkeypatch.setenv("LLM_API_KEY", "sk-test-openai-key")
    monkeypatch.setenv("EMBED_PROVIDER", "openai")
    monkeypatch.setenv("EMBED_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("EMBED_API_KEY", "sk-test-openai-key")


@pytest.fixture
def mock_env_ollama(monkeypatch):
    """Simulate .env configured for Ollama (local, no API key required)."""
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_MODEL", "llama2")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("EMBED_PROVIDER", "ollama")
    monkeypatch.setenv("EMBED_MODEL", "nomic-embed-text")
    monkeypatch.delenv("EMBED_API_KEY", raising=False)


@pytest.fixture
def mock_env_gemini(monkeypatch):
    """Simulate .env configured for Google Gemini."""
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_MODEL", "gemini/gemini-2.5-flash")
    monkeypatch.setenv("LLM_API_KEY", "test-gemini-api-key")
    monkeypatch.setenv("EMBED_PROVIDER", "gemini")
    monkeypatch.setenv("EMBED_MODEL", "gemini/text-embedding-004")
    monkeypatch.setenv("EMBED_API_KEY", "test-gemini-api-key")


@pytest.fixture
def mock_env_anthropic(monkeypatch):
    """Simulate .env configured for Anthropic (LLM only — no embedding support)."""
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MODEL", "anthropic/claude-sonnet-4-5")
    monkeypatch.setenv("LLM_API_KEY", "test-anthropic-api-key")
