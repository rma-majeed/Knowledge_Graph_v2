"""Query pipeline: hybrid retrieval + context assembly + LM Studio answer generation.

Wires together:
  hybrid_retrieve()    — src/query/retriever.py (vector + graph)
  truncate_to_budget() — src/query/assembler.py (token budget)
  build_prompt()       — src/query/assembler.py (system + user messages)
  LM Studio LLM call   — openai.OpenAI(base_url="http://localhost:1234/v1")
  format_answer()      — src/query/assembler.py (append citation table)
  build_citations()    — src/query/assembler.py (HIGH/LOW confidence)

Usage:
    import sqlite3, kuzu
    from src.query.pipeline import answer_question

    conn = sqlite3.connect("data/chunks.db")
    conn.row_factory = sqlite3.Row
    db = kuzu.Database("data/kuzu_db")
    result = answer_question("What EV strategies did Toyota adopt?", conn, db)
    print(result["answer"])
"""
from __future__ import annotations

import time
import sqlite3

import chromadb
import kuzu

DEFAULT_LLM_MODEL = "Qwen2.5-7B-Instruct"
DEFAULT_EMBED_MODEL = "nomic-embed-text-v1.5"
_COLLECTION_NAME = "chunks"
_LLM_MAX_TOKENS = 600
_LLM_TEMPERATURE = 0.2


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
    """Run hybrid retrieval + LM Studio answer generation for a natural language question.

    Args:
        question: Natural language question from the consultant.
        conn: Open sqlite3.Connection (row_factory=sqlite3.Row set by caller).
        kuzu_db: Open kuzu.Database for graph traversal.
        chroma_path: Path to ChromaDB persistence directory. Used if chroma_client is None.
        embed_model: LM Studio embedding model name (must be loaded when calling).
        llm_model: LM Studio LLM model name (must be loaded for generation step).
        n_results: Number of vector results before graph expansion.
        openai_client: openai.OpenAI client. Created automatically if None.
        chroma_client: chromadb client. Created from chroma_path if None.

    Returns:
        Dict with keys:
        - answer (str): Formatted answer with inline [N] citations and citation table
        - citations (list[dict]): [{index, filename, page_num, confidence, source, count}, ...]
        - elapsed_s (float): Total wall-clock seconds for retrieve + generate
    """
    from openai import OpenAI
    from src.query.retriever import hybrid_retrieve
    from src.query.assembler import (
        truncate_to_budget,
        build_citations,
        format_answer,
        build_prompt,
    )
    from src.graph.citations import CitationStore

    if openai_client is None:
        openai_client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

    if chroma_client is None:
        chroma_client = chromadb.PersistentClient(path=chroma_path)

    citation_store = CitationStore(conn)

    start = time.perf_counter()

    # Step 1: Hybrid retrieval (vector + 1-hop graph expansion)
    chunks = hybrid_retrieve(
        query_text=question,
        openai_client=openai_client,
        chroma_client=chroma_client,
        collection_name=_COLLECTION_NAME,
        citation_store=citation_store,
        kuzu_db=kuzu_db,
        sqlite_conn=conn,
        embed_model=embed_model,
        n_results=n_results,
    )

    # Step 2: Assemble context within token budget
    context_str, included_chunks = truncate_to_budget(chunks)

    # Step 3: Build prompt and call LM Studio LLM
    # Fresh messages list per call — never accumulate history (stateless pipeline)
    messages = build_prompt(question, context_str)

    if not included_chunks:
        llm_response = "The available documents do not contain sufficient information to answer this question."
    else:
        response = openai_client.chat.completions.create(
            model=llm_model,
            messages=messages,
            temperature=_LLM_TEMPERATURE,
            max_tokens=_LLM_MAX_TOKENS,
        )
        llm_response = response.choices[0].message.content.strip()

    # Step 4: Build citations and format final answer
    citations = build_citations(included_chunks)
    final_answer = format_answer(llm_response, citations)

    elapsed_s = time.perf_counter() - start

    return {
        "answer": final_answer,
        "citations": citations,
        "elapsed_s": elapsed_s,
    }
