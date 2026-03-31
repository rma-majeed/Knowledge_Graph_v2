---
phase: 05-chat-ui-session-management
plan: 02
type: execute
wave: 2
depends_on:
  - 05-01-test-infrastructure-PLAN.md
files_modified:
  - app.py
autonomous: true
requirements:
  - UI-01
  - UI-02

must_haves:
  truths:
    - "streamlit run app.py opens a browser chat interface at localhost:8501 without crashing"
    - "Consultant types a question and sees the pipeline answer rendered in the chat"
    - "All previous Q&A pairs remain visible after each new submission (session state persists)"
    - "When answer_question() raises an exception, user sees an st.error message with no Python traceback"
    - "test_app_renders_empty_chat and test_chat_input_triggers_response pass (xfail -> pass)"
  artifacts:
    - path: "app.py"
      provides: "Full Streamlit chat interface with session state, cached connections, spinner, error handling"
      min_lines: 80
  key_links:
    - from: "app.py"
      to: "src/query/pipeline.py"
      via: "from src.query.pipeline import answer_question"
      pattern: "from src.query.pipeline import answer_question"
    - from: "app.py"
      to: "src/embed/pipeline.py"
      via: "from src.embed.pipeline import check_lm_studio"
      pattern: "from src.embed.pipeline import check_lm_studio"
    - from: "app.py"
      to: "st.session_state.messages"
      via: "@st.cache_resource + session_state init guard"
      pattern: "session_state.messages"
---

<objective>
Implement the full Streamlit chat application in app.py (replacing the Wave 1 stub).

Purpose: Deliver the core UI-01 and UI-02 requirements — a browser-accessible chat interface where the consultant types questions and sees answers, with history preserved within a session. Uses the already-built answer_question() pipeline without modifying it.

Output: app.py at project root with chat UI, session state management, cached DB connections, spinner, LM Studio health check, and user-friendly error handling.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/05-chat-ui-session-management/05-RESEARCH.md
@.planning/phases/05-chat-ui-session-management/05-01-SUMMARY.md

<interfaces>
<!-- answer_question() — src/query/pipeline.py (Phase 4, fully implemented) -->
```python
def answer_question(
    question: str,
    conn: sqlite3.Connection,       # open sqlite3 connection, row_factory=sqlite3.Row
    kuzu_db: kuzu.Database,         # open kuzu.Database
    chroma_path: str = "data/chroma_db",
    embed_model: str = "nomic-embed-text-v1.5",
    llm_model: str = "Qwen2.5-7B-Instruct",
    n_results: int = 10,
    openai_client=None,             # created internally if None
    chroma_client=None,             # created internally if None
) -> dict:
    # Returns: {"answer": str, "citations": list[dict], "elapsed_s": float}
    # citations items: {"index": int, "filename": str, "page_num": int,
    #                   "confidence": "HIGH"|"LOW", "source": str, "count": int}
```

<!-- check_lm_studio() — src/embed/pipeline.py (Phase 2, fully implemented) -->
```python
def check_lm_studio() -> bool:
    # Returns True if LM Studio is reachable at localhost:1234, False otherwise
```

<!-- Session state message schema for this project -->
{
    "role": "user" | "assistant",
    "content": str,          # answer prose only (not full format_answer() output)
    "citations": list[dict], # raw citations from pipeline; empty list for user msgs
    "elapsed_s": float       # 0.0 for user msgs
}

<!-- @st.cache_resource pattern — Streamlit 1.47.0 -->
# Creates resource once per app session; reused across all reruns
@st.cache_resource
def get_sqlite_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)  # REQUIRED
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

# KuzuDB: cache_resource prevents "Database already open" lock error
@st.cache_resource
def get_kuzu_db(graph_path: str) -> kuzu.Database:
    return kuzu.Database(graph_path)

# OpenAI client: cache_resource avoids recreating on every rerun
@st.cache_resource
def get_openai_client() -> OpenAI:
    return OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

