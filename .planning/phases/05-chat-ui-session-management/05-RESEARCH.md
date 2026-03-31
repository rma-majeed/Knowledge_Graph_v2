# Phase 5: Chat UI & Session Management - Research

**Researched:** 2026-03-31
**Domain:** Streamlit chat interface, session state management, LLM pipeline integration, UX error handling
**Confidence:** HIGH — Streamlit 1.47.0 already installed; API signatures verified directly from the installed package; pipeline integration requirements derived from reading actual source code

---

## Summary

Phase 5 adds a single Streamlit app file (`app.py` at project root) that wraps the already-built `answer_question()` pipeline in a browser chat interface. The implementation surface is intentionally small: one file, no new dependencies beyond Streamlit (already installed at 1.47.0), and a narrow integration surface to `src/query/pipeline.py`.

The idiomatic Streamlit chat pattern — `st.chat_message` + `st.chat_input` + `st.session_state` — is stable and well-documented. `st.chat_message` was introduced in Streamlit 1.23.0 and `st.chat_input` in the same release cycle; both are available in the installed 1.47.0 with verified API signatures. Session state persistence across reruns is the standard mechanism and requires only initializing `st.session_state.messages = []` on first load.

The critical architectural decision is connection management. `answer_question()` requires open `sqlite3.Connection` and `kuzu.Database` objects — these must be created once per session (not per query) using `@st.cache_resource` to avoid reconnection overhead on every Streamlit rerun. Citations returned by the pipeline are already formatted as plain text by `format_answer()`; for the UI, the answer text and raw `citations` list will be stored separately in session state to allow rich rendering (expander with citation table) distinct from the raw `answer` string.

**Primary recommendation:** Implement Phase 5 as three plans: (1) test infrastructure with AppTest stubs, (2) the Streamlit app file with chat UI and session state, (3) citation display and error handling polish. All three can be executed serially with no new pip installs required.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-01 | User can interact with the system via a browser-based Streamlit chat interface | `st.chat_message` + `st.chat_input` + `st.session_state` pattern verified in Streamlit 1.47.0; `streamlit run app.py` provides browser URL; no CLI knowledge required |
| UI-02 | Chat history is maintained within a session (user sees previous Q&A pairs) | `st.session_state.messages` list, initialized once on first load, appended on each exchange, rendered in a for loop with `st.chat_message`; survives Streamlit reruns within a browser session |
</phase_requirements>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **streamlit** | 1.47.0 (installed) | Browser chat UI, session state, spinner, expander | Already installed; roadmap-locked decision; provides all required chat primitives |

### Supporting (already installed — no new installs)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **sqlite3** | stdlib | Open `chunks.db` connection for pipeline | `@st.cache_resource` wrapped connector; reused across reruns |
| **kuzu** | 0.11.3 (installed) | Open `kuzu_db` connection for pipeline | Same `@st.cache_resource` pattern |
| **httpx** | 0.28.1 (installed) | LM Studio health check | Reuse existing `check_lm_studio()` from `src.embed.pipeline` |
| **openai** | 1.93.0 (installed) | OpenAI-compatible client for LM Studio | `@st.cache_resource` wrapped; reused across reruns |

### No New Dependencies Required

All required packages are already installed from Phases 1-4. Phase 5 adds zero new `pip install` requirements.

**Installation:**
```bash
# No new dependencies — streamlit 1.47.0 already installed
# Verify:
pip show streamlit  # Should show 1.47.0
```

**Version verification (confirmed 2026-03-31 from installed package):**
- streamlit 1.47.0 — installed, confirmed
- `st.chat_message`, `st.chat_input`, `st.write_stream`, `st.spinner`, `st.status`, `st.cache_resource` — all present in 1.47.0

---

## Architecture Patterns

### Recommended Project Structure

```
Knowledge_Graph_v2/
├── app.py                     # Streamlit entry point (NEW — Phase 5)
├── src/
│   └── query/
│       └── pipeline.py        # answer_question() — already built
├── tests/
│   └── test_ui_app.py         # AppTest-based tests (NEW — Phase 5)
└── data/
    ├── chunks.db
    ├── chroma_db/
    └── kuzu_db/
```

