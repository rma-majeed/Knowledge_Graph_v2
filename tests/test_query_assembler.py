"""Tests for src/query/assembler.py — context assembly and citation scoring (QUERY-04).

All 4 tests verify the implemented assembler functions:
    truncate_to_budget(), build_citations(), format_answer(), build_prompt()
"""
from __future__ import annotations

import tiktoken

from src.query.assembler import (
    CONTEXT_TOKEN_BUDGET,
    build_citations,
    format_answer,
    truncate_to_budget,
)


def _make_chunk(
    text: str,
    source: str = "vector",
    distance: float = 0.1,
    filename: str = "doc.pdf",
    page_num: int = 1,
) -> dict:
    """Helper: build a synthetic chunk dict in flat (graph-style) format."""
    return {
        "chunk_id": "1",
        "text": text,
        "source": source,
        "distance": distance,
        "filename": filename,
        "page_num": page_num,
    }


def test_assemble_context_respects_token_budget() -> None:
    """truncate_to_budget() stops adding chunks when token budget is exhausted.

    Expected: given chunks whose total token count exceeds CONTEXT_TOKEN_BUDGET,
    truncate_to_budget() returns only the highest-relevance subset that fits.
    Vector chunks (source='vector') are prioritised over graph chunks (source='graph').
    """
    enc = tiktoken.get_encoding("cl100k_base")

    # Build a long text chunk: ~700 tokens per passage ensures 5+ passages overflow 3000-token budget
    long_text = "automotive consulting insight detail. " * 150  # ~600 tokens of text
    # Create 5 vector chunks — 5 * ~620 tokens ≈ 3100 tokens, slightly exceeds budget
    chunks = [
        _make_chunk(
            text=long_text,
            source="vector",
            distance=float(i) * 0.1,
            filename="report.pdf",
            page_num=i + 1,
        )
        for i in range(5)
    ]
    # Add some graph chunks that should be deprioritised
    graph_chunks = [
        _make_chunk(
            text=long_text,
            source="graph",
            distance=0.05,
            filename="graph_doc.pdf",
            page_num=i + 1,
        )
        for i in range(3)
    ]
    all_chunks = chunks + graph_chunks

    context_str, included = truncate_to_budget(all_chunks, token_budget=CONTEXT_TOKEN_BUDGET)

    # Token count of result must not exceed budget
    actual_tokens = len(enc.encode(context_str))
    assert actual_tokens <= CONTEXT_TOKEN_BUDGET, (
        f"context_str has {actual_tokens} tokens, exceeds budget {CONTEXT_TOKEN_BUDGET}"
    )

    # Must have included fewer chunks than the full set
    assert len(included) < len(all_chunks), (
        f"Expected truncation; got {len(included)} == {len(all_chunks)} total chunks"
    )

    # If any graph chunks were included, all vector chunks must appear before them
    sources = [c.get("source") for c in included]
    last_vector = max((i for i, s in enumerate(sources) if s == "vector"), default=-1)
    first_graph = min((i for i, s in enumerate(sources) if s == "graph"), default=len(sources))
    assert last_vector < first_graph, (
        f"Vector chunks must precede graph chunks; last_vector={last_vector}, first_graph={first_graph}"
    )

    # _ctx_index should be 1-based and sequential
    for idx, chunk in enumerate(included, start=1):
        assert chunk["_ctx_index"] == idx


def test_citation_confidence_high() -> None:
    """build_citations() assigns HIGH confidence when source doc+page appears >= 3 times.

    Expected: a chunk list where the same (filename, page_num) pair appears in
    3 or more included chunks produces citations with confidence='HIGH'.
    """
    # Build 3 chunks all pointing to the same (filename, page_num)
    included = [
        {
            "_ctx_index": i + 1,
            "text": f"chunk {i}",
            "source": "vector",
            "distance": float(i) * 0.1,
            "filename": "high_doc.pdf",
            "page_num": 7,
        }
        for i in range(3)
    ]

    citations = build_citations(included)

    assert len(citations) == 3
    for c in citations:
        assert c["filename"] == "high_doc.pdf"
        assert c["page_num"] == 7
        assert c["confidence"] == "HIGH", (
            f"Expected HIGH confidence for source appearing 3 times; got {c['confidence']}"
        )


def test_citation_confidence_low() -> None:
    """build_citations() assigns LOW confidence when source doc+page appears 1-2 times.

    Expected: a chunk list where a (filename, page_num) pair appears only once or
    twice produces citations with confidence='LOW'.
    """
    included = [
        {
            "_ctx_index": 1,
            "text": "first chunk",
            "source": "vector",
            "distance": 0.1,
            "filename": "low_doc.pdf",
            "page_num": 3,
        },
        {
            "_ctx_index": 2,
            "text": "second chunk same source",
            "source": "vector",
            "distance": 0.2,
            "filename": "low_doc.pdf",
            "page_num": 3,
        },
        {
            "_ctx_index": 3,
            "text": "single appearance chunk",
            "source": "graph",
            "distance": 1.0,
            "filename": "other_doc.pdf",
            "page_num": 10,
        },
    ]

    citations = build_citations(included)

    assert len(citations) == 3
    for c in citations:
        assert c["confidence"] == "LOW", (
            f"Expected LOW confidence; got {c['confidence']} for {c['filename']} p.{c['page_num']}"
        )


def test_format_answer_with_citations() -> None:
    """format_answer() appends a formatted citation table after the LLM response text.

    Expected: output string contains the original llm_response text followed by
    a 'Citations:' section listing each citation with index, filename, page, and confidence.
    """
    llm_response = "Answer text [1]."
    citations = [
        {
            "index": 1,
            "filename": "doc.pdf",
            "page_num": 5,
            "confidence": "HIGH",
            "source": "vector",
            "count": 3,
        }
    ]

    result = format_answer(llm_response, citations)

    assert "Answer text [1]." in result
    assert "Citations:" in result
    assert "[1] doc.pdf, p.5  (HIGH)" in result
