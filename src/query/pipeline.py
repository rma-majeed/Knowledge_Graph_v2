"""Query pipeline: hybrid retrieval + context assembly + LM Studio answer generation.

Wires together:
  hybrid_retrieve()    — src/query/retriever.py (vector + graph)
  truncate_to_budget() — src/query/assembler.py (token budget)
  build_prompt()       — src/query/assembler.py (system + user messages)
  _llm_complete()      — dispatch helper (OpenAI client or LiteLLM based on provider)
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

def _llm_complete(client, model: str, messages: list, **kwargs):
    """Dispatch LLM completion to OpenAI client or LiteLLM based on client type.

    For raw OpenAI clients (LM Studio default): calls client.chat.completions.create().
    For _LiteLLMConfig (cloud providers): calls litellm.completion() with provider routing.
    Response shape is identical (OpenAI-compatible) for both paths.
    """
    if hasattr(client, "provider") and isinstance(client.provider, str):  # _LiteLLMConfig from src.config.providers
        import litellm
        return litellm.completion(
            model=client.model,
            api_key=client.api_key,
            api_base=client.api_base,
            messages=messages,
            **kwargs,
        )
    # Raw OpenAI client (LM Studio default)
    return client.chat.completions.create(model=model, messages=messages, **kwargs)


_EXPAND_MAX_TOKENS = 150
_EXPAND_SYSTEM = (
    "Generate 3 alternative search queries for the given question using different terminology "
    "that might appear in consulting documents — e.g., process names, technical terms, business "
    "outcomes, or industry jargon. Return ONLY the 3 queries, one per line, no numbering, "
    "no explanation, no blank lines."
)

_REWRITE_MAX_TOKENS = 80
_REWRITE_SYSTEM = (
    "Rewrite the user's question to be fully self-contained, replacing any pronouns or "
    "references that depend on the conversation history with explicit terms. "
    "If the question is already self-contained, return it unchanged. "
    "Return ONLY the rewritten question — no explanation, no punctuation changes."
)


def _expand_queries(question: str, client, llm_model: str) -> list[str]:
    """Generate alternative phrasings of a query to improve retrieval coverage.

    Example:
        question: "what information is available on warranty?"
        returns: [
            "what information is available on warranty?",
            "warranty claims management and processing",
            "automated warranty approval system",
            "warranty cost reduction and fraud prevention",
        ]

    Falls back to [question] on any error so retrieval always proceeds.
    """
    messages = [
        {"role": "system", "content": _EXPAND_SYSTEM},
        {"role": "user", "content": question},
    ]
    try:
        response = _llm_complete(client, llm_model, messages, temperature=0.0, max_tokens=_EXPAND_MAX_TOKENS)
        lines = response.choices[0].message.content.strip().split("\n")
        expansions = [l.strip() for l in lines if l.strip()][:3]
        return [question] + expansions
    except Exception:
        return [question]


def _rewrite_query(
    question: str,
    conversation_history: list[dict],
    client,
    llm_model: str,
) -> str:
    """Use the LLM to rewrite a follow-up question into a self-contained query.

    Example:
        history: "What did Toyota do in EVs?" / "Toyota invested in solid-state..."
        question: "What about Honda?"
        rewritten: "What did Honda do in electric vehicle strategy?"

    Falls back to the original question on any error.
    """
    if not conversation_history:
        return question

    history_text = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content'][:400]}"
        for m in conversation_history
    )
    messages = [
        {"role": "system", "content": _REWRITE_SYSTEM},
        {"role": "user", "content": f"Conversation so far:\n{history_text}\n\nNew question: {question}"},
    ]
    try:
        response = _llm_complete(client, llm_model, messages, temperature=0.0, max_tokens=_REWRITE_MAX_TOKENS)
        rewritten = response.choices[0].message.content.strip()
        return rewritten if rewritten else question
    except Exception:
        return question


DEFAULT_LLM_MODEL = "Qwen2.5-7B-Instruct"
DEFAULT_EMBED_MODEL = "nomic-embed-text-v1.5"
_COLLECTION_NAME = "chunks"
_LLM_MAX_TOKENS = 600
_LLM_TEMPERATURE = 0.2
DEFAULT_CONTEXT_BUDGET = 3000


def answer_question(
    question: str,
    conn: sqlite3.Connection,
    kuzu_db: kuzu.Database,
    chroma_path: str = "data/chroma_db",
    embed_model: str = DEFAULT_EMBED_MODEL,
    llm_model: str = DEFAULT_LLM_MODEL,
    n_results: int = 10,
    context_budget: int = DEFAULT_CONTEXT_BUDGET,
    openai_client=None,
    chroma_client=None,
    conversation_history: list[dict] | None = None,
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
    from src.query.retriever import vector_search, graph_expand, deduplicate_chunks
    from src.query.assembler import (
        truncate_to_budget,
        build_citations,
        format_answer,
        build_prompt,
    )
    from src.graph.citations import CitationStore

    if openai_client is None:
        from src.config.providers import get_llm_client
        openai_client = get_llm_client()

    if chroma_client is None:
        chroma_client = chromadb.PersistentClient(path=chroma_path)

    citation_store = CitationStore(conn)

    start = time.perf_counter()

    # Step 1: Rewrite question for better retrieval if conversation history present
    retrieval_query = _rewrite_query(question, conversation_history or [], openai_client, llm_model)

    # Step 2: Expand into multiple query variants for broader retrieval coverage
    queries = _expand_queries(retrieval_query, openai_client, llm_model)

    # Step 3: Multi-query vector search — run each variant, merge, deduplicate
    all_vector_chunks: list = []
    for q in queries:
        all_vector_chunks.extend(
            vector_search(q, openai_client, chroma_client, _COLLECTION_NAME, embed_model, n_results)
        )
    vector_chunks = deduplicate_chunks(all_vector_chunks)

    # Step 4: Graph expand on merged vector results
    graph_chunks = graph_expand(vector_chunks, citation_store, kuzu_db, conn)
    chunks = deduplicate_chunks(vector_chunks + graph_chunks)

    # Step 5: Assemble context within token budget
    context_str, included_chunks = truncate_to_budget(chunks, token_budget=context_budget)

    # Step 6: Build prompt with conversation history for multi-turn context
    messages = build_prompt(question, context_str, conversation_history=conversation_history)

    if not included_chunks:
        llm_response = "The available documents do not contain sufficient information to answer this question."
    else:
        response = _llm_complete(openai_client, llm_model, messages,
                                 temperature=_LLM_TEMPERATURE, max_tokens=_LLM_MAX_TOKENS)
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


def stream_answer_question(
    question: str,
    conn: sqlite3.Connection,
    kuzu_db: kuzu.Database,
    chroma_path: str = "data/chroma_db",
    embed_model: str = DEFAULT_EMBED_MODEL,
    llm_model: str = DEFAULT_LLM_MODEL,
    n_results: int = 10,
    context_budget: int = DEFAULT_CONTEXT_BUDGET,
    openai_client=None,
    chroma_client=None,
    conversation_history: list[dict] | None = None,
):
    """Run hybrid retrieval then stream LM Studio answer token-by-token.

    Returns (citations, token_stream) where:
    - citations: list[dict] — same schema as answer_question()
    - token_stream: generator yielding str tokens from the LLM (pass to st.write_stream)

    Retrieval and assembly happen eagerly before streaming starts.
    If no chunks are found, token_stream yields a single fallback message.
    """
    from src.query.retriever import vector_search, graph_expand, deduplicate_chunks
    from src.query.assembler import truncate_to_budget, build_citations, build_prompt
    from src.graph.citations import CitationStore

    if openai_client is None:
        from src.config.providers import get_llm_client
        openai_client = get_llm_client()

    if chroma_client is None:
        chroma_client = chromadb.PersistentClient(path=chroma_path)

    citation_store = CitationStore(conn)

    # Rewrite follow-up questions into self-contained queries for better retrieval
    retrieval_query = _rewrite_query(question, conversation_history or [], openai_client, llm_model)

    # Expand into multiple query variants for broader retrieval coverage
    queries = _expand_queries(retrieval_query, openai_client, llm_model)

    # Multi-query vector search — run each variant, merge, deduplicate
    all_vector_chunks: list = []
    for q in queries:
        all_vector_chunks.extend(
            vector_search(q, openai_client, chroma_client, _COLLECTION_NAME, embed_model, n_results)
        )
    vector_chunks = deduplicate_chunks(all_vector_chunks)

    # Graph expand on merged vector results
    graph_chunks = graph_expand(vector_chunks, citation_store, kuzu_db, conn)
    chunks = deduplicate_chunks(vector_chunks + graph_chunks)

    context_str, included_chunks = truncate_to_budget(chunks, token_budget=context_budget)
    citations = build_citations(included_chunks)

    if not included_chunks:
        def _fallback():
            yield "The available documents do not contain sufficient information to answer this question."
        return citations, _fallback()

    messages = build_prompt(question, context_str, conversation_history=conversation_history)

    stream = _llm_complete(openai_client, llm_model, messages,
                           temperature=_LLM_TEMPERATURE, max_tokens=_LLM_MAX_TOKENS,
                           stream=True)

    def _token_gen():
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    return citations, _token_gen()
