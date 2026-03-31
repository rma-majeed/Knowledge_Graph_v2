"""Tests for src/query/assembler.py — context assembly and citation scoring (QUERY-04).

All tests are xfail stubs. They become passing once plan 04-03 implements
truncate_to_budget(), build_citations(), format_answer(), and build_prompt().
"""
from __future__ import annotations

import pytest


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_assemble_context_respects_token_budget() -> None:
    """truncate_to_budget() stops adding chunks when token budget is exhausted.

    Expected: given chunks whose total token count exceeds CONTEXT_TOKEN_BUDGET,
    truncate_to_budget() returns only the highest-relevance subset that fits.
    Vector chunks (source='vector') are prioritised over graph chunks (source='graph').
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_citation_confidence_high() -> None:
    """build_citations() assigns HIGH confidence when source doc+page appears >= 3 times.

    Expected: a chunk list where the same (filename, page_num) pair appears in
    3 or more included chunks produces citations with confidence='HIGH'.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_citation_confidence_low() -> None:
    """build_citations() assigns LOW confidence when source doc+page appears 1-2 times.

    Expected: a chunk list where a (filename, page_num) pair appears only once or
    twice produces citations with confidence='LOW'.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=False, reason="not implemented yet")
def test_format_answer_with_citations() -> None:
    """format_answer() appends a formatted citation table after the LLM response text.

    Expected: output string contains the original llm_response text followed by
    a 'Citations:' section listing each citation with index, filename, page, and confidence.
    """
    raise NotImplementedError
