"""Pipeline RAG tool — wraps the full 10-step answer_question() pipeline.

DB connections are shared process-wide singletons imported from db_singletons.
KuzuDB only permits one Database instance per process — sharing prevents lock
conflicts when both sub-agents are loaded together under adk web.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Resolve project root (4 levels up from this file) and load .env
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env", override=True)

# Ensure src/ and GraphRAG_Factory/ are importable when running via adk web
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Shared process-wide DB singletons (avoids KuzuDB file lock between agents)
from GraphRAG_Factory.db_singletons import _get_sqlite_conn, _get_kuzu_db

_openai_client = None


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
        citations = result.get("citations", [])
        return {
            "status": "success",
            "answer": result.get("answer", ""),
            "citations": citations,
            "citations_block": _build_citations_block(citations),
            "elapsed_s": result.get("elapsed_s", 0.0),
        }
    except Exception as exc:
        return {
            "status": "error",
            "answer": "",
            "citations": [],
            "citations_block": "(Citations unavailable.)",
            "elapsed_s": 0.0,
            "error": str(exc),
        }


def _build_citations_block(citations: list) -> str:
    """Format a citations list into a Citations block string."""
    if not citations:
        return "(No source citations available.)"
    lines = []
    for c in citations:
        idx = c.get("index", len(lines) + 1)
        filename = c.get("filename", "unknown")
        page_num = c.get("page_num", "?")
        lines.append(f"  [{idx}] {filename}, p.{page_num}")
    return "Citations:\n" + "\n".join(lines)


def append_citations(citations_block: str) -> dict:
    """Return the citations block to append verbatim at the end of your answer.

    Call this as the final step after full_rag_query. Pass the citations_block
    value from the full_rag_query result. Append the returned text verbatim.

    Args:
        citations_block: The citations_block string from full_rag_query result.

    Returns:
        Dict with 'citations_block' to append verbatim to your answer.
    """
    return {"citations_block": citations_block or "(No source citations available.)"}