`app.py` lives at project root. The `streamlit run app.py` command is run from the project root, which ensures `src/` imports resolve correctly (same Python path as `python src/main.py`).

### Pattern 1: Chat History with Session State

**What:** Initialize a `messages` list in `st.session_state` on first load; append user and assistant messages after each exchange; render all messages in a loop on every rerun.

**When to use:** Every Streamlit chat app — this is the canonical pattern from official docs.

```python
# Source: https://docs.streamlit.io/develop/tutorials/chat-and-llm-apps/build-conversational-apps
# Initialize chat history once
if "messages" not in st.session_state:
    st.session_state.messages = []  # list of {"role": str, "content": str, "citations": list}

# Render existing chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("citations"):
            _render_citations(msg["citations"])

# Accept new input
if prompt := st.chat_input("Ask a question about your documents..."):
    # Append user message
    st.session_state.messages.append({"role": "user", "content": prompt, "citations": []})
    with st.chat_message("user"):
        st.markdown(prompt)
    # ... call pipeline, render response
```

**Key detail:** `st.chat_input()` returns `None` when no input is submitted and a string when submitted. The walrus operator `:=` is the idiomatic guard. After submission, Streamlit reruns the script from top to bottom — all previous messages are re-rendered from `st.session_state.messages`.

**Message dict schema for this project:**
```python
{
    "role": "user" | "assistant",
    "content": str,          # display text (answer prose, not full format_answer() output)
    "citations": list[dict], # raw citations list from pipeline result; empty for user msgs
    "elapsed_s": float       # query time; 0.0 for user msgs
}
```

Storing raw `citations` separately from `content` is preferable to storing `format_answer()` output. `format_answer()` embeds citations inline as plain text; storing them separately allows the UI to render them in an `st.expander` with richer formatting (bold confidence, page numbers as pill badges) without re-parsing the text.

### Pattern 2: Database Connection Caching with @st.cache_resource

**What:** Wrap expensive one-time initializations (DB connections, OpenAI client) in `@st.cache_resource` so they are created once per app session and reused across all reruns.

**When to use:** Any shared resource that is expensive to recreate and is not user-specific.

```python
# Source: https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_resource
import sqlite3
import kuzu
from openai import OpenAI

DATA_DIR = Path(__file__).parent / "data"

@st.cache_resource
def get_sqlite_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

@st.cache_resource
def get_kuzu_db(graph_path: str) -> kuzu.Database:
    return kuzu.Database(graph_path)

@st.cache_resource
def get_openai_client() -> OpenAI:
    return OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
```

**Critical note on `check_same_thread=False`:** SQLite's default mode rejects calls from threads other than the creating thread. Streamlit runs in a threaded environment; `check_same_thread=False` is required when using `@st.cache_resource` for a SQLite connection.

### Pattern 3: Loading Indicator During Pipeline Call

**What:** Wrap the `answer_question()` call in `st.spinner` to show "Thinking..." while the LLM generates (typically 5-10 seconds).

**When to use:** Any blocking synchronous operation taking > 1 second.

```python
# Source: Streamlit 1.47.0 installed API — st.spinner(text, show_time=False)
with st.spinner("Thinking...", show_time=True):
    result = answer_question(
        question=prompt,
        conn=get_sqlite_conn(str(DATA_DIR / "chunks.db")),
        kuzu_db=get_kuzu_db(str(DATA_DIR / "kuzu_db")),
        chroma_path=str(DATA_DIR / "chroma_db"),
        openai_client=get_openai_client(),
    )
```

`show_time=True` was added in Streamlit 1.47.0 — it displays elapsed seconds in the spinner, which is good UX for a 5-10s LLM call. The `st.status` API (also verified available in 1.47.0) is more appropriate for multi-step processes with sub-steps; the single-call pipeline is simpler with `st.spinner`.

