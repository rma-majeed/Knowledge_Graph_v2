"""Pipeline RAG sub-agent — full 10-step GraphRAG pipeline as an ADK LlmAgent.

This agent receives a question from the Master agent and calls the
full_rag_query tool which runs: query rewrite → BM25 → vector → RRF →
graph expansion → reranker → parent-doc → context assembly → LLM answer.

Exposes root_agent for ADK discovery.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from .tools.pipeline_tools import full_rag_query, append_citations

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env", override=True)

_LLM_MODEL = os.getenv("LLM_MODEL", "google/gemma-3n-e4b")


def create_pipeline_rag_agent() -> LlmAgent:
    agent = LlmAgent(
        name="pipeline_rag_agent",
        model=LiteLlm(model=f"openai/{_LLM_MODEL}"),
        description=(
            "Runs the full 10-step GraphRAG retrieval pipeline (BM25 + vector + "
            "graph expansion + reranker) and returns a cited answer."
        ),
        instruction=(
            "You are the Pipeline RAG agent for an automotive consulting knowledge base.\n\n"
            "STEP 1: Call full_rag_query with the exact question provided.\n"
            "  - If status is 'error', respond: 'Retrieval failed: <error message>' and stop.\n\n"
            "STEP 2: Write your answer using the 'answer' field from the tool result.\n"
            "  Copy the answer text. Use inline [N] citation markers where they appear.\n\n"
            "STEP 3 — MANDATORY: Call append_citations, passing the 'citations_block' value\n"
            "  from the full_rag_query result. Then append the returned citations_block\n"
            "  verbatim at the end of your response on a new line.\n\n"
            "CITATIONS ARE MANDATORY. Every response must end with the Citations block.\n"
            "Example format:\n"
            "  <answer text with [1][2] inline markers>\n\n"
            "  Citations:\n"
            "    [1] document.pdf, p.3\n"
            "    [2] report.pptx, p.7"
        ),
        output_key="pipeline_rag_result",
        tools=[full_rag_query, append_citations],
    )
    return agent


root_agent = create_pipeline_rag_agent()
