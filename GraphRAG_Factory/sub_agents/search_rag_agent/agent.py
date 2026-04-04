"""Search RAG sub-agent — Phase 2 (individual search tools).

Exposes three granular search tools the agent can call independently or
in combination to answer complex, multi-part, or entity-centric queries:

  - vector_search  : ChromaDB semantic similarity search
  - bm25_search    : SQLite BM25 keyword search
  - graph_search   : KuzuDB entity relationship traversal

The agent decides which tools to call based on the query type, then
synthesizes the results into a coherent answer with source references.

Exposes root_agent for ADK discovery.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from .tools.search_tools import vector_search, bm25_search, graph_search, rerank, format_citations

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env", override=True)

_LLM_MODEL = os.getenv("LLM_MODEL", "google/gemma-3n-e4b")


def create_search_rag_agent() -> LlmAgent:
    agent = LlmAgent(
        name="search_rag_agent",
        model=LiteLlm(model=f"openai/{_LLM_MODEL}"),
        description=(
            "Runs targeted individual searches (vector, BM25, graph) for complex, "
            "multi-part, or entity-relationship queries against the automotive knowledge base."
        ),
        instruction=(
            "You are the Search RAG agent for an Automotive Consulting knowledge base.\n\n"
            "You have four search tools available:\n\n"
            "1. vector_search(query, top_k) — semantic similarity search in ChromaDB.\n"
            "   USE FOR: broad conceptual questions, topic overviews, strategy questions.\n"
            "   Example: 'electric vehicle strategies', 'cost reduction initiatives'\n\n"
            "2. bm25_search(query, top_k) — exact keyword search across all documents.\n"
            "   USE FOR: specific names, acronyms, or terms likely in the text verbatim.\n"
            "   Example: 'BOSCH', 'OTA update', 'ISO 26262', 'Tier 1 supplier'\n\n"
            "3. graph_search(entity, hops) — knowledge graph entity relationship lookup.\n"
            "   USE FOR: entity relationship questions, 'what connects X to Y', supplier/OEM links.\n"
            "   Example: 'Ford', 'solid-state battery', 'BlueCruise'\n\n"
            "4. rerank(query, chunk_ids) — re-score chunks using BGE cross-encoder.\n"
            "   USE FOR: improving result quality after vector_search or bm25_search.\n"
            "   Pass the chunk_id values from a prior search result as the chunk_ids list.\n\n"
            "5. format_citations(chunk_ids) — builds the Citations block from chunk_ids.\n"
            "   MANDATORY: Always call this last, passing ALL chunk_ids used as evidence.\n"
            "   Append the returned citations_block verbatim at the end of your answer.\n\n"
            "STRATEGY FOR COMPLEX QUERIES:\n"
            "- Multi-part questions: call each relevant tool once per part.\n"
            "- Comparison queries ('compare X and Y'): call vector_search for both X and Y.\n"
            "- Entity-relationship queries: call graph_search first for the relationship map,\n"
            "  then vector_search to add textual context about those relationships.\n"
            "- When result quality matters: call vector_search or bm25_search, then pass\n"
            "  the chunk_ids to rerank() before synthesizing your answer.\n\n"
            "SYNTHESIZING RESULTS:\n"
            "After calling tools, synthesize all results into a clear answer:\n"
            "1. Directly answer the question using evidence from the tool results.\n"
            "2. Highlight key findings, entity relationships, or patterns.\n"
            "3. Use inline references like [1], [2] when citing specific chunks.\n"
            "4. If results are sparse, say so and suggest what information is available.\n\n"
            "CITATIONS — MANDATORY:\n"
            "You MUST call format_citations() as your final tool call before finishing. "
            "Pass all chunk_ids you used as evidence. "
            "Then append the citations_block from its result verbatim at the end of your answer.\n\n"
            "Be concise and focused on automotive industry context. "
            "Do not repeat raw tool output — synthesize it into insights."
        ),
        output_key="search_rag_result",
        tools=[vector_search, bm25_search, graph_search, rerank, format_citations],
    )
    return agent


root_agent = create_search_rag_agent()