### Pattern 4: Citations Display with st.expander

**What:** Display the answer prose in the chat message body; render citations in a collapsible `st.expander` below the answer within the same `st.chat_message` context.

**When to use:** Secondary information that clutters the primary answer but must be accessible.

```python
def _render_citations(citations: list[dict]) -> None:
    """Render citations list in a collapsible expander."""
    if not citations:
        return
    with st.expander(f"Sources ({len(citations)} cited)", expanded=False):
        for c in citations:
            confidence_badge = "HIGH" if c["confidence"] == "HIGH" else "LOW"
            st.markdown(
                f"**[{c['index']}]** {c['filename']} — p.{c['page_num']} "
                f"&nbsp;`{confidence_badge}`"
            )
```

This pattern keeps the chat flow readable while making citations discoverable. The `expanded=False` default means citations are collapsed; a consultant can click to expand when they want to verify a source.

**Note on clickable citations:** The `citations` dicts contain `filename` and `page_num` but no file URL. Making these hyperlinks would require either (a) knowing the absolute path to the PDF on disk, or (b) serving PDFs via Streamlit's static file serving. Given the single-user local deployment, displaying `filename + page_num` as formatted text is sufficient for success criterion 4 — the consultant can use the filename to locate the document.

### Pattern 5: Streaming vs. Non-Streaming Decision

**Recommendation: Non-streaming (batch response) with `st.spinner`.**

**Rationale:**

`answer_question()` in `pipeline.py` calls `openai_client.chat.completions.create()` without `stream=True`. The function returns a completed `result` dict with `answer`, `citations`, and `elapsed_s`. Adding streaming would require refactoring `pipeline.py` to expose a streaming path, thread the citation build logic around the stream, and handle partial states in session storage.

The UX tradeoff: for a 5-10s response time, streaming provides perceived latency improvement (user sees first tokens after ~1s) but adds implementation complexity and state management risk. The `st.spinner(show_time=True)` approach shows elapsed time and communicates progress without requiring pipeline changes.

**Decision boundary:** If response times regularly exceed 15 seconds, streaming becomes worthwhile. For Qwen2.5-7B q4 at 15-25 tok/s (fully GPU-resident) producing ~400-600 output tokens, wall time is 7-13s — within the `st.spinner` acceptable UX range.

**If streaming is added later:** `st.write_stream(generator)` accepts a generator that yields string chunks. The signature (verified in 1.47.0) is `write_stream(stream: Callable | Generator | Iterable | AsyncGenerator) -> list | str`. To enable streaming, `pipeline.py` would need a `stream=True` variant that yields token chunks.

### Pattern 6: Error Handling UX

**What:** Catch specific exception types, log technical details internally, and display human-readable messages using `st.error()`.

**Error categories and user-facing messages:**

| Error Condition | Technical Cause | User-Facing Message |
|----------------|-----------------|---------------------|
| LM Studio not running | `httpx.ConnectError` / `check_lm_studio()` returns False | "The AI service is not available. Please ensure LM Studio is running and try again." |
| No documents indexed | `chunks.db` missing or empty | "No documents have been indexed yet. Please run the ingestion pipeline before using the chat." |
| Query pipeline error | `Exception` from `answer_question()` | "Something went wrong while processing your question. Please try again." |
| KuzuDB not found | `data/kuzu_db` directory missing | "The knowledge graph has not been built yet. Please complete setup before using the chat." |

```python
# Pattern — catch at the call site, display friendly message
try:
    result = answer_question(...)
except Exception as e:
    st.error("Something went wrong while processing your question. Please try again.")
    # Optionally log to stderr for admin visibility without exposing to user
    import sys
    print(f"[ERROR] query failed: {e}", file=sys.stderr)
    st.stop()  # Halt further rendering for this rerun
```

**Pre-flight check on startup:** Call `check_lm_studio()` at the top of the app and show a persistent `st.warning` banner (not `st.error`) if LM Studio is unreachable. This is non-blocking — the user can still see the interface and history. The error only blocks submission.