<!-- st.spinner — Streamlit 1.47.0, show_time=True is NEW in 1.47 -->
with st.spinner("Thinking...", show_time=True):
    result = answer_question(...)
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Implement full app.py Streamlit chat interface</name>
  <files>app.py</files>

  <read_first>
    - app.py (current stub — understand what to replace)
    - src/query/pipeline.py (confirm answer_question() signature and return dict keys)
    - src/embed/pipeline.py (confirm check_lm_studio() signature)
  </read_first>

  <action>
Replace the app.py stub (which raises NotImplementedError) with the full Streamlit chat implementation. Write the complete file:

```python
"""Automotive Consulting GraphRAG — Streamlit Chat Interface.

Run with: streamlit run app.py
Requires LM Studio running at localhost:1234 with:
  - Embedding model: nomic-embed-text-v1.5
  - LLM model: Qwen2.5-7B-Instruct (or equivalent)
"""
from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import sqlite3

import kuzu
import streamlit as st
from openai import OpenAI

from src.embed.pipeline import check_lm_studio
from src.query.pipeline import answer_question

# --- Path defaults (relative to project root) ---

_DEFAULT_DB = str(_PROJECT_ROOT / "data" / "chunks.db")
_DEFAULT_CHROMA = str(_PROJECT_ROOT / "data" / "chroma_db")
_DEFAULT_KUZU = str(_PROJECT_ROOT / "data" / "kuzu_db")
_DEFAULT_MODEL = "Qwen2.5-7B-Instruct"
_DEFAULT_TOP_K = 10

# --- Page config ---

st.set_page_config(
    page_title="Automotive Consulting Assistant",
    page_icon="car",
    layout="wide",
)

# --- Cached resources (created once per session, reused across reruns) ---


@st.cache_resource
def get_sqlite_conn(db_path: str = _DEFAULT_DB) -> sqlite3.Connection:
    """Open SQLite connection once; check_same_thread=False required for Streamlit threading."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@st.cache_resource
def get_kuzu_db(graph_path: str = _DEFAULT_KUZU) -> kuzu.Database:
    """Open KuzuDB once; caching prevents 'Database already open' lock error on reruns."""
    return kuzu.Database(graph_path)


@st.cache_resource
def get_openai_client() -> OpenAI:
    """Create OpenAI-compatible client for LM Studio once per session."""
    return OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")


# --- Helper: user-friendly error messages ---


def _friendly_error(exc: Exception) -> str:
    """Map pipeline exceptions to plain-English messages safe to show consultants."""
    msg = str(exc).lower()
    if "connect" in msg or "connection" in msg or "refused" in msg:
        return (
            "The AI service is not available. Please ensure LM Studio is running "
            "at localhost:1234 with the correct model loaded, then try again."
        )
    if "no such table" in msg or "no such file" in msg or "unable to open" in msg:
        return (
            "No documents have been indexed yet. Please run the ingestion pipeline "
            "before using the chat interface."
        )
    if "kuzu" in msg or "graph" in msg or "database" in msg:
        return (
            "The knowledge graph has not been built yet. Please complete the "
            "graph construction step before using the chat."
        )
    return (
        "Something went wrong while processing your question. "
        "Please try again or contact support."
    )


# --- Sidebar ---

with st.sidebar:
    st.header("Automotive Consulting Assistant")
    st.markdown(
        "Ask questions about past consulting engagements. "
        "The system searches 15+ years of project knowledge."
    )
    st.divider()

    st.subheader("System Status")
    lm_ok = check_lm_studio()
    if lm_ok:
        st.success("LM Studio: connected")
    else:
        st.warning(
            "LM Studio is not reachable at localhost:1234. "
            "Start LM Studio and load a model before submitting questions."
        )

    st.divider()
    st.subheader("Advanced Settings")
    llm_model = st.text_input("LLM Model", value=_DEFAULT_MODEL)
    top_k = st.slider("Top-K retrieval results", min_value=3, max_value=20, value=_DEFAULT_TOP_K)

# --- Page header ---

st.title("Automotive Consulting Assistant")
st.caption("Ask a question about our past automotive consulting work.")

# --- Initialize chat history ---

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- Render existing chat history ---

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- Handle new input ---

if prompt := st.chat_input("Ask about our automotive consulting work..."):
    # Append user message ONCE and render immediately
    st.session_state.messages.append(
        {"role": "user", "content": prompt, "citations": [], "elapsed_s": 0.0}
    )
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate and display assistant response
    with st.chat_message("assistant"):
        with st.spinner("Thinking...", show_time=True):
            try:
                result = answer_question(
                    question=prompt,
                    conn=get_sqlite_conn(_DEFAULT_DB),
                    kuzu_db=get_kuzu_db(_DEFAULT_KUZU),
                    chroma_path=_DEFAULT_CHROMA,
                    llm_model=llm_model,
                    n_results=top_k,
                    openai_client=get_openai_client(),
                )
                # Store answer prose only (not the full format_answer() text with embedded citations)
                # Citations list stored separately so plan 05-03 can render them richly
                answer_text = result["answer"]
                citations = result.get("citations", [])
                elapsed = result.get("elapsed_s", 0.0)

                st.markdown(answer_text)
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": answer_text,
                        "citations": citations,
                        "elapsed_s": elapsed,
                    }
                )

            except Exception as exc:
                import sys as _sys
                print(f"[ERROR] query failed: {exc}", file=_sys.stderr)
                error_msg = _friendly_error(exc)
                st.error(error_msg)
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": f"Error: {error_msg}",
                        "citations": [],
                        "elapsed_s": 0.0,
                    }
                )
```

