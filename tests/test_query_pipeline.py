"""Tests for src/query/pipeline.py — end-to-end query pipeline (QUERY-01, QUERY-05).

Stubs become passing once plan 04-04 implements answer_question().
LM Studio integration test is marked @pytest.mark.lm_studio — excluded from quick runs
via: pytest -k 'not lm_studio'
"""
from __future__ import annotations

import pytest


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_query_pipeline_end_to_end() -> None:
    """answer_question() returns dict with answer, citations, and elapsed_s.

    LM Studio is mocked (unittest.mock.patch). Expected: result dict has keys
    'answer' (non-empty str), 'citations' (list), 'elapsed_s' (float >= 0).
    Uses chromadb.EphemeralClient() and tempfile.mkdtemp() KuzuDB.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_query_pipeline_no_results() -> None:
    """answer_question() handles empty corpus gracefully (no chunks in ChromaDB).

    Expected: returns dict with answer indicating no information found;
    citations is an empty list; does not raise an exception.
    """
    raise NotImplementedError


@pytest.mark.lm_studio
@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_lm_studio_integration() -> None:
    """answer_question() produces a real answer via LM Studio (Qwen2.5-7B-Instruct).

    Requires LM Studio running at localhost:1234 with Qwen2.5-7B-Instruct loaded.
    Skip with: pytest -k 'not lm_studio'
    Expected: answer is a non-empty string; elapsed_s < 15.0.
    """
    raise NotImplementedError