### Pattern 7: App Configuration / Data Paths

**What:** Hardcode sensible defaults (relative to project root) with sidebar overrides.

**Approach:** Derive data paths relative to `app.py`'s location using `Path(__file__).parent`. This works correctly when `streamlit run app.py` is run from the project root.

```python
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent
_DEFAULT_DB = str(_PROJECT_ROOT / "data" / "chunks.db")
_DEFAULT_CHROMA = str(_PROJECT_ROOT / "data" / "chroma_db")
_DEFAULT_KUZU = str(_PROJECT_ROOT / "data" / "kuzu_db")
```

No sidebar path overrides are required for the single-user deployment. A sidebar is appropriate for displaying system status (LM Studio reachable: yes/no, documents indexed: N) but should not require configuration input from a non-technical consultant.

### Anti-Patterns to Avoid

- **Creating DB connections outside `@st.cache_resource`:** Streamlit reruns the entire script on every interaction. `sqlite3.connect()` called at module level will reconnect on every rerun. Use `@st.cache_resource`.
- **Storing the full `format_answer()` string in session state:** Mixes prose and citation table as a single unstructured string, losing the ability to re-render citations with richer formatting. Store `answer` prose and `citations` list separately.
- **Using `st.rerun()` manually after appending to session state:** The `st.chat_input` widget triggers a rerun automatically on submission. Manual `st.rerun()` causes double-rerun and flicker.
- **Exposing exception tracebacks to users:** Any `raise` or unhandled `Exception` propagates to the browser as a red error box with Python stack trace. Always wrap `answer_question()` in try/except.
- **Showing `st.error` for slow queries:** A slow query is not an error. Use `st.spinner` during normal operation; only use `st.error` when something genuinely failed.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Chat message rendering | Custom HTML/CSS chat bubbles | `st.chat_message("user")` / `st.chat_message("assistant")` | Native Streamlit chat component handles layout, avatars, accessibility |
| Session persistence | Manual cookie/file-based state | `st.session_state` | Streamlit manages in-memory session state per browser tab automatically |
| Collapsible citations | Custom toggle via `st.button` + conditional render | `st.expander` | Built-in collapsible container with correct accessibility semantics |
| Connection pooling | Custom singleton class | `@st.cache_resource` | Streamlit's caching layer handles lifecycle and thread safety |
| Loading indicator | `time.sleep()` polling loop | `st.spinner` context manager | Blocks the thread correctly while showing UI feedback |
| LM Studio health check | New HTTP check | `check_lm_studio()` from `src.embed.pipeline` | Already implemented and tested; reuse directly |

---

## Common Pitfalls

### Pitfall 1: SQLite "ProgrammingError: SQLite objects created in a thread can only be used in that thread"

**What goes wrong:** `sqlite3.connect()` called without `check_same_thread=False` raises `ProgrammingError` when Streamlit's internal threading model accesses the connection from a different thread than the one that created it.

**Why it happens:** Streamlit's server runs in a threaded environment. The `@st.cache_resource` decorator caches the connection globally, but subsequent access may come from a different thread.

**How to avoid:** Always pass `check_same_thread=False` in the `@st.cache_resource`-wrapped connection factory. Verified fix: `sqlite3.connect(db_path, check_same_thread=False)`.

**Warning signs:** `ProgrammingError: SQLite objects created in a thread` on second or subsequent queries.

### Pitfall 2: Chat History Rendered Twice (Double-Append Bug)

**What goes wrong:** User submits a question; the message appears twice in the chat. This is the most common Streamlit chat bug.

**Why it happens:** The pattern `st.session_state.messages.append(...)` followed immediately by `st.chat_message(...)` renders the message once imperatively. Then on the next rerun, the for-loop at the top re-renders it from session state — but it was already rendered, causing a visual duplicate if the loop runs after the append in the same script execution.

**How to avoid:** Follow the standard pattern strictly: (1) for-loop renders all historical messages from session state at the top, (2) `if prompt :=` block handles the new message, appending to session state AND rendering it within the same block in the same rerun.

