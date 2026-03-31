"""Context assembler and citation builder — plan 04-03.

Public API:
    truncate_to_budget(chunks, token_budget) -> tuple[str, list[dict]]
    build_citations(included_chunks) -> list[dict]
    format_answer(llm_response, citations) -> str
    build_prompt(query, context_str) -> list[dict]

Constants:
    CONTEXT_TOKEN_BUDGET = 3000
    CITATION_HIGH_CONFIDENCE_THRESHOLD = 3
"""
from __future__ import annotations

import collections
from typing import Any

import tiktoken

CONTEXT_TOKEN_BUDGET = 3000
CITATION_HIGH_CONFIDENCE_THRESHOLD = 3

# Initialise encoder once at module level (BPE family, compatible with Qwen2.5)
_ENC = tiktoken.get_encoding("cl100k_base")

_SYSTEM_PROMPT = """You are an expert automotive consulting analyst with access to a knowledge base of consulting documents.

Answer the consultant's question using ONLY the numbered source passages provided. Do not use any knowledge outside the provided sources.

Citation rules:
- Cite each source inline using [N] immediately after the relevant claim
- Every factual statement must have at least one citation
- If multiple sources support a claim, list all relevant citations: [1][3]

Answering guidance:
- If the sources directly answer the question, provide a clear and complete answer with citations
- If the sources do not directly answer the question but contain related or partially relevant information, share what IS available — summarise the related content, cite it, and note that it may not fully address the question
- Only say "The available documents do not contain sufficient information to answer this question." if the sources contain absolutely nothing relevant — no related topics, no partial matches, no adjacent information
- Never fabricate information not present in the sources
- Interpret questions broadly — if asked about a "capability", look for features, tools, approaches, or outcomes related to that topic across all sources

Answer in professional consulting language. Be concise (3-6 sentences for most questions). Do not repeat the question."""


def _get_filename(chunk: dict[str, Any]) -> str:
    """Extract filename from chunk, handling both flat and nested metadata shapes."""
    return (
        chunk.get("metadata", {}).get("filename")
        or chunk.get("filename", "unknown")
    )


def _get_page_num(chunk: dict[str, Any]) -> int:
    """Extract page_num from chunk, handling both flat and nested metadata shapes."""
    page = (
        chunk.get("metadata", {}).get("page_num")
        if chunk.get("metadata") is not None
        else None
    )
    if page is None:
        page = chunk.get("page_num", 0)
    return page


def truncate_to_budget(
    chunks: list[dict[str, Any]],
    token_budget: int = CONTEXT_TOKEN_BUDGET,
) -> tuple[str, list[dict[str, Any]]]:
    """Sort chunks by relevance, truncate to token_budget, return (context_str, included).

    Sort order: vector chunks first (source='vector'), then graph chunks (source='graph').
    Within each group, sort by distance ascending (lowest distance = most relevant first).
    Token counting uses tiktoken cl100k_base.

    Returns:
        context_str: numbered passages joined with "\\n\\n"
        included_chunks: chunk dicts that fit within the budget, each augmented with
                         a 1-based '_ctx_index' key indicating passage number.
    """
    if not chunks:
        return "", []

    sorted_chunks = sorted(
        chunks,
        key=lambda c: (0 if c.get("source") == "vector" else 1, c.get("distance", 1.0)),
    )

    budget_remaining = token_budget
    included: list[dict[str, Any]] = []
    parts: list[str] = []
    counter = 0

    for chunk in sorted_chunks:
        text = chunk.get("text", "")
        filename = _get_filename(chunk)
        page = _get_page_num(chunk)
        passage = f"[{counter + 1}] Source: {filename}, page {page}\n{text}"
        token_count = len(_ENC.encode(passage))
        if token_count > budget_remaining:
            break
        budget_remaining -= token_count
        counter += 1
        parts.append(passage)
        chunk_copy = dict(chunk)
        chunk_copy["_ctx_index"] = counter
        included.append(chunk_copy)

    context_str = "\n\n".join(parts)
    return context_str, included


def build_citations(included_chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build citation list with HIGH/LOW confidence from included_chunks.

    Counts how many times each (filename, page_num) pair appears.
    HIGH confidence = appears >= CITATION_HIGH_CONFIDENCE_THRESHOLD (3) times.
    LOW confidence  = appears 1-2 times.

    Returns list of citation dicts sorted by _ctx_index (ascending).
    Each citation:
        {index, filename, page_num, confidence, source, count}
    """
    if not included_chunks:
        return []

    # Count appearances of each (filename, page_num) pair
    pair_counter: collections.Counter = collections.Counter()
    for chunk in included_chunks:
        filename = _get_filename(chunk)
        page = _get_page_num(chunk)
        pair_counter[(filename, page)] += 1

    citations: list[dict[str, Any]] = []
    for chunk in included_chunks:
        filename = _get_filename(chunk)
        page = _get_page_num(chunk)
        count = pair_counter[(filename, page)]
        confidence = "HIGH" if count >= CITATION_HIGH_CONFIDENCE_THRESHOLD else "LOW"
        citations.append(
            {
                "index": chunk.get("_ctx_index", 0),
                "filename": filename,
                "page_num": page,
                "confidence": confidence,
                "source": chunk.get("source", "vector"),
                "count": count,
            }
        )

    citations.sort(key=lambda c: c["index"])
    return citations


def format_answer(llm_response: str, citations: list[dict[str, Any]]) -> str:
    """Format LLM answer string with appended citation table.

    If citations is non-empty, appends:
        \\n\\nCitations:\\n
        followed by one line per citation: "  [N] filename, p.PAGE  (CONFIDENCE)\\n"

    If citations is empty, appends "\\n\\n(No source citations available.)" instead.
    """
    if not citations:
        return llm_response + "\n\n(No source citations available.)"

    lines = "".join(
        f"  [{c['index']}] {c['filename']}, p.{c['page_num']}  ({c['confidence']})\n"
        for c in citations
    )
    return llm_response + "\n\nCitations:\n" + lines


def build_prompt(
    query: str,
    context_str: str,
    conversation_history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Build messages list for the LLM chat API.

    If conversation_history is provided, prior Q&A turns are inserted between
    the system prompt and the current question so the LLM understands context.

    Args:
        query: The (possibly rewritten) question for the current turn.
        context_str: Retrieved document passages, numbered.
        conversation_history: List of {"role": "user"|"assistant", "content": str}
            dicts representing prior turns. Pass the last N pairs only.

    Returns:
        List of message dicts ready for chat.completions.create(messages=...).
    """
    messages: list[dict[str, str]] = [{"role": "system", "content": _SYSTEM_PROMPT}]

    if conversation_history:
        for turn in conversation_history:
            messages.append({"role": turn["role"], "content": turn["content"]})

    messages.append({"role": "user", "content": f"Question: {query}\n\nSources:\n{context_str}"})
    return messages
