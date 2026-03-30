"""Shared pytest fixtures for Phase 1 tests."""
import pytest
import sqlite3
from pathlib import Path


def pytest_configure(config):
    """Register custom marks to suppress PytestUnknownMarkWarning."""
    config.addinivalue_line(
        "markers", "integration: marks tests that require external services (e.g. LM Studio)"
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
