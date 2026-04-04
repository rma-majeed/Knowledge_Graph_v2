"""Answer quality gate — pure heuristic, no LLM call.

check_answer_quality() inspects three signals to decide whether
pipeline_rag_agent should retry full_rag_query with a broader question.

Signals checked (in order):
  1. Low-confidence phrases in the answer text
  2. No citations in citations_block
  3. Answer word count below minimum threshold

Returns a PASS or RETRY verdict instantly without any network or model call.
"""
from __future__ import annotations

_LOW_CONFIDENCE_PHRASES = (
    "i don't know",
    "i do not know",
    "no information",
    "cannot find",
    "could not find",
    "unable to find",
    "not available",
    "no relevant",
    "no data",
    "insufficient information",
    "i'm not sure",
    "i am not sure",
    "no specific information",
    "not mentioned",
    "not found",
    "no results",
)

_MIN_WORD_COUNT = 50


def check_answer_quality(answer: str, citations_block: str) -> dict:
    """Heuristic quality gate: returns PASS or RETRY with a reason.

    Called by pipeline_rag_agent immediately after full_rag_query to decide
    whether the answer is sufficient or a retry with a broader question is needed.
    Maximum one retry is allowed — after that the answer is accepted regardless.

    Args:
        answer:          The 'answer' field from the full_rag_query result.
        citations_block: The 'citations_block' field from the full_rag_query result.

    Returns:
        Dict with:
          - verdict: "PASS" or "RETRY"
          - reason:  Human-readable explanation of the verdict.
    """
    answer_lower = (answer or "").lower().strip()

    # Signal 1: low-confidence phrases indicate the model had no relevant context
    for phrase in _LOW_CONFIDENCE_PHRASES:
        if phrase in answer_lower:
            return {
                "verdict": "RETRY",
                "reason": (
                    f"Low-confidence phrase detected: '{phrase}'. "
                    "Retrying with broader query prefix."
                ),
            }

    # Signal 2: no citations means retrieval returned nothing useful
    cb = (citations_block or "").strip()
    no_citations = (
        not cb
        or cb == "(No source citations available.)"
        or "(Citations unavailable.)" in cb
        or "Citations:" not in cb
    )
    if no_citations:
        return {
            "verdict": "RETRY",
            "reason": (
                "No source citations retrieved — answer is unsupported by documents. "
                "Retrying with broader query prefix."
            ),
        }

    # Signal 3: answer too short (under-specified or truncated)
    word_count = len(answer.split())
    if word_count < _MIN_WORD_COUNT:
        return {
            "verdict": "RETRY",
            "reason": (
                f"Answer too short ({word_count} words, minimum {_MIN_WORD_COUNT}). "
                "Retrying with broader query prefix."
            ),
        }

    return {"verdict": "PASS", "reason": "Answer meets quality threshold."}
