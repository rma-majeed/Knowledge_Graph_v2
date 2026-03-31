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


# ---------------------------------------------------------------------------
# Phase 7: RAG retrieval quality fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bm25_corpus():
    """Small in-memory chunk corpus for BM25 index unit tests.

    Returns a list of dicts matching the chunk shape used in retriever.py:
      {chunk_id, text, filename, page_num, source, distance}
    """
    return [
        {"chunk_id": "1", "text": "warranty claims management automation reduces processing time", "filename": "a.pdf", "page_num": 1, "source": "vector", "distance": 0.1},
        {"chunk_id": "2", "text": "electric vehicle battery supply chain optimization", "filename": "b.pdf", "page_num": 2, "source": "vector", "distance": 0.2},
        {"chunk_id": "3", "text": "supplier quality audit findings for tier-2 automotive parts", "filename": "c.pdf", "page_num": 3, "source": "vector", "distance": 0.3},
        {"chunk_id": "4", "text": "warranty cost reduction through predictive analytics", "filename": "a.pdf", "page_num": 4, "source": "vector", "distance": 0.4},
        {"chunk_id": "5", "text": "OEM partnership strategy for electric vehicle platforms", "filename": "b.pdf", "page_num": 5, "source": "vector", "distance": 0.5},
    ]


@pytest.fixture
def mock_reranker_scores():
    """Pre-computed reranker scores for a fixed (query, passage) set.

    Simulates the output of CrossEncoder.predict() — a list of floats, one per
    (query, passage) pair. Order matches bm25_corpus fixture.
    """
    return [0.92, 0.31, 0.15, 0.88, 0.42]


@pytest.fixture
def sample_enriched_chunks():
    """Chunks with enriched_text field set (as stored after contextual enrichment).

    Used to verify that truncate_to_budget prefers enriched_text when available.
    """
    return [
        {
            "chunk_id": "10",
            "text": "original chunk text about warranty",
            "enriched_text": "Context: This passage is from a consulting report on warranty management. warranty claims automation reduces cost",
            "filename": "warranty_report.pdf",
            "page_num": 7,
            "source": "vector",
            "distance": 0.1,
        },
        {
            "chunk_id": "11",
            "text": "original text about EV strategy",
            "enriched_text": None,
            "filename": "ev_report.pdf",
            "page_num": 2,
            "source": "vector",
            "distance": 0.2,
        },
    ]


@pytest.fixture
def chunk_parent_map():
    """Mapping of child_chunk_id -> parent_chunk_id for parent-doc retrieval tests."""
    return {
        "10": "10",   # identity mapping: v1 uses existing chunks as own parents
        "11": "11",
        "1": "1",
        "2": "2",
    }
