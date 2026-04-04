# Agentic RAG Architecture Document
## System B — Automotive Consulting Knowledge Base
### Upgrade from Pipeline RAG to Agentic RAG using Google ADK

**Version:** 1.0  
**Target System:** System B (Automotive GraphRAG)  
**Framework:** Google Agent Development Kit (ADK) for Python  
**Date:** April 2026  
**Purpose:** Reference document for Claude Code to implement agentic RAG on top of existing System B codebase

---

## Table of Contents

1. [Overview and Objective](#1-overview-and-objective)
2. [Current System B Architecture](#2-current-system-b-architecture)
3. [Target Agentic Architecture](#3-target-agentic-architecture)
4. [Agent Team Structure](#4-agent-team-structure)
5. [Agent Specifications](#5-agent-specifications)
6. [Tool Specifications](#6-tool-specifications)
7. [Session and State Management](#7-session-and-state-management)
8. [Google ADK Implementation Guide](#8-google-adk-implementation-guide)
9. [File and Folder Structure](#9-file-and-folder-structure)
10. [Configuration and Environment](#10-configuration-and-environment)
11. [Integration Points with Existing System B](#11-integration-points-with-existing-system-b)
12. [Implementation Sequence for Claude Code](#12-implementation-sequence-for-claude-code)

---

## 1. Overview and Objective

### 1.1 What This Document Is For

This document is the authoritative specification for upgrading System B (Automotive GraphRAG) from a fixed sequential pipeline into a true **Agentic RAG system** using Google's Agent Development Kit (ADK). It is written for Claude Code to use as a build instruction guide.

### 1.2 The Core Problem Being Solved

System B currently runs a deterministic 10-step pipeline on every query regardless of query type. This has several limitations:

- **No retry on poor retrieval** — if step 3 (BM25+vector search) misses relevant chunks, the system generates a poor answer with no self-correction
- **No query decomposition** — complex multi-hop queries like "how did our EV battery recommendations evolve from 2019–2023?" are treated as single retrievals
- **No quality gate** — the system cannot evaluate whether it retrieved enough information before generating
- **No session continuity** — follow-up questions lose context from previous turns
- **No adaptive strategy** — keyword-heavy queries and conceptual queries get the same retrieval treatment

### 1.3 What Agentic RAG Adds

The agentic layer adds:
1. **Query classification** — understand what type of question was asked before retrieving
2. **Sub-query decomposition** — break complex questions into targeted retrievals
3. **Quality evaluation with feedback** — score retrieved context and loop back with specific instructions if insufficient
4. **Adaptive retry** — rewrite queries based on what was missing, not just repeat
5. **Multi-hop synthesis** — connect findings across multiple documents explicitly
6. **Persistent session memory** — conversation history survives and informs follow-up queries

### 1.4 What Does NOT Change

The following System B components are **preserved unchanged** and called by agents as tools:

- `src/ingest/` — document ingestion pipeline
- `src/embed/` — embedding pipeline
- `src/graph/` — KuzuDB knowledge graph construction
- `src/query/pipeline.py` — the core retrieval pipeline (BM25 + vector + RRF + graph + reranker)
- `data/chunks.db` — SQLite chunk storage
- `data/chroma_db/` — ChromaDB vector store
- `data/kuzu_db/` — KuzuDB graph store
- `app.py` (Streamlit UI) — modified to call the new agent layer instead of `pipeline.py` directly

---

## 2. Current System B Architecture

### 2.1 Existing Flow (to be wrapped by agents)

```
User Query (Streamlit)
    ↓
src/query/pipeline.py
    ├── Step 1: Query expansion (3 variants)
    ├── Step 2: BM25 keyword search
    ├── Step 3: ChromaDB vector search
    ├── Step 4: RRF fusion (BM25 + vector)
    ├── Step 5: KuzuDB graph expansion (top-5 seeds)
    ├── Step 6: BGE cross-encoder reranking (top-30 → 20)
    ├── Step 7: Parent-document expansion
    ├── Step 8: Context assembly (2K token budget)
    ├── Step 9: LLM generation (Qwen / cloud)
    └── Step 10: Citation building
```

### 2.2 Key Existing Classes and Functions

Claude Code must be aware of the following existing interfaces:

```python
# src/query/pipeline.py
def answer_question(question: str, db_conn, kuzu_db, llm_client) -> dict:
    # Returns: {"answer": str, "citations": list, "chunks": list}

# src/retrieval/bm25_indexer.py  
class BM25Indexer:
    def build(self, chunks: list) -> None
    def query(self, query: str, n_results: int) -> list

# src/retrieval/vector_store.py
class VectorStore:
    def similarity_search(self, query_embedding, n_results: int) -> list

# src/retrieval/reranker.py
class Reranker:
    def rerank(self, query: str, chunks: list, top_n: int) -> list

# src/graph/kuzu_store.py
class KuzuStore:
    def get_entity_neighbors(self, entity_names: list) -> list
    def get_related_chunks(self, entity_names: list) -> list

# src/config/retrieval_config.py
RAG_ENABLE_BM25: bool
RAG_ENABLE_RERANKER: bool
RAG_ENABLE_PARENT_DOC: bool
RAG_ENABLE_ENRICHMENT: bool
```

---

## 3. Target Agentic Architecture

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Streamlit UI (app.py)                       │
│         User types query → adk_runner.run(query)            │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│              MASTER ORCHESTRATOR AGENT                       │
│              (OrchestratorAgent — LlmAgent)                  │
│  • Classifies query type                                     │
│  • Reads session state for conversation history              │
│  • Routes to appropriate specialist agents via AgentTool     │
│  • Assembles final answer from agent outputs                 │
└──────┬──────────────┬──────────────┬──────────────┬─────────┘
       ↓              ↓              ↓              ↓
┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌──────────────┐
│ Query    │  │  Retrieval   │  │ Quality  │  │  Reasoning   │
│ Rewriter │  │  Agent       │  │ Evaluator│  │  Agent       │
│ Agent    │  │  (LlmAgent)  │  │ Agent    │  │  (LlmAgent)  │
└──────────┘  └──────────────┘  └──────────┘  └──────────────┘
       ↑              ↓                ↓
       └──────────────┴── LOOP ────────┘
              (LoopAgent — max 3 retries)
                      ↓
┌─────────────────────────────────────────────────────────────┐
│              EXISTING SYSTEM B RETRIEVAL TOOLS               │
│  • bm25_search_tool        • vector_search_tool             │
│  • graph_expansion_tool    • rerank_tool                    │
│  • rrf_fusion_tool         • context_assembly_tool          │
└─────────────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│              STORAGE LAYER (unchanged)                       │
│  SQLite chunks.db │ ChromaDB vectors │ KuzuDB graph         │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 ADK Agent Type Mapping

| Agent | ADK Type | Reason |
|---|---|---|
| OrchestratorAgent | `LlmAgent` | Needs LLM reasoning to classify and route |
| QueryRewriterAgent | `LlmAgent` | Needs LLM to generate query variants |
| RetrievalAgent | `LlmAgent` | Needs LLM to decide which tools to call |
| QualityEvaluatorAgent | `LlmAgent` | Needs LLM to score relevance and coverage |
| ReasoningAgent | `LlmAgent` | Needs LLM for multi-document synthesis |
| RetrievalLoopAgent | `LoopAgent` | Drives the retry loop (non-LLM, deterministic) |
| RetrievalPipelineAgent | `SequentialAgent` | Runs retrieval steps in fixed order |

---

## 4. Agent Team Structure

### 4.1 Hierarchy

```
OrchestratorAgent (root_agent)
│
├── QueryRewriterAgent
│
├── RetrievalLoopAgent  [LoopAgent, max_iterations=3]
│   ├── RetrievalAgent
│   │   └── (tools: bm25_search, vector_search, graph_expansion, rrf_fusion, rerank)
│   └── QualityEvaluatorAgent
│       └── (tool: exit_loop — calls escalate=True when quality sufficient)
│
└── ReasoningAgent
    └── (tools: context_assembly, citation_builder)
```

### 4.2 Communication Pattern

Agents communicate via **ADK Session State** — a shared key-value dictionary accessible to all agents within a session. This is the ADK equivalent of passing data between pipeline steps.

Key state variables passed between agents:

```python
# Written by OrchestratorAgent, read by all
session.state["original_query"]       # str: raw user question
session.state["query_type"]           # str: "simple" | "multi_hop" | "comparative" | "temporal"
session.state["conversation_history"] # list: previous turns

# Written by QueryRewriterAgent, read by RetrievalAgent
session.state["sub_queries"]          # list[str]: expanded query variants
session.state["retry_feedback"]       # str: specific gap description from evaluator

# Written by RetrievalAgent, read by QualityEvaluatorAgent
session.state["retrieved_chunks"]     # list[dict]: chunk objects with text, source, score
session.state["retrieval_attempt"]    # int: current loop iteration (1, 2, 3)

# Written by QualityEvaluatorAgent, read by OrchestratorAgent
session.state["quality_score"]        # float: 0.0–1.0
session.state["quality_passed"]       # bool
session.state["coverage_gaps"]        # str: what was missing

# Written by ReasoningAgent, read by OrchestratorAgent
session.state["synthesised_context"]  # str: connected findings across documents
session.state["final_answer"]         # str
session.state["citations"]            # list[dict]
```

---

## 5. Agent Specifications

### 5.1 OrchestratorAgent

**ADK Type:** `LlmAgent`  
**Model:** `gemini-2.0-flash` (primary) or LiteLLM-routed provider  
**Role:** Root agent. The entry point for every user query. Plans execution and assembles final response.

**Responsibilities:**
- Classify the incoming query into one of four types: `simple`, `multi_hop`, `comparative`, `temporal`
- Resolve pronouns and references using conversation history from session state (e.g., "their strategy" → resolve to specific OEM from previous turn)
- Decide whether to invoke the full retrieval loop or answer directly from session history
- Receive final synthesised answer from ReasoningAgent and format it for the UI

**ADK Definition:**

```python
from google.adk.agents import LlmAgent
from google.adk.tools import agent_tool

orchestrator_agent = LlmAgent(
    name="OrchestratorAgent",
    model="gemini-2.0-flash",
    description="Root orchestrator for automotive consulting knowledge base queries.",
    instruction="""
You are the master orchestrator for an automotive consulting knowledge base containing
10 years of consulting PDFs and PowerPoint presentations.

Your job when receiving a query:
1. Read {conversation_history} from session state to resolve any references (e.g. pronouns, "that company")
2. Classify the query type:
   - simple: single-fact lookup (answer likely in one document)
   - multi_hop: requires connecting information across multiple documents or time periods
   - comparative: requires comparing entities (OEMs, suppliers, strategies)
   - temporal: asks about evolution or change over time
3. Write the classification to session state as query_type
4. Write the resolved query to session state as original_query
5. Delegate to QueryRewriterAgent first, then the RetrievalLoopAgent, then ReasoningAgent
6. Return the final_answer from session state as your response, preserving all citations

For simple queries, you may reduce max retrieval iterations to 1.
For multi_hop and temporal queries, allow up to 3 retrieval iterations.
Always include the citation table in your final response.
    """,
    sub_agents=[query_rewriter_agent, retrieval_loop_agent, reasoning_agent],
    output_key="orchestrator_output"
)
```

**Session State Read:** `conversation_history`  
**Session State Write:** `query_type`, `original_query`

---

### 5.2 QueryRewriterAgent

**ADK Type:** `LlmAgent`  
**Model:** `gemini-2.0-flash`  
**Role:** Transforms the original query into targeted sub-queries optimised for the retrieval pipeline.

**Responsibilities:**
- Generate 3–5 sub-queries from the original query, each targeting a different aspect or phrasing
- On retry (when `retry_feedback` exists in state): generate new sub-queries specifically targeting the gaps identified by QualityEvaluatorAgent
- Use automotive consulting domain vocabulary in sub-queries (OEM names, supplier names, technology terms)
- Ensure sub-queries cover both keyword-friendly phrasing (for BM25) and conceptual phrasing (for vector)

**ADK Definition:**

```python
query_rewriter_agent = LlmAgent(
    name="QueryRewriterAgent",
    model="gemini-2.0-flash",
    description="Expands and reformulates queries for hybrid retrieval.",
    instruction="""
You are a query expansion specialist for an automotive consulting knowledge base.

You will receive:
- original_query: {original_query}
- query_type: {query_type}
- retry_feedback: {retry_feedback}  (empty on first attempt, filled on retries)
- retrieval_attempt: {retrieval_attempt}

Your task:
1. If retry_feedback is empty (first attempt):
   Generate 3–5 sub-queries from original_query that:
   - Cover different phrasings (exact terms, synonyms, conceptual descriptions)
   - Include at least one sub-query with specific entity names (OEM, supplier, technology)
   - Include at least one sub-query with contextual/conceptual language
   - For temporal queries: include year-specific sub-queries (one per time period)
   - For comparative queries: include one sub-query per entity being compared

2. If retry_feedback is NOT empty (retry attempt):
   Generate 2–3 NEW sub-queries specifically targeting the gaps described in retry_feedback.
   Do NOT repeat sub-queries from previous attempts.
   Focus precisely on what was described as missing.

Output format (write to session state as sub_queries):
Return a JSON array of strings. Example:
["Toyota EV battery supplier strategy 2022",
 "battery supply chain automotive OEM recommendation",
 "CATL LG Energy Toyota partnership consulting"]

Domain context: queries will search documents about automotive consulting,
OEM strategies, EV transitions, supplier relationships, cost reduction,
and market analysis from 2015–2025.
    """,
    output_key="sub_queries"
)
```

**Session State Read:** `original_query`, `query_type`, `retry_feedback`, `retrieval_attempt`  
**Session State Write:** `sub_queries`

---

### 5.3 RetrievalLoopAgent

**ADK Type:** `LoopAgent`  
**Model:** N/A (workflow agent, not LLM-powered)  
**Role:** Drives the retry loop between RetrievalAgent and QualityEvaluatorAgent.

**Responsibilities:**
- Execute RetrievalAgent followed by QualityEvaluatorAgent in sequence, repeatedly
- Stop when QualityEvaluatorAgent signals sufficient quality (via `exit_loop` tool)
- Stop after maximum 3 iterations regardless of quality score
- Pass loop iteration count to session state

**ADK Definition:**

```python
from google.adk.agents import LoopAgent

retrieval_loop_agent = LoopAgent(
    name="RetrievalLoopAgent",
    description="Iterative retrieval loop with quality gate.",
    sub_agents=[retrieval_agent, quality_evaluator_agent],
    max_iterations=3
)
```

**Notes for Claude Code:**
- `LoopAgent` is not LLM-powered. It simply executes sub-agents in sequence and repeats.
- Loop termination is controlled by `QualityEvaluatorAgent` calling `exit_loop` tool (ADK built-in).
- `max_iterations=3` is the hard stop — prevents infinite loops on difficult queries.
- After `max_iterations`, the loop exits automatically and proceeds to `ReasoningAgent` with whatever chunks were found.

---

### 5.4 RetrievalAgent

**ADK Type:** `LlmAgent`  
**Model:** `gemini-2.0-flash`  
**Role:** Executes hybrid retrieval across all three channels using the sub-queries from QueryRewriterAgent.

**Responsibilities:**
- For each sub-query in `sub_queries`: call BM25 search, vector search, and graph expansion tools
- Fuse all results using RRF fusion tool
- Apply BGE cross-encoder reranking
- Store retrieved chunks in session state
- Track retrieval attempt number

**ADK Definition:**

```python
retrieval_agent = LlmAgent(
    name="RetrievalAgent",
    model="gemini-2.0-flash",
    description="Executes hybrid retrieval across BM25, vector, and graph channels.",
    instruction="""
You are the retrieval specialist for an automotive consulting knowledge base.

You have access to the following tools:
- bm25_search(query, n_results): keyword-based search
- vector_search(query, n_results): semantic embedding search
- graph_expansion(chunk_ids, n_neighbors): KuzuDB entity graph traversal
- rrf_fusion(bm25_results, vector_results): Reciprocal Rank Fusion merger
- rerank(query, chunks, top_n): BGE cross-encoder reranking

Your task:
1. Read sub_queries from session state: {sub_queries}
2. For EACH sub-query, call both bm25_search and vector_search with n_results=10
3. Collect all BM25 results and all vector results across all sub-queries
4. Call rrf_fusion with the combined BM25 and vector result lists
5. Take the top-5 chunks from RRF results and call graph_expansion to find related entity chunks
6. Call rerank with the original_query and all candidate chunks (RRF + graph), top_n=20
7. Write the top 20 reranked chunks to session state as retrieved_chunks
8. Increment retrieval_attempt in session state by 1

Important: Do not summarise or modify the chunks. Store them exactly as returned by tools.
Always run ALL sub-queries before calling rrf_fusion.
    """,
    tools=[
        bm25_search_tool,
        vector_search_tool,
        graph_expansion_tool,
        rrf_fusion_tool,
        rerank_tool
    ],
    output_key="retrieved_chunks"
)
```

**Session State Read:** `sub_queries`, `original_query`  
**Session State Write:** `retrieved_chunks`, `retrieval_attempt`  
**Tools Used:** `bm25_search`, `vector_search`, `graph_expansion`, `rrf_fusion`, `rerank`

---

### 5.5 QualityEvaluatorAgent

**ADK Type:** `LlmAgent`  
**Model:** `gemini-2.0-flash`  
**Role:** Scores the quality of retrieved chunks against the original query and decides whether to continue the loop or proceed to synthesis.

**Responsibilities:**
- Score retrieved chunks on three dimensions: relevance, coverage, and completeness
- Identify specific gaps in coverage (missing time periods, missing entities, missing aspects)
- If quality is sufficient: call `exit_loop` tool to break the LoopAgent cycle
- If quality is insufficient and `retrieval_attempt < 3`: write specific gap description to `retry_feedback` in session state
- On third attempt: always call `exit_loop` regardless of score (fallback behaviour)

**Quality Scoring Criteria:**

| Dimension | Description | Weight |
|---|---|---|
| Relevance | Are chunks directly about the query topic? | 40% |
| Coverage | Do chunks cover all aspects/entities/time periods asked about? | 40% |
| Completeness | Is there enough content to synthesise a complete answer? | 20% |

**ADK Definition:**

```python
from google.adk.tools.tool_context import ToolContext

def exit_loop(tool_context: ToolContext) -> dict:
    """
    Signals the LoopAgent to stop iterating and proceed to ReasoningAgent.
    Call this when retrieved context quality is sufficient OR on the 3rd attempt.
    """
    tool_context.actions.escalate = True
    return {"status": "loop_terminated", "reason": "quality_sufficient_or_max_attempts"}

quality_evaluator_agent = LlmAgent(
    name="QualityEvaluatorAgent",
    model="gemini-2.0-flash",
    description="Evaluates retrieval quality and decides whether to retry or proceed.",
    instruction="""
You are the quality evaluator for a retrieval-augmented generation system
serving automotive consultants.

You will receive:
- original_query: {original_query}
- query_type: {query_type}
- retrieved_chunks: {retrieved_chunks}
- retrieval_attempt: {retrieval_attempt}

Your task:
1. Evaluate the retrieved_chunks against the original_query on:
   - Relevance (0–10): Are chunks directly about what was asked?
   - Coverage (0–10): Are all key entities, time periods, and aspects represented?
   - Completeness (0–10): Is there enough to write a complete, cited answer?

2. Calculate overall quality_score = (relevance*0.4 + coverage*0.4 + completeness*0.2) / 10

3. Write quality_score and quality_passed (True if score >= 0.65) to session state

4. Decision logic:
   a. If quality_passed is True: call exit_loop tool. Write "SUFFICIENT" to coverage_gaps.
   b. If quality_passed is False AND retrieval_attempt < 3:
      - Write a specific, actionable description to coverage_gaps that explains exactly
        what is missing. Examples:
        "Missing chunks about 2020–2021 period. Found 2019 and 2022 but gap in middle years."
        "Found Toyota EV strategy but no supplier-specific recommendations."
        "Chunks are about battery chemistry, not supply chain procurement as asked."
      - Write coverage_gaps content to retry_feedback in session state
      - Do NOT call exit_loop (loop will continue)
   c. If retrieval_attempt >= 3: call exit_loop regardless of score. 
      Write "MAX_ATTEMPTS_REACHED" to coverage_gaps.

Be specific and actionable in coverage_gaps — the QueryRewriterAgent will use this
to generate better sub-queries on the next iteration.
    """,
    tools=[exit_loop],
    output_key="quality_evaluation"
)
```

**Session State Read:** `original_query`, `query_type`, `retrieved_chunks`, `retrieval_attempt`  
**Session State Write:** `quality_score`, `quality_passed`, `coverage_gaps`, `retry_feedback`  
**Tools Used:** `exit_loop` (ADK ToolContext escalate pattern)

---

### 5.6 ReasoningAgent

**ADK Type:** `LlmAgent`  
**Model:** `gemini-2.0-flash` (or stronger cloud model for synthesis)  
**Role:** Synthesises retrieved chunks into a coherent, cited answer. This is the only agent that generates the user-facing response.

**Responsibilities:**
- Read `retrieved_chunks` and `original_query` from session state
- Explicitly connect findings across documents (this is the multi-hop synthesis step)
- Generate a structured answer appropriate to the `query_type`:
  - `simple`: direct answer with single citation
  - `multi_hop`: narrative connecting findings from multiple sources
  - `comparative`: structured comparison with entity-by-entity breakdown
  - `temporal`: chronological narrative showing evolution over time
- Build citation table with HIGH/LOW confidence badges
- Write `final_answer` and `citations` to session state
- Append current turn to `conversation_history` for future session continuity

**ADK Definition:**

```python
reasoning_agent = LlmAgent(
    name="ReasoningAgent",
    model="gemini-2.0-flash",
    description="Synthesises retrieved context into a cited, structured answer.",
    instruction="""
You are the synthesis specialist for an automotive consulting knowledge base.
You serve a team of professional automotive consultants who need accurate,
cited, well-structured answers from 10 years of internal consulting documents.

You will receive:
- original_query: {original_query}
- query_type: {query_type}
- retrieved_chunks: {retrieved_chunks}
- quality_score: {quality_score}
- coverage_gaps: {coverage_gaps}

Your task:
1. Read ALL retrieved_chunks carefully. Do not skip any.

2. Identify connections across chunks — especially:
   - Same entity (OEM, supplier) mentioned in multiple documents over time
   - Contradictions or changes in recommendation across time periods
   - Supporting evidence that reinforces a recommendation
   - Related entities connected through shared strategies or relationships

3. Generate a response structured by query_type:
   - simple: 2–3 paragraphs with inline citations [Source: filename, p.X]
   - multi_hop: narrative with explicit connective language ("Building on the 2019 
     finding in [Source A], the 2022 review [Source B] shows...")
   - comparative: entity-by-entity breakdown with citations per entity
   - temporal: chronological structure with year markers and citations

4. Build a citation table at the end:
   - HIGH confidence: chunk cited by 2+ sources or explicitly stated recommendation
   - LOW confidence: single-source or indirect inference

5. If coverage_gaps is not "SUFFICIENT" or "MAX_ATTEMPTS_REACHED":
   Add a brief note: "Note: Coverage may be incomplete — [coverage_gaps description]."

6. Write final_answer (complete response text) to session state
7. Write citations (list of dicts with filename, page, confidence) to session state
8. Append to conversation_history: {"role": "assistant", "query": original_query, 
   "answer_summary": first 200 chars of final_answer}

Tone: Professional consulting language. Be precise about what documents say vs. what
you are inferring. Never fabricate citations. If a claim has no supporting chunk,
do not include it.
    """,
    tools=[context_assembly_tool, citation_builder_tool],
    output_key="final_answer"
)
```

**Session State Read:** `original_query`, `query_type`, `retrieved_chunks`, `quality_score`, `coverage_gaps`  
**Session State Write:** `final_answer`, `citations`, `conversation_history` (append)  
**Tools Used:** `context_assembly_tool`, `citation_builder_tool`

---

## 6. Tool Specifications

All tools are Python functions registered with ADK agents. Each tool must have a complete docstring — ADK uses the docstring to describe the tool to the LLM.

### 6.1 bm25_search_tool

**File:** `src/agents/tools/retrieval_tools.py`

```python
def bm25_search(query: str, n_results: int = 10) -> dict:
    """
    Performs BM25 keyword-based search across all indexed document chunks.
    
    Use this tool when the query contains specific terminology, entity names,
    product codes, or exact phrases that should be matched literally.
    
    Args:
        query: The search query string. Use exact terms, entity names, or phrases.
        n_results: Number of top results to return. Default 10, max 20.
    
    Returns:
        A dict with:
        - results: list of chunk dicts, each containing:
            - chunk_id: int
            - text: str (chunk content)
            - filename: str (source document)
            - page_num: int
            - bm25_score: float
            - source: "bm25"
        - total_found: int
    
    Example:
        bm25_search("Toyota battery supplier LG Energy 2022", n_results=10)
    """
    from src.query.bm25_indexer import BM25Indexer
    from src.storage.chunk_store import get_all_chunks
    
    indexer = BM25Indexer()
    chunks = get_all_chunks()  # reads from SQLite chunks.db
    indexer.build(chunks)
    results = indexer.query(query, n_results=n_results)
    return {"results": results, "total_found": len(results)}
```

---

### 6.2 vector_search_tool

**File:** `src/agents/tools/retrieval_tools.py`

```python
def vector_search(query: str, n_results: int = 10) -> dict:
    """
    Performs semantic vector similarity search using ChromaDB and nomic-embed-text-v1.5.
    
    Use this tool when the query is conceptual, paraphrased, or uses different
    terminology than what might appear in source documents.
    
    Args:
        query: The search query string. Conceptual or natural language phrasing works best.
        n_results: Number of top results to return. Default 10, max 20.
    
    Returns:
        A dict with:
        - results: list of chunk dicts, each containing:
            - chunk_id: int
            - text: str (chunk content)
            - filename: str (source document)
            - page_num: int
            - cosine_distance: float (lower = more similar)
            - similarity_score: float (1 - cosine_distance)
            - source: "vector"
        - total_found: int
    
    Example:
        vector_search("battery supply chain procurement strategy automotive", n_results=10)
    """
    from src.embed.embedding_pipeline import get_embedding_client
    from src.storage.vector_store import VectorStore
    
    embedder = get_embedding_client()
    query_embedding = embedder.embed_query(query)
    store = VectorStore()
    results = store.similarity_search(query_embedding, n_results=n_results)
    return {"results": results, "total_found": len(results)}
```

---

### 6.3 graph_expansion_tool

**File:** `src/agents/tools/retrieval_tools.py`

```python
def graph_expansion(chunk_ids: list, n_neighbors: int = 5) -> dict:
    """
    Expands a set of seed chunks by traversing the KuzuDB knowledge graph.
    
    For each seed chunk, this tool finds entities mentioned in that chunk,
    then returns other chunks that contain related entities (connected by
    OEM→Supplier, OEM→Technology, Supplier→Product, etc. relationships).
    
    Use this tool after initial BM25/vector retrieval to find contextually
    related content that keyword or embedding search may have missed.
    
    Args:
        chunk_ids: List of chunk_id integers from prior retrieval results.
                   Pass the top 5 chunk IDs from RRF fusion results.
        n_neighbors: Number of entity neighbors to traverse per entity. Default 5.
    
    Returns:
        A dict with:
        - expanded_chunks: list of chunk dicts (same format as bm25/vector results)
            - each has source: "graph"
            - each has entity_path: str describing how it was found
        - entities_found: list of entity names discovered
        - total_expanded: int
    
    Example:
        graph_expansion(chunk_ids=[42, 17, 88, 103, 55], n_neighbors=5)
    """
    from src.graph.kuzu_store import KuzuStore
    from src.storage.chunk_store import get_chunks_by_ids
    
    store = KuzuStore()
    seed_chunks = get_chunks_by_ids(chunk_ids)
    expanded = store.get_related_chunks(seed_chunks, n_neighbors=n_neighbors)
    return {
        "expanded_chunks": expanded["chunks"],
        "entities_found": expanded["entities"],
        "total_expanded": len(expanded["chunks"])
    }
```

---

### 6.4 rrf_fusion_tool

**File:** `src/agents/tools/retrieval_tools.py`

```python
def rrf_fusion(bm25_results: list, vector_results: list, k: int = 60) -> dict:
    """
    Merges BM25 and vector search result lists using Reciprocal Rank Fusion.
    
    RRF formula: score(chunk) = Σ 1 / (rank_i + k)
    where k=60 prevents dominance by top-ranked results.
    
    Deduplicates by chunk_id and re-ranks by combined RRF score.
    Pass ALL BM25 results and ALL vector results collected across multiple
    sub-queries before calling this tool.
    
    Args:
        bm25_results: List of all BM25 result dicts from one or more bm25_search calls.
        vector_results: List of all vector result dicts from one or more vector_search calls.
        k: RRF smoothing constant. Default 60. Higher values reduce top-rank dominance.
    
    Returns:
        A dict with:
        - fused_results: list of chunk dicts sorted by RRF score (descending)
            - each has rrf_score: float
            - each has source: "rrf"
        - total_candidates: int (before deduplication)
        - total_unique: int (after deduplication)
    
    Example:
        rrf_fusion(bm25_results=[...], vector_results=[...])
    """
    from src.query.rrf import rrf_fuse
    
    fused = rrf_fuse(bm25_results, vector_results, k=k)
    return {
        "fused_results": fused,
        "total_candidates": len(bm25_results) + len(vector_results),
        "total_unique": len(fused)
    }
```

---

### 6.5 rerank_tool

**File:** `src/agents/tools/retrieval_tools.py`

```python
def rerank(query: str, chunks: list, top_n: int = 20) -> dict:
    """
    Re-ranks candidate chunks using the BGE cross-encoder (BAAI/bge-reranker-v2-m3).
    
    The cross-encoder scores each (query, chunk) pair directly for semantic
    relevance, which is more accurate than embedding cosine similarity alone.
    
    Pass combined results from rrf_fusion + graph_expansion as chunks.
    Lazy-loads the reranker model on first call (~200ms initial load).
    
    Args:
        query: The original user query string (not sub-queries).
        chunks: List of candidate chunk dicts. Include all RRF and graph-expanded chunks.
        top_n: Number of top results to return after reranking. Default 20.
    
    Returns:
        A dict with:
        - reranked_chunks: list of top_n chunk dicts sorted by cross-encoder score
            - each has rerank_score: float (0.0–1.0)
            - each has rerank_rank: int
        - model_used: str ("BAAI/bge-reranker-v2-m3")
    
    Example:
        rerank(query="Toyota EV battery supplier evolution", chunks=[...], top_n=20)
    """
    from src.retrieval.reranker import Reranker
    
    reranker = Reranker()
    results = reranker.rerank(query=query, chunks=chunks, top_n=top_n)
    return {
        "reranked_chunks": results,
        "model_used": "BAAI/bge-reranker-v2-m3"
    }
```

---

### 6.6 context_assembly_tool

**File:** `src/agents/tools/synthesis_tools.py`

```python
def context_assembly(chunks: list, token_budget: int = 3000) -> dict:
    """
    Assembles retrieved chunks into a context string within a token budget.
    
    Uses tiktoken cl100k_base for accurate token counting.
    Prefers enriched_text if available, falls back to chunk_text.
    Sorts chunks by rerank_score (descending) before assembly.
    
    Args:
        chunks: List of reranked chunk dicts from rerank_tool output.
        token_budget: Maximum tokens for assembled context. Default 3000.
                      (Note: larger than pipeline default of 2000 — agents
                       can use more context since LLM handles it)
    
    Returns:
        A dict with:
        - assembled_context: str (formatted context with source markers)
        - chunks_included: int
        - chunks_excluded: int
        - total_tokens: int
        - sources: list of unique filenames included
    
    Example:
        context_assembly(chunks=[...], token_budget=3000)
    """
    import tiktoken
    from src.config.retrieval_config import RAG_ENABLE_ENRICHMENT
    
    encoder = tiktoken.get_encoding("cl100k_base")
    context_parts = []
    tokens_used = 0
    included = 0
    excluded = 0
    sources = set()
    
    sorted_chunks = sorted(chunks, key=lambda x: x.get("rerank_score", 0), reverse=True)
    
    for chunk in sorted_chunks:
        text = chunk.get("enriched_text") if RAG_ENABLE_ENRICHMENT else None
        text = text or chunk.get("text", "")
        source = f"[Source: {chunk.get('filename','unknown')}, p.{chunk.get('page_num','?')}]"
        chunk_str = f"{source}\n{text}\n"
        chunk_tokens = len(encoder.encode(chunk_str))
        
        if tokens_used + chunk_tokens <= token_budget:
            context_parts.append(chunk_str)
            tokens_used += chunk_tokens
            sources.add(chunk.get("filename", "unknown"))
            included += 1
        else:
            excluded += 1
    
    return {
        "assembled_context": "\n---\n".join(context_parts),
        "chunks_included": included,
        "chunks_excluded": excluded,
        "total_tokens": tokens_used,
        "sources": list(sources)
    }
```

---

### 6.7 citation_builder_tool

**File:** `src/agents/tools/synthesis_tools.py`

```python
def citation_builder(chunks: list, answer_text: str) -> dict:
    """
    Builds a structured citation table from retrieved chunks and the generated answer.
    
    Assigns HIGH or LOW confidence based on:
    - HIGH: chunk filename appears 2+ times across retrieved chunks (corroborated)
    - HIGH: chunk has rerank_score >= 0.75
    - LOW: single-source or rerank_score < 0.75
    
    Args:
        chunks: List of reranked chunk dicts used to generate the answer.
        answer_text: The generated answer text (used to find cited sources).
    
    Returns:
        A dict with:
        - citations: list of citation dicts, each containing:
            - filename: str
            - page_num: int
            - confidence: "HIGH" | "LOW"
            - rerank_score: float
            - excerpt: str (first 100 chars of chunk text)
        - high_confidence_count: int
        - low_confidence_count: int
    
    Example:
        citation_builder(chunks=[...], answer_text="The analysis shows...")
    """
    from collections import Counter
    
    filename_counts = Counter(c.get("filename") for c in chunks)
    citations = []
    
    for chunk in chunks:
        fname = chunk.get("filename", "unknown")
        score = chunk.get("rerank_score", 0.0)
        is_high = filename_counts[fname] >= 2 or score >= 0.75
        
        citations.append({
            "filename": fname,
            "page_num": chunk.get("page_num", 0),
            "confidence": "HIGH" if is_high else "LOW",
            "rerank_score": round(score, 3),
            "excerpt": chunk.get("text", "")[:100]
        })
    
    high = sum(1 for c in citations if c["confidence"] == "HIGH")
    low = len(citations) - high
    
    return {
        "citations": citations,
        "high_confidence_count": high,
        "low_confidence_count": low
    }
```

---

## 7. Session and State Management

### 7.1 ADK Session Service

System B uses SQLite for persistent storage. The ADK session service should also use SQLite to persist conversation history across Streamlit reruns and browser refreshes.

```python
# src/agents/session_manager.py
from google.adk.sessions import DatabaseSessionService

SESSION_DB_URI = "sqlite:///data/adk_sessions.db"

session_service = DatabaseSessionService(db_url=SESSION_DB_URI)
```

**This replaces `st.session_state["messages"]`** for conversation history persistence. Streamlit's `st.session_state` is still used for UI rendering (displaying messages), but the authoritative conversation history lives in the ADK session database.

### 7.2 Session Lifecycle

```python
# src/agents/adk_runner.py
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types

APP_NAME = "automotive_consulting_rag"

async def run_query(user_id: str, session_id: str, query: str) -> dict:
    """
    Main entry point called by Streamlit UI.
    Replaces direct call to src/query/pipeline.answer_question()
    """
    runner = Runner(
        agent=orchestrator_agent,
        app_name=APP_NAME,
        session_service=session_service
    )
    
    # Get or create session
    session = await session_service.get_or_create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id
    )
    
    # Set initial state for this invocation
    session.state["retrieval_attempt"] = 0
    session.state["retry_feedback"] = ""
    
    # Run the agent
    content = types.Content(role="user", parts=[types.Part(text=query)])
    
    final_response = None
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content
    ):
        if event.is_final_response():
            final_response = event.content.parts[0].text
    
    # Extract structured outputs from session state
    session = await session_service.get_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id
    )
    
    return {
        "answer": final_response or session.state.get("final_answer", ""),
        "citations": session.state.get("citations", []),
        "quality_score": session.state.get("quality_score", 0.0),
        "retrieval_attempts": session.state.get("retrieval_attempt", 1)
    }
```

### 7.3 State Key Reference Table

| Key | Type | Written by | Read by | Persists |
|---|---|---|---|---|
| `original_query` | str | OrchestratorAgent | All agents | Session |
| `query_type` | str | OrchestratorAgent | QueryRewriter, Evaluator | Session |
| `conversation_history` | list | ReasoningAgent (append) | OrchestratorAgent | Session (DatabaseSessionService) |
| `sub_queries` | list[str] | QueryRewriterAgent | RetrievalAgent | Invocation |
| `retry_feedback` | str | QualityEvaluator | QueryRewriterAgent | Invocation |
| `retrieval_attempt` | int | RetrievalAgent | QualityEvaluator | Invocation |
| `retrieved_chunks` | list[dict] | RetrievalAgent | QualityEvaluator, ReasoningAgent | Invocation |
| `quality_score` | float | QualityEvaluator | ReasoningAgent, Orchestrator | Session |
| `quality_passed` | bool | QualityEvaluator | Loop termination | Invocation |
| `coverage_gaps` | str | QualityEvaluator | ReasoningAgent | Invocation |
| `synthesised_context` | str | ReasoningAgent | Orchestrator | Invocation |
| `final_answer` | str | ReasoningAgent | Orchestrator, UI | Session |
| `citations` | list[dict] | ReasoningAgent | UI | Session |

---

## 8. Google ADK Implementation Guide

### 8.1 Installation

```bash
pip install google-adk>=1.0.0
```

**Note for Claude Code:** Check the ADK security advisory (April 2026) — LiteLLM versions 1.82.7 and 1.82.8 had a supply chain incident. Use `pip install google-adk` only from PyPI and verify the version. Do not install `google-adk[eval]` or `google-adk[extensions]` unless specifically needed.

### 8.2 Required Environment Variables

Add to `.env`:

```bash
# Google ADK / Gemini
GOOGLE_API_KEY=your_gemini_api_key_here
# OR for Vertex AI:
# GOOGLE_GENAI_USE_VERTEXAI=TRUE
# GOOGLE_CLOUD_PROJECT=your_project_id
# GOOGLE_CLOUD_LOCATION=us-central1

# Agent configuration
ADK_APP_NAME=automotive_consulting_rag
ADK_SESSION_DB=sqlite:///data/adk_sessions.db
ADK_MAX_RETRY_LOOPS=3
ADK_QUALITY_THRESHOLD=0.65
ADK_CONTEXT_TOKEN_BUDGET=3000

# LLM provider for agents (can differ from embedding provider)
# Options: gemini (default), openai, anthropic, lm-studio (local)
AGENT_LLM_PROVIDER=gemini
AGENT_LLM_MODEL=gemini-2.0-flash
```

### 8.3 Agent Registration Pattern

ADK requires agents to be importable as a Python package. The `root_agent` variable name is mandatory.

```python
# src/agents/__init__.py
from .orchestrator import orchestrator_agent as root_agent

__all__ = ["root_agent"]
```

### 8.4 ADK Agent Types — Quick Reference for Claude Code

| ADK Class | Import | Use When |
|---|---|---|
| `LlmAgent` | `from google.adk.agents import LlmAgent` | Agent needs LLM reasoning |
| `LoopAgent` | `from google.adk.agents import LoopAgent` | Repeat sub-agents until condition |
| `SequentialAgent` | `from google.adk.agents import SequentialAgent` | Run sub-agents in fixed order |
| `ParallelAgent` | `from google.adk.agents import ParallelAgent` | Run sub-agents concurrently |
| `BaseAgent` | `from google.adk.agents import BaseAgent` | Custom orchestration logic |

**Key LlmAgent parameters:**

```python
LlmAgent(
    name="AgentName",           # str, unique within system
    model="gemini-2.0-flash",   # str, model identifier
    description="...",          # str, used by parent for routing decisions
    instruction="...",          # str, system prompt; use {state_key} for state injection
    tools=[func1, func2],       # list of Python functions (docstrings required)
    sub_agents=[agent1],        # list of child agents (AgentTool pattern)
    output_key="state_key",     # str, writes final response to session state
)
```

**LoopAgent parameters:**

```python
LoopAgent(
    name="LoopAgentName",
    sub_agents=[agent1, agent2],    # executed in order, repeatedly
    max_iterations=3                # hard stop
)
```

**Loop termination — the escalate pattern:**

```python
from google.adk.tools.tool_context import ToolContext

def exit_loop(tool_context: ToolContext) -> dict:
    """Terminates the parent LoopAgent."""
    tool_context.actions.escalate = True
    return {"status": "exited"}
```

### 8.5 State Injection in Instructions

ADK injects session state values into agent instructions using `{key}` syntax:

```python
instruction="""
Process this query: {original_query}
Query type is: {query_type}
Previous retry feedback: {retry_feedback}
"""
# ADK replaces {original_query}, {query_type}, {retry_feedback}
# with their values from session.state at runtime
```

### 8.6 Testing with ADK Web UI

```bash
# From project root
adk web src/agents/

# Opens browser at http://localhost:8000
# Allows testing agents interactively before integrating with Streamlit
```

### 8.7 ADK Runner for Production

For async use within Streamlit:

```python
import asyncio
from src.agents.adk_runner import run_query

# In Streamlit (synchronous context):
result = asyncio.run(run_query(
    user_id=st.session_state["user_id"],
    session_id=st.session_state["session_id"],
    query=user_input
))
```

---

## 9. File and Folder Structure

### 9.1 New Files to Create

```
src/
├── agents/                          ← NEW directory
│   ├── __init__.py                  ← exports root_agent
│   ├── orchestrator.py              ← OrchestratorAgent definition
│   ├── query_rewriter.py            ← QueryRewriterAgent definition
│   ├── retrieval_loop.py            ← RetrievalLoopAgent (LoopAgent)
│   ├── retrieval_agent.py           ← RetrievalAgent definition
│   ├── quality_evaluator.py         ← QualityEvaluatorAgent definition
│   ├── reasoning_agent.py           ← ReasoningAgent definition
│   ├── adk_runner.py                ← async runner, session management
│   ├── session_manager.py           ← DatabaseSessionService setup
│   └── tools/                       ← NEW directory
│       ├── __init__.py
│       ├── retrieval_tools.py       ← bm25_search, vector_search, graph_expansion,
│       │                               rrf_fusion, rerank
│       └── synthesis_tools.py       ← context_assembly, citation_builder, exit_loop
│
data/
├── adk_sessions.db                  ← NEW: ADK session persistence (SQLite)
│
```

### 9.2 Files to Modify

```
app.py                               ← Replace direct pipeline.answer_question() 
│                                       call with asyncio.run(adk_runner.run_query())
│
.env                                 ← Add ADK environment variables (section 10)
│
requirements.txt                     ← Add google-adk>=1.0.0
│
src/config/retrieval_config.py       ← Add ADK config constants:
                                        ADK_MAX_RETRY_LOOPS, ADK_QUALITY_THRESHOLD,
                                        ADK_CONTEXT_TOKEN_BUDGET
```

### 9.3 Files NOT to Modify

```
src/ingest/           ← untouched
src/embed/            ← untouched
src/graph/            ← untouched
src/query/pipeline.py ← kept as fallback; tools wrap its functions
src/retrieval/        ← untouched; tools import from here
data/chunks.db        ← untouched
data/chroma_db/       ← untouched
data/kuzu_db/         ← untouched
```

---

## 10. Configuration and Environment

### 10.1 Complete .env Reference

```bash
# ── Existing System B variables (unchanged) ──────────────────────────
EMBED_PROVIDER=lm-studio
EMBED_MODEL=nomic-embed-text-v1.5
EMBED_API_BASE=http://localhost:1234
LLM_PROVIDER=lm-studio
LLM_MODEL=Qwen2.5-7B-Instruct

# RAG feature flags (unchanged)
RAG_ENABLE_BM25=true
RAG_ENABLE_RERANKER=true
RAG_ENABLE_PARENT_DOC=false
RAG_ENABLE_ENRICHMENT=false

# ── New ADK variables ─────────────────────────────────────────────────
GOOGLE_API_KEY=your_api_key_here

# Agent LLM (separate from embedding and generation LLM)
# Agents need cloud LLM — local 7B model is insufficient for planning/evaluation
AGENT_LLM_PROVIDER=gemini
AGENT_LLM_MODEL=gemini-2.0-flash

# Session persistence
ADK_SESSION_DB=sqlite:///data/adk_sessions.db

# Loop control
ADK_MAX_RETRY_LOOPS=3
ADK_QUALITY_THRESHOLD=0.65

# Context assembly
ADK_CONTEXT_TOKEN_BUDGET=3000
```

### 10.2 Important Note on LLM Split

System B uses a **two-LLM strategy** in the agentic version:

| Role | Model | Why |
|---|---|---|
| Embedding | nomic-embed-text-v1.5 (local) | Free, high quality, local |
| Agent reasoning (orchestration, evaluation, rewriting) | gemini-2.0-flash (cloud) | Needs strong reasoning for planning/evaluation |
| Final answer generation | gemini-2.0-flash (cloud) | Needs strong synthesis quality |

The local Qwen 7B model is **not recommended for agent reasoning** — classification, quality evaluation, and query rewriting require stronger instruction following than a 4-bit quantised 7B model reliably provides.

---

## 11. Integration Points with Existing System B

### 11.1 app.py Modification

Replace this existing code in `app.py`:

```python
# EXISTING (remove this):
from src.query.pipeline import answer_question

def handle_query(question: str):
    result = answer_question(
        question=question,
        db_conn=get_sqlite_conn(),
        kuzu_db=get_kuzu_db(),
        llm_client=get_openai_client()
    )
    return result
```

With this new code:

```python
# NEW (replace with this):
import asyncio
from src.agents.adk_runner import run_query

def handle_query(question: str) -> dict:
    """
    Entry point for all user queries.
    Now routes through ADK agent system instead of direct pipeline call.
    """
    user_id = st.session_state.get("user_id", "default_user")
    session_id = st.session_state.get("session_id", "default_session")
    
    result = asyncio.run(run_query(
        user_id=user_id,
        session_id=session_id,
        query=question
    ))
    return result
```

### 11.2 Session ID Management in Streamlit

```python
# Add to app.py initialisation (before any st.write calls):
import uuid

if "user_id" not in st.session_state:
    st.session_state["user_id"] = "consultant_default"

if "session_id" not in st.session_state:
    # Generate new session ID per browser session
    st.session_state["session_id"] = str(uuid.uuid4())
```

### 11.3 Backward Compatibility Fallback

Keep `src/query/pipeline.py` unchanged and add a fallback mechanism:

```python
# src/agents/adk_runner.py

async def run_query(user_id: str, session_id: str, query: str) -> dict:
    try:
        # Attempt agentic path
        return await _run_agentic_query(user_id, session_id, query)
    except Exception as e:
        # Fallback to direct pipeline on any agent failure
        import logging
        logging.warning(f"Agent pipeline failed: {e}. Falling back to direct pipeline.")
        from src.query.pipeline import answer_question
        from src.storage.connections import get_sqlite_conn, get_kuzu_db
        from src.config.providers import get_llm_client
        
        return answer_question(
            question=query,
            db_conn=get_sqlite_conn(),
            kuzu_db=get_kuzu_db(),
            llm_client=get_llm_client()
        )
```

---

## 12. Implementation Sequence for Claude Code

Follow this exact sequence. Each phase is independently testable before moving to the next.

### Phase 1: Foundation (Do First)
1. Install `google-adk>=1.0.0` and add to `requirements.txt`
2. Add ADK environment variables to `.env`
3. Create `src/agents/` directory structure with empty `__init__.py` files
4. Create `src/agents/tools/retrieval_tools.py` with all 5 retrieval tools
5. Create `src/agents/tools/synthesis_tools.py` with `context_assembly`, `citation_builder`, `exit_loop`
6. **Test:** Import all tools and call each individually with hardcoded test data

### Phase 2: Individual Agents
7. Create `src/agents/session_manager.py` with `DatabaseSessionService`
8. Create `src/agents/query_rewriter.py`
9. Create `src/agents/retrieval_agent.py`
10. Create `src/agents/quality_evaluator.py`
11. Create `src/agents/reasoning_agent.py`
12. **Test each agent independently using `adk web`**

### Phase 3: Loop Assembly
13. Create `src/agents/retrieval_loop.py` combining `LoopAgent(RetrievalAgent, QualityEvaluatorAgent)`
14. **Test loop with a query that needs 2 iterations** — verify retry_feedback flows correctly

### Phase 4: Orchestrator
15. Create `src/agents/orchestrator.py` as root `LlmAgent` with all sub-agents
16. Create `src/agents/__init__.py` exporting `root_agent`
17. Create `src/agents/adk_runner.py` with async `run_query` function
18. **Test full end-to-end with `adk web`**

### Phase 5: Streamlit Integration
19. Modify `app.py` to call `adk_runner.run_query()` instead of `pipeline.answer_question()`
20. Add session ID management to Streamlit
21. Update citation display in Streamlit to use new `citations` format
22. **Test full system: `streamlit run app.py`**

### Phase 6: Validation
23. Run the existing test suite: `pytest tests/` — all 39 tests must still pass
24. Test the warranty query: `python src/main.py query "warranty claim processing"` — must succeed
25. Test a multi-hop query: `python src/main.py query "how did our EV battery supplier recommendations evolve from 2019 to 2023"` — verify 2–3 loop iterations

---

## Appendix A: ADK Agent Communication Patterns Summary

```
Pattern 1: Sub-agents via sub_agents list (LLM-driven routing)
─────────────────────────────────────────────────────────────
parent = LlmAgent(sub_agents=[child1, child2])
→ Parent LLM decides which child to call based on its instruction

Pattern 2: AgentTool (explicit tool call)
─────────────────────────────────────────
from google.adk.tools import agent_tool
child_tool = agent_tool.AgentTool(agent=child_agent)
parent = LlmAgent(tools=[child_tool])
→ Parent explicitly calls child as if it were a function tool

Pattern 3: LoopAgent (deterministic loop)
─────────────────────────────────────────
loop = LoopAgent(sub_agents=[agent_a, agent_b], max_iterations=3)
→ Runs agent_a then agent_b repeatedly until escalate=True or max_iterations

Pattern 4: SequentialAgent (fixed pipeline)
───────────────────────────────────────────
seq = SequentialAgent(sub_agents=[step1, step2, step3])
→ Runs step1 → step2 → step3 exactly once in order

Pattern 5: Shared state communication
──────────────────────────────────────
agent_a writes: output_key="my_result" (or tool writes to ToolContext)
agent_b reads: instruction="Process: {my_result}"
→ ADK injects state values into instructions automatically
```

## Appendix B: Troubleshooting Common ADK Issues

**Issue: `await` outside function error**  
Solution: Wrap `runner.run_async()` calls in `asyncio.run()` for synchronous contexts (Streamlit).

**Issue: Agent not found / routing fails**  
Solution: Ensure each agent has a unique `name` and a clear `description`. The orchestrator uses `description` to decide routing.

**Issue: State key not injected into instruction**  
Solution: Use single braces `{key}` not double `{{key}}`. Double braces are Python f-string escaping.

**Issue: LoopAgent runs forever**  
Solution: Ensure `exit_loop` tool sets `tool_context.actions.escalate = True`. Verify `max_iterations` is set.

**Issue: Session state lost between Streamlit reruns**  
Solution: Use `DatabaseSessionService` with SQLite, not `InMemorySessionService`. Streamlit reruns on every interaction.

**Issue: Tool not called by agent**  
Solution: Check the tool's docstring — ADK uses it to decide when to call the tool. Make the docstring explicit about when to use the tool.

---

*Document prepared for Claude Code implementation. All code examples are pseudocode — exact import paths must match the actual System B file structure. Validate each phase before proceeding to the next.*
