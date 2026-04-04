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


def passthrough_citations(citations_block: str) -> dict:
    """Return the citations block verbatim so it can be appended to the answer.

    ALWAYS call this as your final step. Pass the full 'Citations:' section
    text from the sub-agent result. Append the returned citations_block
    verbatim at the end of your response.

    Args:
        citations_block: The exact 'Citations:\\n  [1] ...' text from the sub-agent.

    Returns:
        Dict with citations_block to append verbatim.
    """
    block = (citations_block or "").strip()
    if not block or block == "(No source citations available.)":
        return {"citations_block": "(No source citations available.)"}
    if not block.startswith("Citations:"):
        block = "Citations:\n" + block
    return {"citations_block": block}

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
            "2. search_rag_agent — runs targeted individual searches (vector, BM25, graph) "
            "for complex, multi-part, or entity-relationship queries.\n\n"
            "ROUTING RULES:\n"
            "- Standard questions (single topic, general Q&A, 'what', 'how', 'why') "
            "→ call pipeline_rag_agent with the user's question.\n"
            "- Complex queries: multi-part questions, comparisons ('compare X and Y'), "
            "entity relationship lookups ('what suppliers does Toyota use', 'what connects A to B') "
            "→ call search_rag_agent.\n\n"
            "AFTER receiving results from the sub-agent, follow these steps IN ORDER:\n\n"
            "STEP 1 — Write your answer:\n"
            "  Synthesize the answer into clear consulting insights.\n"
            "  Include Key Findings as bullet points where helpful.\n"
            "  Use inline [N] citation markers from the sub-agent result.\n\n"
            "STEP 2 — MANDATORY: Find the 'Citations:' block in the sub-agent result.\n"
            "  It looks like: 'Citations:\\n  [1] filename.pdf, p.N'\n"
            "  Call passthrough_citations() passing that exact text as citations_block.\n\n"
            "STEP 3 — MANDATORY: Append the citations_block returned by passthrough_citations\n"
            "  verbatim at the end of your response on a new line.\n\n"
            "CITATIONS ARE MANDATORY in every response. Final output must always end with:\n"
            "  Citations:\n"
            "    [1] document.pdf, p.N\n\n"
            "If the sub-agent found no results, say so clearly and suggest rephrasing.\n"
            "ALWAYS pass the original user question exactly as stated when calling a sub-agent.\n"
            "Be professional, concise, and focused on automotive industry context."
        ),
        tools=[pipeline_rag_tool, search_rag_tool, passthrough_citations],
    )
    return agent


root_agent = create_graphrag_factory_agent()
