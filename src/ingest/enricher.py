"""Contextual chunk enrichment for RAG-03.

Generates a 2-3 sentence context summary for each chunk using the configured
LLM (via LM Studio or any supported provider). The summary is prepended to
the chunk text before embedding, helping retrieval for context-sparse chunks.

Usage:
    from src.ingest.enricher import enrich_chunk_context
    enriched = enrich_chunk_context(chunk_text, llm_client, model_name)
    # embed enriched text instead of original
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_ENRICH_SYSTEM = (
    "You are a document analyst assistant. Given a passage from an automotive consulting document, "
    "write a 2-3 sentence context summary that explains what topic or problem this passage addresses, "
    "what type of document it likely comes from, and any key entities (OEMs, suppliers, technologies) "
    "mentioned. Return ONLY the summary sentences — no labels, no bullet points."
)

_ENRICH_MAX_TOKENS = 120


def enrich_chunk_context(
    chunk_text: str,
    llm_client,
    llm_model: str,
) -> str:
    """Generate a 2-3 sentence context summary to prepend before embedding.

    The returned string is: "{summary} {original_text}" so that both the
    context summary and original text are embedded together.

    Falls back to the original chunk_text on any LLM error (network timeout,
    model not loaded, invalid response) — ingest never fails due to enrichment.

    Args:
        chunk_text: Original chunk text to enrich.
        llm_client: An openai.OpenAI client or _LiteLLMConfig object.
        llm_model: The LLM model name to use.

    Returns:
        Enriched string: "Context: {summary} {chunk_text}", or chunk_text on error.
    """
    if not chunk_text or not chunk_text.strip():
        return chunk_text

    messages = [
        {"role": "system", "content": _ENRICH_SYSTEM},
        {"role": "user", "content": chunk_text[:2000]},  # cap input to avoid timeout
    ]

    try:
        # Dispatch: LiteLLM config or raw OpenAI client
        if hasattr(llm_client, "provider") and isinstance(llm_client.provider, str):
            import litellm
            response = litellm.completion(
                model=llm_client.model,
                api_key=llm_client.api_key,
                api_base=llm_client.api_base,
                messages=messages,
                temperature=0.0,
                max_tokens=_ENRICH_MAX_TOKENS,
            )
        else:
            response = llm_client.chat.completions.create(
                model=llm_model,
                messages=messages,
                temperature=0.0,
                max_tokens=_ENRICH_MAX_TOKENS,
            )

        summary = response.choices[0].message.content.strip()
        if not summary:
            return chunk_text

        return f"Context: {summary} {chunk_text}"

    except Exception as exc:
        logger.debug("enrich_chunk_context fallback (model=%s): %s", llm_model, exc)
        return chunk_text
