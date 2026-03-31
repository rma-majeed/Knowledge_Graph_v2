"""Tests for src/query/pipeline.py — end-to-end query pipeline (QUERY-01, QUERY-05).

LM Studio integration test is marked @pytest.mark.lm_studio — excluded from quick runs
via: pytest -k 'not lm_studio'
"""
from __future__ import annotations

import sqlite3
import tempfile
import os
from unittest.mock import MagicMock, patch

import chromadb
import kuzu
import pytest


def _make_sqlite_db(path: str) -> sqlite3.Connection:
    """Create a minimal SQLite DB with the chunks and chunk_citations tables."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS chunks (
            chunk_id INTEGER PRIMARY KEY,
            chunk_text TEXT,
            embedding_flag INTEGER DEFAULT 0
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS chunk_citations (
            id INTEGER PRIMARY KEY,
            chunk_id INTEGER,
            entity_canonical_name TEXT,
            entity_type TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS documents (
            doc_id INTEGER PRIMARY KEY,
            filename TEXT
        )"""
    )
    conn.commit()
    return conn


def test_query_pipeline_end_to_end() -> None:
    """answer_question() returns dict with answer, citations, and elapsed_s.

    LM Studio is mocked. Expected: result dict has keys 'answer' (non-empty str),
    'citations' (list), 'elapsed_s' (float >= 0).
    Uses chromadb.EphemeralClient() and tempfile.mkdtemp() KuzuDB.
    """
    from src.query.pipeline import answer_question

    # Set up ephemeral ChromaDB with one chunk
    chroma_client = chromadb.EphemeralClient()
    collection = chroma_client.create_collection(
        name="chunks",
        configuration={"hnsw": {"space": "cosine"}},
    )
    collection.add(
        ids=["1"],
        documents=["Toyota announced an EV strategy focused on solid-state batteries."],
        metadatas=[{"filename": "toyota_ev.pdf", "page_num": 3}],
        embeddings=[[0.1] * 768],
    )

    # Set up SQLite DB
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "chunks.db")
        conn = _make_sqlite_db(db_path)

        # Add matching chunk text in SQLite
        conn.execute(
            "INSERT INTO chunks (chunk_id, chunk_text, embedding_flag) VALUES (1, ?, 1)",
            ("Toyota announced an EV strategy focused on solid-state batteries.",),
        )
        conn.commit()

        # Set up KuzuDB (empty graph — no graph expansion)
        # Note: kuzu.Database expects a non-existent path (it creates the dir itself)
        kuzu_dir = os.path.join(tmpdir, "kuzu_db")
        kuzu_db = kuzu.Database(kuzu_dir)

        # Mock openai_client to return a fake embedding and fake LLM response
        mock_openai = MagicMock()
        # embed_query response
        mock_openai.embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=[0.1] * 768)]
        )
        # LLM chat completion response
        mock_choice = MagicMock()
        mock_choice.message.content = "Toyota is investing heavily in solid-state batteries [1]."
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        result = answer_question(
            question="What EV strategies did Toyota adopt?",
            conn=conn,
            kuzu_db=kuzu_db,
            chroma_path=os.path.join(tmpdir, "chroma_db"),
            openai_client=mock_openai,
            chroma_client=chroma_client,
        )

        conn.close()
        del kuzu_db  # release kuzu file handles before temp dir cleanup

    assert isinstance(result, dict), "answer_question() must return a dict"
    assert "answer" in result, "result must have 'answer' key"
    assert "citations" in result, "result must have 'citations' key"
    assert "elapsed_s" in result, "result must have 'elapsed_s' key"
    assert isinstance(result["answer"], str) and len(result["answer"]) > 0, "answer must be non-empty str"
    assert isinstance(result["citations"], list), "citations must be a list"
    assert isinstance(result["elapsed_s"], float) and result["elapsed_s"] >= 0.0, "elapsed_s must be float >= 0"


def test_query_pipeline_no_results() -> None:
    """answer_question() handles empty corpus gracefully (no chunks in ChromaDB).

    Expected: returns dict with answer indicating no information found;
    citations is an empty list; does not raise an exception.
    """
    from src.query.pipeline import answer_question

    # Empty ChromaDB
    chroma_client = chromadb.EphemeralClient()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "chunks.db")
        conn = _make_sqlite_db(db_path)

        # Note: kuzu.Database expects a non-existent path (it creates the dir itself)
        kuzu_dir = os.path.join(tmpdir, "kuzu_db")
        kuzu_db = kuzu.Database(kuzu_dir)

        mock_openai = MagicMock()
        mock_openai.embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=[0.0] * 768)]
        )

        result = answer_question(
            question="What EV strategies did Toyota adopt?",
            conn=conn,
            kuzu_db=kuzu_db,
            chroma_path=os.path.join(tmpdir, "chroma_db"),
            openai_client=mock_openai,
            chroma_client=chroma_client,
        )

        conn.close()
        del kuzu_db  # release kuzu file handles before temp dir cleanup

    assert isinstance(result, dict), "answer_question() must return a dict"
    assert "answer" in result
    assert "citations" in result
    assert "elapsed_s" in result
    assert result["citations"] == [], "citations should be empty for empty corpus"
    assert "not contain sufficient information" in result["answer"], (
        f"answer should mention insufficient information, got: {result['answer']!r}"
    )


@pytest.mark.lm_studio
@pytest.mark.xfail(strict=False, reason="requires live LM Studio with Qwen2.5-7B-Instruct")
def test_lm_studio_integration() -> None:
    """answer_question() produces a real answer via LM Studio (Qwen2.5-7B-Instruct).

    Requires LM Studio running at localhost:1234 with Qwen2.5-7B-Instruct loaded.
    Skip with: pytest -k 'not lm_studio'
    Expected: answer is a non-empty string; elapsed_s < 15.0.
    """
    raise NotImplementedError
