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
