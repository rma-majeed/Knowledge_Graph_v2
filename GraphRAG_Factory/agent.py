"""GraphRAG Master Orchestrator — top-level ADK Factory agent.

Routes user queries to sub-agents via AgentTool:
  - pipeline_rag_agent: full 10-step GraphRAG pipeline with quality-gated retry
  - search_rag_agent:   individual targeted search tools for complex queries
  - reasoning_agent:    structured analytical synthesis (optional — see REASONING_AGENT_ENABLED)

Routing is DETERMINISTIC via detect_route() — the LLM never decides which path
to take. detect_route() keyword-matches the question and returns an explicit
route string. The LLM's only job is to execute the steps for that route.

Routes (when reasoning enabled):
  "pipeline_only"  → pipeline_rag_agent → passthrough_citations
  "search_only"    → search_rag_agent   → passthrough_citations
  "analytical"     → pipeline_rag_agent → reasoning_agent → passthrough_citations

Routes (when reasoning disabled — default):
  "pipeline_only"  → pipeline_rag_agent → passthrough_citations
  "search_only"    → search_rag_agent   → passthrough_citations
  (analytical keywords fall through to "pipeline_only")

Feature flag — set in .env:
  REASONING_AGENT_ENABLED=true   # enable reasoning_agent for analytical queries
  REASONING_AGENT_ENABLED=false  # default — pipeline + search only

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

# Read reasoning agent feature flag
_raw = os.getenv("REASONING_AGENT_ENABLED", "false").strip().lower()
_REASONING_ENABLED: bool = _raw not in ("false", "0", "no", "off")

# ---------------------------------------------------------------------------
# Keyword sets for deterministic routing — no LLM judgment
# ---------------------------------------------------------------------------

_ANALYTICAL_KEYWORDS = frozenset([
    "analyze", "analyse", "analysis",
    "implications", "implication",
    "strategic", "strategy",
    "recommend", "recommendation",
    "evaluate", "evaluation",
    "assess", "assessment",
    "significance",
    "impact",
    "justify", "justification",
    "critique", "critically",
])

_SEARCH_KEYWORDS = frozenset([
    "compare", "comparison", "versus", " vs ",
    "suppliers", "supplier",
    "connects", "connection", "relationship",
    "between", "link", "links",
])


# ---------------------------------------------------------------------------
# Deterministic routing tool — called first on every query
# ---------------------------------------------------------------------------

def detect_route(question: str) -> dict:
    """Detect which processing route to use for this question.

    ALWAYS call this tool FIRST before calling any other tool.
    Returns a route string that determines the exact sequence of tool calls
    to make. Never skip this step — the route must come from this tool,
    not from your own judgment.

    Routes returned:
      "analytical"    → call pipeline_rag_agent, THEN reasoning_agent
                        (only returned when REASONING_AGENT_ENABLED=true)
      "search_only"   → call search_rag_agent only
      "pipeline_only" → call pipeline_rag_agent only

    Args:
        question: The exact user question, unchanged.

    Returns:
        Dict with:
          - route:  "analytical" | "search_only" | "pipeline_only"
          - reason: Which keywords triggered the route (for logging).
    """
    q_lower = question.lower()

    # Analytical check — only return "analytical" route when feature is enabled
    if _REASONING_ENABLED:
        for kw in _ANALYTICAL_KEYWORDS:
            if kw in q_lower:
                return {
                    "route": "analytical",
                    "reason": f"Analytical keyword matched: '{kw}' (reasoning enabled).",
                }

    # Entity / comparison check
    for kw in _SEARCH_KEYWORDS:
        if kw in q_lower:
            return {
                "route": "search_only",
                "reason": f"Search/entity keyword matched: '{kw}'.",
            }

    # Default: standard Q&A (also covers analytical when reasoning is disabled)
    reason = (
        "No search keywords detected — standard Q&A."
        if not _REASONING_ENABLED
        else "No analytical or search keywords detected — standard Q&A."
    )
    return {"route": "pipeline_only", "reason": reason}


# ---------------------------------------------------------------------------
# Passthrough citations — deterministic, prevents LLM reformatting
# ---------------------------------------------------------------------------

def passthrough_citations(citations_block: str) -> dict:
    """Return the citations block verbatim so it can be appended to the answer.

    ALWAYS call this as your FINAL step. Pass the full 'Citations:' section
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


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

def create_graphrag_factory_agent() -> LlmAgent:
    pipeline_rag_tool = AgentTool(agent=create_pipeline_rag_agent())
    search_rag_tool = AgentTool(agent=create_search_rag_agent())

    tools = [detect_route, pipeline_rag_tool, search_rag_tool, passthrough_citations]

    if _REASONING_ENABLED:
        from .sub_agents.reasoning_agent.agent import create_reasoning_agent
        reasoning_tool = AgentTool(agent=create_reasoning_agent())
        tools.insert(3, reasoning_tool)  # insert before passthrough_citations

    # Base instruction — two routes always present
    base_instruction = (
        "You are the Master Orchestrator for an Automotive Consulting knowledge base.\n\n"

        "STEP 1 — MANDATORY FIRST ACTION: Call detect_route(question).\n"
        "  Pass the user's exact question. Do not skip this step.\n"
        "  The returned 'route' value tells you exactly what to do next.\n\n"

        "STEP 2 — Execute the route returned by detect_route:\n\n"

        "  If route is 'pipeline_only':\n"
        "    a) Call pipeline_rag_agent with the user's question.\n"
        "    b) Write a consulting answer using the result. Include Key Findings "
        "as bullet points. Use inline [N] citation markers from the result.\n"
        "    c) Call passthrough_citations with the citations_block from the result.\n"
        "    d) Append the returned citations_block verbatim at the end.\n\n"

        "  If route is 'search_only':\n"
        "    a) Call search_rag_agent with the user's question.\n"
        "    b) Write a consulting answer using the result. Include Key Findings "
        "as bullet points. Use inline [N] citation markers from the result.\n"
        "    c) Call passthrough_citations with the citations_block from the result.\n"
        "    d) Append the returned citations_block verbatim at the end.\n\n"
    )

    # Route C appended only when reasoning is enabled
    analytical_instruction = (
        "  If route is 'analytical':\n"
        "    a) Call pipeline_rag_agent with the user's question.\n"
        "    b) Call reasoning_agent with this EXACT message:\n"
        "       'Question: <user question>\\n\\nRAG Result:\\n<full pipeline_rag_agent output>'\n"
        "    c) Output the reasoning_agent result as-is. Do NOT rewrite or summarise it.\n"
        "    d) Call passthrough_citations with the citations_block from reasoning_agent.\n"
        "    e) Append the returned citations_block verbatim at the end.\n\n"
    ) if _REASONING_ENABLED else ""

    closing_instruction = (
        "CITATIONS ARE MANDATORY. Every response must end with:\n"
        "  Citations:\n"
        "    [1] document.pdf, p.N\n\n"
        "If no results were found, say so clearly and suggest rephrasing.\n"
        "Always pass the original user question unchanged when calling any sub-agent."
    )

    agent = LlmAgent(
        name="graphrag_master_agent",
        model=LiteLlm(model=f"openai/{_LLM_MODEL}"),
        description=(
            "Master orchestrator for the Automotive Consulting GraphRAG system. "
            "Routes queries deterministically and synthesizes cited answers."
        ),
        instruction=base_instruction + analytical_instruction + closing_instruction,
        tools=tools,
    )
    return agent


root_agent = create_graphrag_factory_agent()
