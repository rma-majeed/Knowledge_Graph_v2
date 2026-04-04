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

from .tools.pipeline_tools import full_rag_query

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
            "When given a question:\n"
            "1. Call full_rag_query with the exact question provided.\n"
            "2. If status is 'success', return the answer and citations as-is.\n"
            "3. If status is 'error', return: 'Retrieval failed: <error message>'\n\n"
            "Do NOT rephrase or modify the answer — return it exactly as the tool provides.\n"
            "Always include the citations list in your response."
        ),
        output_key="pipeline_rag_result",
        tools=[full_rag_query],
    )
    return agent


root_agent = create_pipeline_rag_agent()
