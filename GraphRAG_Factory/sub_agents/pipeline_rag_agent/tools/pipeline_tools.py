"""Pipeline RAG tool — wraps the full 10-step answer_question() pipeline.

DB connections are module-level singletons, initialized lazily on first call.
This avoids passing complex objects through the ADK tool calling interface.
"""
from __future__ import annotations

import os
import sys
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

# Resolve project root (4 levels up from this file) and load .env
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env", override=True)

# Ensure src/ is importable when running via adk web
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# --- Lazy singletons ---

_sqlite_conn: sqlite3.Connection | None = None
_kuzu_db = None
_openai_client = None


def _get_sqlite_conn() -> sqlite3.Connection:
    global _sqlite_conn
    if _sqlite_conn is None:
        db_path = str(_PROJECT_ROOT / "data" / "chunks.db")
        _sqlite_conn = sqlite3.connect(db_path, check_same_thread=False)
        _sqlite_conn.row_factory = sqlite3.Row
        _sqlite_conn.execute("PRAGMA journal_mode=WAL")
    return _sqlite_conn


def _get_kuzu_db():
    global _kuzu_db
    if _kuzu_db is None:
        import kuzu
        kuzu_path = str(_PROJECT_ROOT / "data" / "kuzu_db")
        _kuzu_db = kuzu.Database(kuzu_path)
    return _kuzu_db


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        from src.config.providers import get_llm_client
        _openai_client = get_llm_client()
    return _openai_client


# --- Tool ---

def full_rag_query(question: str) -> dict:
    """Run the full 10-step GraphRAG pipeline for the given question.

    Performs query rewriting, BM25 + vector search, RRF fusion, graph
    expansion, optional reranking, parent-doc expansion, context assembly,
    and LLM-based answer generation with citations.

    Args:
        question: The automotive consulting question to answer.

    Returns:
        A dict with:
        - status: "success" or "error"
        - answer: Full answer text with inline [N] citation markers
        - citations: List of dicts [{index, filename, page_num, confidence, source}]
        - elapsed_s: Wall-clock seconds for retrieve + generate
        - error: Error message string (only present when status is "error")
    """
    try:
        from src.query.pipeline import answer_question

        chroma_path = str(_PROJECT_ROOT / "data" / "chroma_db")
        llm_model = os.getenv("LLM_MODEL", "google/gemma-3n-e4b")
        embed_model = os.getenv("EMBED_MODEL", "text-embedding-nomic-embed-text-v1.5")

        result = answer_question(
            question=question,
            conn=_get_sqlite_conn(),
            kuzu_db=_get_kuzu_db(),
            chroma_path=chroma_path,
            embed_model=embed_model,
            llm_model=llm_model,
            openai_client=_get_openai_client(),
        )
        return {
            "status": "success",
            "answer": result.get("answer", ""),
            "citations": result.get("citations", []),
            "elapsed_s": result.get("elapsed_s", 0.0),
        }
    except Exception as exc:
        return {
            "status": "error",
            "answer": "",
            "citations": [],
            "elapsed_s": 0.0,
            "error": str(exc),
        }
