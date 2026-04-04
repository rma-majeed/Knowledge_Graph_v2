"""Reasoning sub-agent — structured analytical synthesis over a RAG result.

Receives a message from the Master agent containing:
  - The original user question
  - The full pipeline_rag_agent output (answer + Citations block)

Calls apply_reasoning() to produce a structured four-section analysis:
  SUMMARY / KEY INSIGHTS / BUSINESS IMPLICATIONS / GAPS & LIMITATIONS

The Citations block from the original RAG result is preserved verbatim.

Model is controlled by REASONING_MODEL env var (defaults to LLM_MODEL).
Swap to a dedicated reasoning model with a one-line .env change.

Exposes root_agent for ADK discovery.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from .tools.reasoning_tools import apply_reasoning

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env", override=True)

# Reasoning agent uses REASONING_MODEL if set, otherwise falls back to LLM_MODEL
_LLM_MODEL = os.getenv("REASONING_MODEL") or os.getenv("LLM_MODEL", "google/gemma-3n-e4b")


def create_reasoning_agent() -> LlmAgent:
    agent = LlmAgent(
        name="reasoning_agent",
        model=LiteLlm(model=f"openai/{_LLM_MODEL}"),
        description=(
            "Applies structured analytical reasoning to a RAG pipeline result. "
            "Produces a four-section analysis: Summary, Key Insights, Business "
            "Implications, and Gaps/Limitations. Used for analytical queries that "
            "require deeper synthesis beyond a direct retrieval answer."
        ),
        instruction=(
            "You are the Reasoning Agent for an Automotive Consulting knowledge base.\n\n"
            "The Master agent sends you a message in this format:\n"
            "  Question: <the user's original question>\n"
            "  RAG Result:\n"
            "  <full answer text including a Citations: block at the end>\n\n"

            "Follow these steps IN ORDER:\n\n"

            "STEP 1 — Call apply_reasoning with:\n"
            "  question      = the text after 'Question:' (up to 'RAG Result:')\n"
            "  raw_rag_result = the full text after 'RAG Result:' "
            "(include the Citations: section)\n\n"

            "STEP 2 — Check the result:\n"
            "  If status is 'error', output the 'reasoned_answer' field as-is "
            "(it contains the original RAG answer as a fallback) and proceed to STEP 3.\n\n"

            "STEP 3 — Output your response:\n"
            "  Write the 'reasoned_answer' field from the tool result exactly as returned.\n"
            "  Then append the 'citations_block' field verbatim on a new line.\n\n"

            "CITATIONS ARE MANDATORY. Every response must end with the citations_block.\n"
            "Do not rewrite, reformat, or summarise the citations_block."
        ),
        output_key="reasoning_result",
        tools=[apply_reasoning],
    )
    return agent


root_agent = create_reasoning_agent()
