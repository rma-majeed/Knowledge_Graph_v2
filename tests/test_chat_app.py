"""Tests for app.py — Streamlit chat interface (UI-01, UI-02).

All tests are xfail stubs. They become passing once plan 05-02 implements
the core chat app and plan 05-03 adds citation display and error handling.

Test isolation:
  - Use AppTest.from_file("app.py") — never import app.py directly
  - Mock answer_question via patch("src.query.pipeline.answer_question", ...)
  - No real LM Studio calls in unit tests
  - lm_studio marker: excluded from quick runs via: pytest -k "not lm_studio"
"""
from __future__ import annotations

import pytest


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_app_renders_empty_chat() -> None:
    """AppTest loads app.py and shows an empty chat with no messages initially.

    Expected: AppTest.from_file("app.py").run() succeeds without exception;
    no chat_message elements are rendered on first load (no pre-populated history);
    a chat_input widget is present and accepting input.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_chat_input_triggers_response() -> None:
    """Submitting a question via chat_input triggers answer_question() and displays the response.

    Setup: mock answer_question to return {"answer": "Test answer about EVs",
    "citations": [], "elapsed_s": 2.5}.
    Action: at.chat_input[0].set_value("What EVs did we work on?").run()
    Expected: at.chat_message contains an element whose markdown includes "Test answer about EVs";
    answer_question mock was called exactly once with the submitted question.
    Uses patch("src.query.pipeline.answer_question", return_value=mock_result).
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_chat_history_persists() -> None:
    """Two sequential question submissions both appear in chat history (UI-02).

    Setup: mock answer_question to return distinct answers for two calls.
    Action: submit first question, then submit second question.
    Expected: both user questions and both assistant answers appear in the
    rendered chat_message elements after the second submission; neither is lost.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_lm_studio_error_shows_friendly_message() -> None:
    """When answer_question() raises an exception, user sees a friendly error (no stack trace).

    Setup: mock answer_question to raise Exception("Connection refused").
    Action: at.chat_input[0].set_value("Any question").run()
    Expected: at.error is non-empty (st.error was called); the error message text
    does not contain "Traceback", "Exception", or raw Python error details;
    the app does not crash (AppTest.run() completes without raising).
    """
    raise NotImplementedError
