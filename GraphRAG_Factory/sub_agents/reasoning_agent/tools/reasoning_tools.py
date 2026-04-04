"""Reasoning tool — structured analytical synthesis over a RAG pipeline answer.

apply_reasoning() receives the original user question and the full text output
from pipeline_rag_agent (answer + Citations block). It calls the configured
reasoning LLM to produce a structured analysis with four sections:
  - SUMMARY
  - KEY INSIGHTS
  - BUSINESS IMPLICATIONS
  - GAPS / LIMITATIONS

The original Citations block is split out before the LLM call and reattached
verbatim to the output — the LLM never sees or touches the citation formatting.

Model is controlled by REASONING_MODEL env var (defaults to LLM_MODEL so no
extra model download is needed unless the user explicitly overrides it).

DB connections are NOT needed here — this tool only calls the LLM.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# 4 levels up: tools/ → reasoning_agent/ → sub_agents/ → GraphRAG_Factory/ → project root
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env", override=True)

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# REASONING_MODEL defaults to LLM_MODEL — swap to a dedicated reasoning model
# by adding REASONING_MODEL=<model-name> to .env without touching any code.
_REASONING_MODEL = os.getenv("REASONING_MODEL") or os.getenv("LLM_MODEL", "google/gemma-3n-e4b")

# Rough word budget before the LLM call (~600 words ≈ 800 tokens)
_MAX_ANSWER_WORDS = 600

_openai_client = None


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        from src.config.providers import get_llm_client
        _openai_client = get_llm_client()
    return _openai_client


def _llm_complete(client, model: str, messages: list, **kwargs):
    """Dispatch to raw OpenAI client or LiteLLM based on client type.

    Mirrors the same dispatch used in src/query/pipeline.py so both
    LM Studio (raw OpenAI) and cloud providers (LiteLLM) are supported.
    """
    if hasattr(client, "provider") and isinstance(client.provider, str):
        import litellm
        return litellm.completion(
            model=client.model,
            api_key=client.api_key,
            api_base=client.api_base,
            messages=messages,
            **kwargs,
        )
    return client.chat.completions.create(model=model, messages=messages, **kwargs)


def _truncate_to_words(text: str, max_words: int) -> str:
    """Truncate text to at most max_words words to stay within LLM context."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + " [...]"


def _split_answer_citations(raw_rag_result: str) -> tuple[str, str]:
    """Split a full RAG result into (answer_text, citations_block).

    Looks for 'Citations:' as the split point. If not found, the whole
    text is treated as the answer with no citations block.
    """
    if "Citations:" in raw_rag_result:
        idx = raw_rag_result.index("Citations:")
        return raw_rag_result[:idx].strip(), raw_rag_result[idx:].strip()
    return raw_rag_result.strip(), "(No source citations available.)"


def apply_reasoning(question: str, raw_rag_result: str) -> dict:
    """Apply structured analytical reasoning to a RAG pipeline result.

    Takes the original question and the full pipeline_rag_agent output text
    (which includes an answer and a Citations block). Produces a structured
    four-section analysis via the reasoning LLM. The Citations block from
    the original RAG result is preserved verbatim and never rewritten by the LLM.

    The reasoning LLM receives a fill-in-the-blanks prompt to maximise
    reliability with small models (gemma, Qwen) that struggle with free-form
    template generation.

    Args:
        question:       The original user question passed to the RAG pipeline.
        raw_rag_result: Full text output from pipeline_rag_agent, including
                        the Citations block at the end.

    Returns:
        Dict with:
          - status:          "success" or "error"
          - reasoned_answer: Structured analytical response (four sections, no Citations).
          - citations_block: Original Citations block preserved verbatim.
          - error:           Error message string (only present when status is "error").
    """
    try:
        answer_text, citations_block = _split_answer_citations(raw_rag_result)
        truncated_answer = _truncate_to_words(answer_text, _MAX_ANSWER_WORDS)

        # Fill-in-the-blanks prompt — prescriptive format improves small-LLM reliability
        prompt = (
            "You are an automotive consulting analyst producing a structured briefing.\n"
            "Based ONLY on the knowledge base answer provided below, complete the four "
            "sections. Do not add information not present in the answer.\n"
            "Preserve any inline citation markers such as [1] or [2] exactly as they appear.\n\n"
            f"QUESTION: {question}\n\n"
            f"KNOWLEDGE BASE ANSWER:\n{truncated_answer}\n\n"
            "---\n"
            "Complete each section below. Replace the placeholder text in brackets.\n\n"
            "SUMMARY:\n"
            "[Write 1-2 sentences that directly answer the question using the answer above.]\n\n"
            "KEY INSIGHTS:\n"
            "- [First key finding from the answer]\n"
            "- [Second key finding from the answer]\n"
            "- [Third key finding from the answer, or omit if fewer than 3 findings exist]\n\n"
            "BUSINESS IMPLICATIONS:\n"
            "- [First practical implication for automotive industry stakeholders]\n"
            "- [Second practical implication]\n\n"
            "GAPS / LIMITATIONS:\n"
            "- [One aspect the knowledge base answer does not fully address]\n"
        )

        client = _get_openai_client()
        response = _llm_complete(
            client,
            model=_REASONING_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.3,
        )

        reasoned_answer = response.choices[0].message.content.strip()

        return {
            "status": "success",
            "reasoned_answer": reasoned_answer,
            "citations_block": citations_block,
        }

    except Exception as exc:
        # On any failure, fall back to the original RAG answer unchanged
        _, citations_block = _split_answer_citations(raw_rag_result or "")
        return {
            "status": "error",
            "reasoned_answer": raw_rag_result or "",
            "citations_block": citations_block,
            "error": str(exc),
        }
