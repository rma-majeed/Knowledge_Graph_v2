"""Query pipeline stub — implemented in plan 04-04.

Public API (raises NotImplementedError until plan 04-04):
    answer_question(question, conn, kuzu_db, chroma_path, embed_model, llm_model, n_results) -> dict

Returns dict with keys: answer (str), citations (list[dict]), elapsed_s (float).
"""
from __future__ import annotations

DEFAULT_LLM_MODEL = "Qwen2.5-7B-Instruct"
DEFAULT_EMBED_MODEL = "nomic-embed-text-v1.5"


def answer_question(question, conn, kuzu_db, chroma_path="data/chroma_db",
                    embed_model=DEFAULT_EMBED_MODEL, llm_model=DEFAULT_LLM_MODEL,
                    n_results=10):
    """Run hybrid retrieval + context assembly + LLM generation for question.

    Returns:
        dict with keys: answer (str), citations (list[dict]), elapsed_s (float)
    """
    raise NotImplementedError
