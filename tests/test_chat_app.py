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

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from streamlit.testing.v1 import AppTest


_APP_PATH = str(Path(__file__).parent.parent / "app.py")

# Shared mock fixtures to prevent actual network/DB calls in every test
_MOCK_ANSWER = {"answer": "Test answer about EVs", "citations": [], "elapsed_s": 2.5}
_MOCK_CONN = MagicMock()
_MOCK_KUZU_DB = MagicMock()
_MOCK_OAI = MagicMock()


def _make_at(timeout: int = 30) -> AppTest:
    """Create AppTest instance."""
    return AppTest.from_file(_APP_PATH, default_timeout=timeout)


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_app_renders_empty_chat() -> None:
    """AppTest loads app.py and shows an empty chat with no messages initially.

    Expected: AppTest.from_file("app.py").run() succeeds without exception;
    no chat_message elements are rendered on first load (no pre-populated history);
    a chat_input widget is present and accepting input.
    """
    with (
        patch("src.embed.pipeline.check_lm_studio", return_value=False),
        patch("src.query.pipeline.answer_question", return_value=_MOCK_ANSWER),
        patch("kuzu.Database", return_value=_MOCK_KUZU_DB),
        patch("sqlite3.connect", return_value=_MOCK_CONN),
    ):
        at = _make_at()
        at.run()

    assert not at.exception, f"App raised: {at.exception}"
    # No messages pre-populated
    assert len(at.chat_message) == 0
    # Chat input is present
    assert len(at.chat_input) >= 1


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
    mock_result = {"answer": "Test answer about EVs", "citations": [], "elapsed_s": 2.5}

    with (
        patch("src.embed.pipeline.check_lm_studio", return_value=False),
        patch("src.query.pipeline.answer_question", return_value=mock_result),
        patch("kuzu.Database", return_value=_MOCK_KUZU_DB),
        patch("sqlite3.connect", return_value=_MOCK_CONN),
    ):
        at = _make_at()
        at.run()
        at.chat_input[0].set_value("What EVs did we work on?").run()

    assert not at.exception, f"App raised: {at.exception}"

    # Find assistant response containing the answer text
    all_text = " ".join(
        elem.value
        for m in at.chat_message
        if m.name == "assistant"
        for elem in m.markdown
    )
    assert "Test answer about EVs" in all_text


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_chat_history_persists() -> None:
    """Two sequential question submissions both appear in chat history (UI-02).

    Setup: mock answer_question to return distinct answers for two calls.
    Action: submit first question, then submit second question.
    Expected: both user questions and both assistant answers appear in the
    rendered chat_message elements after the second submission; neither is lost.
    """
    answers = [
        {"answer": "First answer about Toyota", "citations": [], "elapsed_s": 1.0},
        {"answer": "Second answer about Honda", "citations": [], "elapsed_s": 1.5},
    ]

    with (
        patch("src.embed.pipeline.check_lm_studio", return_value=False),
        patch("src.query.pipeline.answer_question", side_effect=answers),
        patch("kuzu.Database", return_value=_MOCK_KUZU_DB),
        patch("sqlite3.connect", return_value=_MOCK_CONN),
    ):
        at = _make_at()
        at.run()
        at.chat_input[0].set_value("Tell me about Toyota").run()
        at.chat_input[0].set_value("Tell me about Honda").run()

    assert not at.exception, f"App raised: {at.exception}"

    all_text = " ".join(
        elem.value
        for m in at.chat_message
        if m.markdown
        for elem in m.markdown
    )
    assert "First answer about Toyota" in all_text
    assert "Second answer about Honda" in all_text


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_lm_studio_error_shows_friendly_message() -> None:
    """When answer_question() raises an exception, user sees a friendly error (no stack trace).

    Setup: mock answer_question to raise Exception("Connection refused").
    Action: at.chat_input[0].set_value("Any question").run()
    Expected: at.error is non-empty (st.error was called); the error message text
    does not contain "Traceback", "Exception", or raw Python error details;
    the app does not crash (AppTest.run() completes without raising).
    """
    with (
        patch(
            "src.query.pipeline.answer_question",
            side_effect=Exception("Connection refused"),
        ),
        patch("src.embed.pipeline.check_lm_studio", return_value=False),
        patch("kuzu.Database", return_value=_MOCK_KUZU_DB),
        patch("sqlite3.connect", return_value=_MOCK_CONN),
    ):
        at = _make_at()
        at.run()
        at.chat_input[0].set_value("Any question").run()

    assert not at.exception, f"App crashed: {at.exception}"
    # st.error was called
    assert len(at.error) > 0
    error_text = at.error[0].value
    # No raw Python traceback details exposed
    assert "Traceback" not in error_text
    assert "Exception" not in error_text
