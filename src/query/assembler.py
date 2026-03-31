"""Context assembler and citation builder stub — implemented in plan 04-03.

Public API (all raise NotImplementedError until plan 04-03):
    truncate_to_budget(chunks, token_budget) -> tuple[str, list[dict]]
    build_citations(included_chunks) -> list[dict]
    format_answer(llm_response, citations) -> str
    build_prompt(query, context_str) -> list[dict]

Constants (available now for tests):
    CONTEXT_TOKEN_BUDGET = 3000
    CITATION_HIGH_CONFIDENCE_THRESHOLD = 3
"""
from __future__ import annotations

CONTEXT_TOKEN_BUDGET = 3000
CITATION_HIGH_CONFIDENCE_THRESHOLD = 3


def truncate_to_budget(chunks, token_budget=CONTEXT_TOKEN_BUDGET):
    """Sort chunks by relevance, truncate to token_budget, return (context_str, included)."""
    raise NotImplementedError


def build_citations(included_chunks):
    """Build citation list with HIGH/LOW confidence from included_chunks."""
    raise NotImplementedError


def format_answer(llm_response, citations):
    """Format LLM answer string with appended citation table."""
    raise NotImplementedError


def build_prompt(query, context_str):
    """Build messages list [system, user] for LM Studio chat API."""
    raise NotImplementedError
