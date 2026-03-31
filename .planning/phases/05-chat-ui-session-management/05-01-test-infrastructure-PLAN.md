---
phase: 05-chat-ui-session-management
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - app.py
  - tests/test_chat_app.py
autonomous: true
requirements:
  - UI-01
  - UI-02

must_haves:
  truths:
    - "pytest tests/test_chat_app.py -x -q -k 'not lm_studio' collects all stubs and reports xfail (not errors or import failures)"
    - "app.py exists at project root and raises NotImplementedError when executed as a module"
    - "AppTest.from_file('app.py') can be constructed without ImportError (app.py is importable)"
  artifacts:
    - path: "app.py"
      provides: "NotImplementedError stub — Streamlit entry point placeholder"
    - path: "tests/test_chat_app.py"
      provides: "xfail stubs for UI-01 and UI-02 covering 4 test scenarios"
  key_links:
    - from: "tests/test_chat_app.py"
      to: "app.py"
      via: "AppTest.from_file('app.py')"
      pattern: "AppTest.from_file"
    - from: "tests/test_chat_app.py"
      to: "src.query.pipeline"
      via: "patch('src.query.pipeline.answer_question', ...)"
      pattern: "patch.*answer_question"
---

<objective>
Create the Wave 1 test scaffold (xfail stubs) and app.py stub for Phase 5 Chat UI & Session Management.

Purpose: Establish xfail test stubs using Streamlit AppTest and a NotImplementedError app.py stub before implementation begins. This mirrors the Wave 1 pattern used in Phases 2, 3, and 4 exactly. All stubs become passing once plans 05-02 and 05-03 implement the real code.

Output: 1 test file with 4 xfail stubs (tests/test_chat_app.py), 1 app.py stub at project root.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/05-chat-ui-session-management/05-RESEARCH.md

<interfaces>
<!-- answer_question() signature from src/query/pipeline.py (Phase 4) -->
```python
def answer_question(
    question: str,
    conn: sqlite3.Connection,
    kuzu_db: kuzu.Database,
    chroma_path: str = "data/chroma_db",
    embed_model: str = DEFAULT_EMBED_MODEL,
    llm_model: str = DEFAULT_LLM_MODEL,
    n_results: int = 10,
    openai_client=None,
    chroma_client=None,
) -> dict:
    # Returns: {"answer": str, "citations": list[dict], "elapsed_s": float}
```

<!-- AppTest pattern for Streamlit unit tests — Streamlit 1.47.0 -->
```python
from streamlit.testing.v1 import AppTest
from unittest.mock import patch

at = AppTest.from_file("app.py")
at.run()
at.chat_input[0].set_value("question text").run()
# Assertions on at.chat_message, at.error, at.markdown etc.
```

<!-- xfail stub pattern (established in Phases 2-4) -->
```python
@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_example() -> None:
    """Docstring describing what will be tested."""
    raise NotImplementedError
```

<!-- Mock result shape for answer_question() -->
mock_result = {
    "answer": "Test answer text",
    "citations": [{"index": 1, "filename": "report.pdf", "page_num": 3, "confidence": "HIGH"}],
    "elapsed_s": 2.5,
}
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create app.py stub at project root</name>
  <files>app.py</files>

  <read_first>
    - src/main.py (review sys.path guard pattern — replicate in app.py stub)
  </read_first>

  <action>
Create `app.py` at the project root as a minimal stub that:
1. Includes the sys.path guard (same pattern as src/main.py) so `from src.query.pipeline import answer_question` will resolve when `streamlit run app.py` is executed from project root.
2. Raises NotImplementedError when run, making all AppTest calls fail predictably until plan 05-02 implements the real app.

```python
"""Automotive Consulting GraphRAG — Streamlit Chat Interface.

Stub — Phase 5 plan 05-02 implements this.
"""
from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

raise NotImplementedError("app.py not yet implemented — see plan 05-02")
```

This stub is intentionally minimal: AppTest.from_file("app.py") will import it successfully (no ImportError), but running the app raises NotImplementedError, making all xfail stubs fail correctly until plan 05-02 replaces this file.
  </action>

  <verify>
    <automated>cd "C:/Users/2171176/Documents/Python/Knowledge_Graph_v2" && python -c "import ast; ast.parse(open('app.py').read()); print('app.py parses OK')"</automated>
  </verify>

  <done>app.py exists at project root, parses without syntax error, and contains the sys.path guard and NotImplementedError raise.</done>
</task>

<task type="auto">
  <name>Task 2: Create xfail test stubs in tests/test_chat_app.py</name>
  <files>tests/test_chat_app.py</files>

  <read_first>
    - tests/test_query_pipeline.py (review xfail + lm_studio marker pattern — replicate for lm_studio test)
    - conftest.py (confirm lm_studio marker is already registered before writing @pytest.mark.lm_studio)
  </read_first>

  <action>
Create `tests/test_chat_app.py` with 4 xfail stubs covering UI-01 and UI-02. All stubs use `@pytest.mark.xfail(strict=False, reason="not implemented yet")` and raise NotImplementedError.

```python
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
```
  </action>

  <verify>
    <automated>cd "C:/Users/2171176/Documents/Python/Knowledge_Graph_v2" && python -m pytest tests/test_chat_app.py -x -q -k "not lm_studio" 2>&1 | tail -5</automated>
  </verify>

  <done>All 4 xfail stubs collected without import errors; pytest reports xfailed (not ERROR); -k "not lm_studio" works cleanly (no PytestUnknownMarkWarning); full prior test suite still green.</done>
</task>

</tasks>

<verification>
```bash
# Stubs collect and report xfail (not import errors)
cd "C:/Users/2171176/Documents/Python/Knowledge_Graph_v2"
python -m pytest tests/test_chat_app.py -x -q -k "not lm_studio"

# app.py parses and has sys.path guard
python -c "import ast; ast.parse(open('app.py').read()); print('app.py parses OK')"

# Full prior suite unaffected
python -m pytest tests/ -x -q -k "not lm_studio" --tb=short 2>&1 | tail -5
```
</verification>

<success_criteria>
- pytest collects all 4 xfail stubs from tests/test_chat_app.py without import errors or collection errors
- pytest -k "not lm_studio" filters correctly with no PytestUnknownMarkWarning
- app.py exists at project root, is syntactically valid, contains sys.path guard
- Full prior test suite (phases 1-4) still green: pytest tests/ -x -q -k "not lm_studio" exits 0
</success_criteria>

<output>
After completion, create `.planning/phases/05-chat-ui-session-management/05-01-SUMMARY.md`
</output>
