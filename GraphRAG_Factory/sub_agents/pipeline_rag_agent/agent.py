"""Pipeline RAG sub-agent — full 10-step GraphRAG pipeline as an ADK LlmAgent.

This agent receives a question from the Master agent and:
  1. Calls full_rag_query to run the 10-step retrieval pipeline.
  2. Calls check_answer_quality to gate quality heuristically.
  3. Retries full_rag_query once (max) if verdict is RETRY.
  4. Calls append_citations to finalise the Citations block.

Exposes root_agent for ADK discovery.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from .tools.pipeline_tools import full_rag_query, append_citations
from .tools.quality_tools import check_answer_quality

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env", override=True)

_LLM_MODEL = os.getenv("LLM_MODEL", "google/gemma-3n-e4b")


def create_pipeline_rag_agent() -> LlmAgent:
    agent = LlmAgent(
        name="pipeline_rag_agent",
        model=LiteLlm(model=f"openai/{_LLM_MODEL}"),
        description=(
            "Runs the full 10-step GraphRAG retrieval pipeline (BM25 + vector + "
            "graph expansion + reranker) with quality-gated retry, and returns "
            "a cited answer."
        ),
        instruction=(
            "You are the Pipeline RAG agent for an automotive consulting knowledge base.\n\n"
            "Follow these steps IN ORDER. Do not skip any step.\n\n"

            "STEP 1 — Retrieve:\n"
            "  Call full_rag_query with the exact question provided.\n"
            "  If status is 'error', respond: 'Retrieval failed: <error message>' and stop.\n\n"

            "STEP 2 — Quality check:\n"
            "  Call check_answer_quality with:\n"
            "    answer        = the 'answer' field from STEP 1\n"
            "    citations_block = the 'citations_block' field from STEP 1\n\n"

            "STEP 3 — Retry if needed (ONE retry maximum):\n"
            "  If check_answer_quality returned verdict 'RETRY':\n"
            "    Call full_rag_query again with the question prefixed exactly as:\n"
            "    'Provide comprehensive detail on: <original question>'\n"
            "    Use the result of this retry for all subsequent steps.\n"
            "  If verdict is 'PASS', skip directly to STEP 4.\n"
            "  Do NOT retry more than once regardless of the quality verdict.\n\n"

            "STEP 4 — Write your answer:\n"
            "  Use the 'answer' field from the most recent full_rag_query result.\n"
            "  Copy the answer text as-is. Preserve all inline [N] citation markers.\n\n"

            "STEP 5 — MANDATORY: Append citations:\n"
            "  Call append_citations passing the 'citations_block' value from the most\n"
            "  recent full_rag_query result.\n"
            "  Append the returned citations_block verbatim at the end of your response\n"
            "  on a new line.\n\n"

            "CITATIONS ARE MANDATORY. Every response must end with the Citations block.\n"
            "Example format:\n"
            "  <answer text with [1][2] inline markers>\n\n"
            "  Citations:\n"
            "    [1] document.pdf, p.3\n"
            "    [2] report.pptx, p.7"
        ),
        output_key="pipeline_rag_result",
        tools=[full_rag_query, check_answer_quality, append_citations],
    )
    return agent


root_agent = create_pipeline_rag_agent()