**Warning signs:** Messages appear twice after submission.

### Pitfall 3: KuzuDB "Database already open" Error

**What goes wrong:** A second attempt to open `kuzu.Database(path)` on the same path raises an error because KuzuDB locks the database directory on open.

**Why it happens:** If `@st.cache_resource` is not used, `kuzu.Database(path)` is called on every Streamlit rerun, attempting to re-open an already-locked database.

**How to avoid:** Wrap `kuzu.Database(path)` in `@st.cache_resource`. With caching, the database is opened once and the same object is returned on all subsequent reruns.

**Warning signs:** KuzuDB lock errors on the second query or after app reload.

### Pitfall 4: `st.spinner` Not Showing Because Code Is Synchronous

**What goes wrong:** The spinner never appears visually; the UI freezes for 5-10s then displays the answer.

**Why it happens:** `st.spinner` uses a context manager that must wrap a blocking call. If the call is made outside the `with st.spinner():` block, or if Streamlit's event loop is blocked before rendering, the spinner may not display.

**How to avoid:** Ensure `answer_question()` is called inside the `with st.spinner():` block. Do not pre-call the function and store the result — call it inside the context.

**Warning signs:** App appears frozen during query; no spinner visible.

### Pitfall 5: `app.py` Import of `src/` Modules Fails

**What goes wrong:** `from src.query.pipeline import answer_question` raises `ModuleNotFoundError` when `streamlit run app.py` is executed.

**Why it happens:** `streamlit run app.py` does not automatically add the project root to `sys.path` in all configurations. `src/` is a package within the project root, but it may not be discoverable if the CWD is not the project root.

**How to avoid:** Add an explicit `sys.path.insert` guard at the top of `app.py`, mirroring the pattern already used in `src/main.py`:

```python
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
```

**Warning signs:** `ModuleNotFoundError: No module named 'src'` on startup.

---

## Code Examples

### Complete Chat App Skeleton

```python
# app.py — Source: verified patterns from Streamlit 1.47.0 installed API
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import sqlite3
import streamlit as st
import kuzu
from openai import OpenAI

from src.query.pipeline import answer_question
from src.embed.pipeline import check_lm_studio

_DEFAULT_DB    = str(_PROJECT_ROOT / "data" / "chunks.db")
_DEFAULT_CHROMA = str(_PROJECT_ROOT / "data" / "chroma_db")
_DEFAULT_KUZU  = str(_PROJECT_ROOT / "data" / "kuzu_db")

st.set_page_config(page_title="Automotive Consulting Assistant", layout="centered")

# --- Cached resources (created once per session) ---

@st.cache_resource
def get_sqlite_conn(db_path: str = _DEFAULT_DB) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

@st.cache_resource
def get_kuzu_db(graph_path: str = _DEFAULT_KUZU) -> kuzu.Database:
    return kuzu.Database(graph_path)

@st.cache_resource
def get_openai_client() -> OpenAI:
    return OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

# --- Helper: render citations expander ---

def _render_citations(citations: list[dict]) -> None:
    if not citations:
        return
    with st.expander(f"Sources ({len(citations)} cited)", expanded=False):
        for c in citations:
            badge = "HIGH" if c["confidence"] == "HIGH" else "LOW"
            st.markdown(
                f"**[{c['index']}]** {c['filename']} — p.{c['page_num']} "
                f"&nbsp;`{badge}`"
            )

# --- Page header ---
st.title("Automotive Consulting Assistant")

# --- LM Studio status check (non-blocking warning) ---
if not check_lm_studio():
    st.warning(
        "The AI service (LM Studio) is not currently reachable. "
        "Ensure LM Studio is running before submitting a question.",
        icon="⚠️",
    )

# --- Initialize session state ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- Render chat history ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("citations"):
            _render_citations(msg["citations"])

# --- Accept new input ---
if prompt := st.chat_input("Ask a question about your documents..."):
    # Render and store user message
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append(
        {"role": "user", "content": prompt, "citations": [], "elapsed_s": 0.0}
    )

    # Run pipeline with spinner
    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking...", show_time=True):
                result = answer_question(
                    question=prompt,
                    conn=get_sqlite_conn(),
                    kuzu_db=get_kuzu_db(),
                    chroma_path=_DEFAULT_CHROMA,
                    openai_client=get_openai_client(),
                )
            # Display answer (prose only, not format_answer() full string)
            st.markdown(result["answer"])
            _render_citations(result.get("citations", []))
            elapsed = result.get("elapsed_s", 0.0)
            st.caption(f"Answered in {elapsed:.1f}s")
        except Exception as e:
            print(f"[ERROR] query failed: {e}", file=sys.stderr)
            st.error(
                "Something went wrong while processing your question. Please try again."
            )
            result = None

    if result is not None:
        st.session_state.messages.append({
            "role": "assistant",
            "content": result["answer"],
            "citations": result.get("citations", []),
            "elapsed_s": result.get("elapsed_s", 0.0),
        })
```

