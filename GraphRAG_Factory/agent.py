"""GraphRAG Master Orchestrator — top-level ADK Factory agent.

Routes user queries to one of two sub-agents via AgentTool:
  - pipeline_rag_agent: full 10-step GraphRAG pipeline (Phase 1, active)
  - search_rag_agent:   individual targeted search tools (Phase 2, stub)

The master synthesizes results from the sub-agent and delivers insights
to the user.

Exposes root_agent for ADK discovery (required by adk web).
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.agent_tool import AgentTool

from .sub_agents.pipeline_rag_agent.agent import create_pipeline_rag_agent
from .sub_agents.search_rag_agent.agent import create_search_rag_agent

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env", override=True)

_LLM_MODEL = os.getenv("LLM_MODEL", "google/gemma-3n-e4b")


def create_graphrag_factory_agent() -> LlmAgent:
    pipeline_rag_tool = AgentTool(agent=create_pipeline_rag_agent())
    search_rag_tool = AgentTool(agent=create_search_rag_agent())

    agent = LlmAgent(
        name="graphrag_master_agent",
        model=LiteLlm(model=f"openai/{_LLM_MODEL}"),
        description=(
            "Master orchestrator for the Automotive Consulting GraphRAG system. "
            "Routes queries to RAG sub-agents and synthesizes insights for the user."
        ),
        instruction=(
            "You are the Master Orchestrator for an Automotive Consulting knowledge base system.\n\n"
            "You have access to two sub-agents as tools:\n"
            "1. pipeline_rag_agent — runs the full 10-step retrieval pipeline "
            "(BM25 + vector + graph expansion + reranker). Use this for most questions.\n"
            "2. search_rag_agent — runs targeted individual searches for complex or "
            "multi-part queries. NOTE: This is Phase 2 and not yet active.\n\n"
            "ROUTING RULES:\n"
            "- Standard questions (single topic, general Q&A, 'what', 'how', 'why') "
            "→ call pipeline_rag_agent with the user's question.\n"
            "- Complex queries (multi-part, comparisons, entity relationship lookups, "
            "'compare X and Y', 'what connects A to B') → call search_rag_agent. "
            "If it responds as unavailable, fall back to pipeline_rag_agent.\n\n"
            "AFTER receiving results from the sub-agent:\n"
            "1. Synthesize the answer into clear, concise consulting insights.\n"
            "2. Highlight key findings, patterns, or strategic implications.\n"
            "3. Present citations at the end so the user can trace sources.\n"
            "4. If no results were found, say so clearly and suggest rephrasing.\n\n"
            "ALWAYS pass the original user question exactly as stated when calling a sub-agent.\n"
            "Be professional, concise, and focused on automotive industry context."
        ),
        tools=[pipeline_rag_tool, search_rag_tool],
    )
    return agent


root_agent = create_graphrag_factory_agent()
