"""Shared DB singletons for GraphRAG Factory agents.

Both pipeline_rag_agent and search_rag_agent run in the same process under
adk web. KuzuDB only permits one kuzu.Database instance per process per path —
a second open attempt raises a file lock error.

All tool modules import _get_kuzu_db(), _get_sqlite_conn(), and
_get_chroma_client() from here so the process holds exactly one handle each.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env", override=True)

_SQLITE_PATH = str(_PROJECT_ROOT / "data" / "chunks.db")
_KUZU_PATH   = str(_PROJECT_ROOT / "data" / "kuzu_db")
_CHROMA_PATH = str(_PROJECT_ROOT / "data" / "chroma_db")

_sqlite_conn   = None
_kuzu_db       = None
_chroma_client = None


def _get_sqlite_conn() -> sqlite3.Connection:
    global _sqlite_conn
    if _sqlite_conn is None:
        _sqlite_conn = sqlite3.connect(_SQLITE_PATH, check_same_thread=False)
        _sqlite_conn.row_factory = sqlite3.Row
        _sqlite_conn.execute("PRAGMA journal_mode=WAL")
    return _sqlite_conn


def _get_kuzu_db():
    global _kuzu_db
    if _kuzu_db is None:
        import kuzu
        _kuzu_db = kuzu.Database(_KUZU_PATH)
    return _kuzu_db


def _get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        import chromadb
        _chroma_client = chromadb.PersistentClient(path=_CHROMA_PATH)
    return _chroma_client
