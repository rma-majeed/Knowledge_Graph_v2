"""Search RAG sub-agent — Phase 2 stub.

Phase 2 will implement individual granular tools:
  - vector_search: ChromaDB semantic search
  - bm25_search: SQLite BM25 keyword search
  - graph_search: KuzuDB graph traversal

Currently returns a graceful not-available message so the master agent
can fall back to pipeline_rag_agent.

Exposes root_agent for ADK discovery.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from .tools.search_tools import vector_search, bm25_search, graph_search

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env", override=True)

_LLM_MODEL = os.getenv("LLM_MODEL", "google/gemma-3n-e4b")


def create_search_rag_agent() -> LlmAgent:
    agent = LlmAgent(
        name="search_rag_agent",
        model=LiteLlm(model=f"openai/{_LLM_MODEL}"),
        description=(
            "Phase 2: Runs targeted individual searches (vector, BM25, graph) "
            "for complex or multi-part queries. Currently a stub — not yet implemented."
        ),
        instruction=(
            "You are the Search RAG agent for an automotive consulting knowledge base.\n\n"
            "IMPORTANT: This agent is not yet fully implemented (Phase 2).\n\n"
            "If called, respond with:\n"
            "'The Search RAG agent (individual tool mode) is not yet available. "
            "Please use the Pipeline RAG agent for your query.'\n\n"
            "Do not attempt to call any tools — return the message above directly."
        ),
        output_key="search_rag_result",
        tools=[vector_search, bm25_search, graph_search],
    )
    return agent


root_agent = create_search_rag_agent()