Key implementation decisions to verify are followed exactly:
- `check_same_thread=False` in get_sqlite_conn — prevents SQLite threading error in Streamlit
- `@st.cache_resource` on all three connection factories — prevents KuzuDB lock on rerun
- Messages appended ONCE inside `if prompt:=` block — prevents double-append bug
- `st.spinner("Thinking...", show_time=True)` — show_time=True requires Streamlit 1.47.0 (installed)
- `_friendly_error()` maps all exceptions to plain English — no tracebacks exposed
- `answer_text` extracted from `result["answer"]` — citations stored separately in session state
  </action>

  <verify>
    <automated>cd "C:/Users/2171176/Documents/Python/Knowledge_Graph_v2" && python -c "import ast; ast.parse(open('app.py').read()); print('app.py syntax OK')" && python -m pytest tests/test_chat_app.py -x -q -k "not lm_studio" 2>&1 | tail -8</automated>
  </verify>

  <done>
- app.py parses without syntax error
- test_app_renders_empty_chat passes (xfail -> pass or passes outright)
- test_chat_input_triggers_response passes (xfail -> pass or passes outright)
- test_chat_history_persists passes (xfail -> pass or passes outright)
- test_lm_studio_error_shows_friendly_message passes (xfail -> pass or passes outright)
- Full prior test suite still green: pytest tests/ -x -q -k "not lm_studio" exits 0
  </done>
</task>

</tasks>

<verification>
```bash
cd "C:/Users/2171176/Documents/Python/Knowledge_Graph_v2"

# Syntax check
python -c "import ast; ast.parse(open('app.py').read()); print('app.py syntax OK')"

# Unit tests pass (xfail stubs become passing)
python -m pytest tests/test_chat_app.py -x -q -k "not lm_studio"

# Full suite unaffected
python -m pytest tests/ -x -q -k "not lm_studio" --tb=short 2>&1 | tail -5

# Manual smoke test (requires LM Studio running):
# streamlit run app.py
```
</verification>

<success_criteria>
- app.py is fully implemented with chat UI, session state, cached connections, spinner, and error handling
- All 4 xfail stubs in tests/test_chat_app.py transition from xfail to passing
- No double-append: submitting a question shows each message exactly once
- check_same_thread=False present in get_sqlite_conn
- @st.cache_resource decorating all three resource factories
- st.spinner("Thinking...", show_time=True) wraps the answer_question() call
- Full prior test suite (phases 1-4) still green
</success_criteria>

<output>
After completion, create `.planning/phases/05-chat-ui-session-management/05-02-SUMMARY.md`
</output>
