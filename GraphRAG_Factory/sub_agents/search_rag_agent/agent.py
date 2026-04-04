"""Search RAG sub-agent — Phase 2 (individual search tools + quality gate).

Exposes granular search tools the agent can call independently or in
combination to answer complex, multi-part, or entity-centric queries:

  - vector_search  : ChromaDB semantic similarity search
  - bm25_search    : SQLite BM25 keyword search
  - graph_search   : KuzuDB entity relationship traversal
  - rerank         : BGE cross-encoder re-scoring
  - format_citations: build the Citations block from chunk_ids

After synthesizing the answer and calling format_citations, the agent calls
check_answer_quality. If verdict is RETRY, it calls vector_search again with
a broadened prefix, merges chunk_ids, and re-calls format_citations.
Maximum one retry.

Exposes root_agent for ADK discovery.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from .tools.search_tools import vector_search, bm25_search, graph_search, rerank, format_citations
from ..pipeline_rag_agent.tools.quality_tools import check_answer_quality

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
            "   Call this after collecting all chunk_ids used as evidence.\n\n"
            "6. check_answer_quality(answer, citations_block) — quality gate.\n"
            "   Call this AFTER format_citations. Pass your synthesized answer and the\n"
            "   citations_block from format_citations. Returns PASS or RETRY verdict.\n\n"

            "STRATEGY FOR COMPLEX QUERIES:\n"
            "- Multi-part questions: call each relevant tool once per part.\n"
            "- Comparison queries ('compare X and Y'): call vector_search for both X and Y.\n"
            "- Entity-relationship queries: call graph_search first for the relationship map,\n"
            "  then vector_search to add textual context about those relationships.\n"
            "- When result quality matters: call vector_search or bm25_search, then pass\n"
            "  the chunk_ids to rerank() before synthesizing your answer.\n\n"

            "STANDARD SEQUENCE (follow in order):\n\n"

            "STEP 1 — Search: call the appropriate search tool(s) for the question.\n\n"

            "STEP 2 — Synthesize: write your answer using evidence from the tool results.\n"
            "  Directly answer the question. Highlight key findings and entity relationships.\n"
            "  Use inline references like [1], [2] when citing specific chunks.\n\n"

            "STEP 3 — Citations: call format_citations with ALL chunk_ids used as evidence.\n\n"

            "STEP 4 — Quality check: call check_answer_quality with:\n"
            "  answer          = your synthesized answer text from STEP 2\n"
            "  citations_block = the citations_block from format_citations in STEP 3\n\n"

            "STEP 5 — Retry if needed (ONE retry maximum):\n"
            "  If check_answer_quality returns verdict 'RETRY':\n"
            "    a) Call vector_search again with the question prefixed:\n"
            "       'Provide comprehensive detail on: <original question>'\n"
            "    b) Collect the new chunk_ids from this search.\n"
            "    c) Call format_citations again passing ALL chunk_ids "
            "(original + new combined).\n"
            "    d) Update your answer to incorporate any new evidence found.\n"
            "  If verdict is 'PASS': proceed to STEP 6.\n"
            "  Do NOT retry more than once.\n\n"

            "STEP 6 — MANDATORY: Append citations verbatim at the end of your response.\n"
            "  Use the citations_block from the most recent format_citations call.\n\n"

            "CITATIONS ARE MANDATORY. Every response must end with the Citations block.\n"
            "Be concise and focused on automotive industry context.\n"
            "Do not repeat raw tool output — synthesize it into insights."
        ),
        output_key="search_rag_result",
        tools=[vector_search, bm25_search, graph_search, rerank, format_citations, check_answer_quality],
    )
    return agent


root_agent = create_search_rag_agent()