**Note on `result["answer"]` vs. `format_answer()` output:** `answer_question()` returns `answer` as the output of `format_answer()`, which already includes the plain-text citation table appended to the LLM response. For the UI, we display this full string via `st.markdown()` (which renders the citation table as-is) and additionally show the richer `st.expander` for structured citations. This is slightly redundant. An alternative is to store the raw LLM response before `format_answer()` is applied — but that requires a minor pipeline change. The simplest approach is to display `result["answer"]` as markdown (the citation table renders cleanly) and add the expander as a supplementary view.

### AppTest Skeleton

```python
# tests/test_ui_app.py
# Source: https://docs.streamlit.io/develop/api-reference/app-testing
from unittest.mock import patch, MagicMock
from streamlit.testing.v1 import AppTest

def _make_mock_result():
    return {
        "answer": "Toyota adopted hybrid-first EV strategy. [1]",
        "citations": [{"index": 1, "filename": "toyota_ev.pdf",
                       "page_num": 5, "confidence": "HIGH",
                       "source": "vector", "count": 3}],
        "elapsed_s": 3.2,
    }

def test_initial_render_shows_title():
    """App renders title and empty chat input on first load."""
    at = AppTest.from_file("app.py")
    with patch("src.query.pipeline.answer_question"), \
         patch("src.embed.pipeline.check_lm_studio", return_value=True):
        at.run()
    assert not at.exception
    assert at.title[0].value == "Automotive Consulting Assistant"
    assert len(at.chat_message) == 0  # no messages yet

def test_user_question_appears_in_chat():
    """Submitting a question adds user message to chat history."""
    at = AppTest.from_file("app.py")
    with patch("src.query.pipeline.answer_question", return_value=_make_mock_result()), \
         patch("src.embed.pipeline.check_lm_studio", return_value=True), \
         patch("app.get_sqlite_conn"), patch("app.get_kuzu_db"):
        at.run()
        at.chat_input[0].set_value("What EV strategies did Toyota adopt?").run()
    assert not at.exception
    # User and assistant messages
    assert len(at.chat_message) == 2
    assert at.chat_message[0].markdown[0].value == "What EV strategies did Toyota adopt?"

def test_lm_studio_warning_shown_when_unreachable():
    """Warning banner appears when LM Studio is not running."""
    at = AppTest.from_file("app.py")
    with patch("src.embed.pipeline.check_lm_studio", return_value=False):
        at.run()
    assert not at.exception
    assert len(at.warning) == 1
```

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 (installed) + streamlit.testing.v1.AppTest (built-in, Streamlit 1.47.0) |
| Config file | `pytest.ini` (exists in project root) |
| Quick run command | `pytest tests/test_ui_app.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-01 | App renders chat interface in browser without CLI knowledge | unit (AppTest) | `pytest tests/test_ui_app.py::test_initial_render_shows_title -x` | Wave 0 |
| UI-01 | Chat input widget is present and accepts text | unit (AppTest) | `pytest tests/test_ui_app.py::test_user_question_appears_in_chat -x` | Wave 0 |
| UI-02 | Chat history persists across reruns (session state) | unit (AppTest) | `pytest tests/test_ui_app.py::test_chat_history_persists -x` | Wave 0 |
| UI-01 | Error message shown when LM Studio unreachable | unit (AppTest) | `pytest tests/test_ui_app.py::test_lm_studio_warning_shown_when_unreachable -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_ui_app.py -x -q`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- `tests/test_ui_app.py` — covers UI-01, UI-02 (4+ test functions); `app.py` must exist before tests can run via `AppTest.from_file`
- `app.py` (project root) — the Streamlit entry point; Wave 0 creates stub, Wave 1 implements

---

## Recommended Plan Decomposition

Phase 5 fits cleanly into 3 plans (matching the existing project convention):

### Plan 05-01: Test Infrastructure

**Wave:** 0 (foundation)
**Contents:**
- Create `tests/test_ui_app.py` with 4-6 xfail test stubs using `AppTest`
- Create stub `app.py` at project root (minimal — just `st.title(...)` so `AppTest.from_file("app.py")` succeeds)
- Confirm `streamlit` is in `requirements.txt`
- Run `pytest tests/test_ui_app.py` and verify all stubs show `xfail` (not errors)

**Acceptance:** `pytest tests/test_ui_app.py` passes with all tests marked `xfail`; no import errors

### Plan 05-02: Streamlit Chat App

**Wave:** 1 (core implementation)
**Contents:**
- Implement full `app.py`: `@st.cache_resource` connections, session state initialization, chat history loop, `st.chat_input` handler, `st.spinner` + `answer_question()` call, error handling try/except
- Remove xfail markers from tests as functions are implemented
- Verify: `streamlit run app.py` launches browser UI; manual test of one question returns an answer

**Acceptance:** All AppTest tests pass; `streamlit run app.py` works from project root

### Plan 05-03: Citations Display and Error Handling Polish

**Wave:** 2 (polish)
**Contents:**
- Implement `_render_citations()` with `st.expander` and formatted citation lines
- Add sidebar status panel (LM Studio status, documents indexed count from `chunks.db`)
- Add `st.warning` for missing/empty database conditions
- Add `st.caption` with elapsed time display
- Final test: all 5 success criteria verified manually

**Acceptance:** All tests pass; citations expander renders in chat; user-friendly errors for LM Studio down and no documents indexed

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| streamlit | UI framework | Yes | 1.47.0 | None needed |
| sqlite3 | chunks.db connection | Yes | stdlib | None needed |
| kuzu | kuzu_db connection | Yes | 0.11.3 | None needed |
| openai | LM Studio client | Yes | 1.93.0 | None needed |
| httpx | LM Studio health check | Yes | 0.28.1 | None needed |
| pytest | Test runner | Yes | 9.0.2 | None needed |
| LM Studio (runtime) | Answer generation | Not checked — runtime dependency | — | User-facing error message |

**Missing dependencies with no fallback:** None — all pip packages are installed.

**Runtime note:** LM Studio must be running when the consultant submits a query. The app gracefully handles LM Studio being absent with a `st.warning` banner and a try/except around the pipeline call. No Streamlit package depends on LM Studio being available at import time.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Third-party `streamlit-chat` component | Native `st.chat_message` + `st.chat_input` | Streamlit 1.23 (mid-2023) | No extra dependencies; maintained by Streamlit core team |
| `@st.cache` (deprecated) | `@st.cache_resource` for connections, `@st.cache_data` for data | Streamlit 1.18 (2023) | `@st.cache` was removed; must use new APIs |
| `st.write()` with streaming | `st.write_stream(generator)` | Streamlit 1.31 (2024) | Proper typewriter streaming effect; returns collected string |
| Manual spinner re-implementation | `st.spinner(show_time=True)` | Streamlit 1.47 (2025) | `show_time` shows elapsed seconds natively |

**Deprecated/outdated:**
- `streamlit-chat` (PyPI package): Superseded by native `st.chat_message`; do not install
- `@st.cache`: Removed; `@st.cache_resource` is the replacement for connections

---

## Open Questions

1. **`format_answer()` output in UI — redundant citation display?**
   - What we know: `answer_question()` returns `answer` = the output of `format_answer()`, which appends a plain-text `Citations:` block after the LLM response. The UI also shows an `st.expander` for rich citations.
   - What's unclear: Should the UI strip the plain-text citation table from the answer string before displaying it, to avoid showing citations twice (once inline, once in expander)?
   - Recommendation: In Plan 05-02, display `result["answer"]` as-is via `st.markdown()`. If the double-citation display looks cluttered during manual testing in Plan 05-03, strip the `\n\nCitations:\n...` suffix before rendering. This is a minor cosmetic decision best made during implementation.

2. **`data/` path assumptions when `streamlit run app.py` is run from a different CWD**
   - What we know: Using `Path(__file__).parent / "data"` gives absolute paths regardless of CWD.
   - What's unclear: Whether consultants will always run from project root vs. a parent directory.
   - Recommendation: Use `Path(__file__).parent` as the anchor in `app.py`; document the run command as `streamlit run app.py` executed from the project root directory.

---

## Sources

### Primary (HIGH confidence)
- Streamlit 1.47.0 installed package — API signatures verified directly: `st.chat_message`, `st.chat_input`, `st.write_stream`, `st.spinner`, `st.status`, `st.cache_resource`, `AppTest`
- `src/query/pipeline.py` (this repo) — `answer_question()` signature, return dict schema, default parameters
- `src/query/assembler.py` (this repo) — `format_answer()` output format; citations dict schema

### Secondary (MEDIUM confidence)
- [Build a basic LLM chat app — Streamlit Docs](https://docs.streamlit.io/develop/tutorials/chat-and-llm-apps/build-conversational-apps) — canonical session state + chat pattern; WebSearch confirmed, official source
- [st.cache_resource — Streamlit Docs](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_resource) — database connection caching; WebSearch confirmed, official source
- [App testing — Streamlit Docs](https://docs.streamlit.io/develop/api-reference/app-testing) — AppTest pattern for chat tests; WebSearch confirmed, official source
- [st.write_stream — Streamlit Docs](https://docs.streamlit.io/develop/api-reference/write-magic/st.write_stream) — streaming API; WebSearch confirmed, official source

### Tertiary (LOW confidence)
- Streamlit community forum posts on `check_same_thread=False` for SQLite — pattern independently verified by the installed API signature confirming `check_same_thread` is a valid `sqlite3.connect` parameter

---

## Project Constraints (from CLAUDE.md)

No `CLAUDE.md` found in the project root. No project-level overrides apply beyond the constraints documented in the Phase 5 scope:

- **pip-only:** All dependencies must be pip-installable. Phase 5 adds zero new pip dependencies.
- **Streamlit:** Roadmap-locked. Use `streamlit` for the UI. No alternatives.
- **Single-user:** No authentication required.
- **No model loading in UI:** The app calls `answer_question()` which calls LM Studio via HTTP; the app itself loads no ML models.
- **Non-technical users:** No stack traces, no CLI, no technical jargon in user-visible error messages.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Streamlit 1.47.0 verified installed; all API signatures confirmed programmatically; no new dependencies needed
- Architecture patterns: HIGH — canonical Streamlit patterns verified against official docs; session state and cache_resource behavior confirmed
- Pitfalls: HIGH — SQLite threading issue and double-append bug are well-documented; KuzuDB locking behavior derived from Phase 3 precedent and KuzuDB file-locking model
- Test approach: HIGH — AppTest available in installed Streamlit; `at.chat_message`, `at.chat_input` attributes confirmed

**Research date:** 2026-03-31
**Valid until:** 2026-06-30 (Streamlit releases frequently; re-verify if upgrading beyond 1.47.0)
