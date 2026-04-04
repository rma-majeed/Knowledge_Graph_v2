# Agentic Loop Plan: Quality Evaluator + Retry + Reasoning Agent

## Current Architecture

```
graphrag_master_agent  (LlmAgent + AgentTool routing)
├── pipeline_rag_agent   →  full_rag_query, append_citations
└── search_rag_agent     →  vector_search, bm25_search, graph_search, rerank, format_citations
```

The master agent routes, calls one sub-agent, synthesizes, and calls `passthrough_citations`.
There is no quality check, no retry, no deeper reasoning step.

---

## Target Architecture

```
graphrag_master_agent  (LlmAgent + AgentTool routing)
├── pipeline_rag_agent              ← MODIFIED
│   ├── full_rag_query              (existing)
│   ├── append_citations            (existing)
│   └── [NEW] check_answer_quality  ← heuristic quality gate
│       • if LOW quality → retry full_rag_query with broadened prefix
│       • max 2 retries, then pass through regardless
│
├── search_rag_agent                (unchanged)
│   └── 5 search tools              (unchanged)
│
└── [NEW] reasoning_agent           ← new sub-agent (AgentTool in master)
    └── [NEW] apply_reasoning tool
        • takes question + answer + citations
        • adds: Key Insights, Implications, Gaps/Limitations
        • preserves all inline [N] citation markers
```

---

## Component 1 — `check_answer_quality` Tool

**New file:** `GraphRAG_Factory/sub_agents/pipeline_rag_agent/tools/quality_tools.py`

This is a **pure Python heuristic** — no extra LLM call, no added latency.

### Quality Signals

| Signal | Verdict |
|---|---|
| Answer contains "I don't know" / "no information" / "cannot find" | RETRY |
| `citations` list is empty (no evidence retrieved) | RETRY |
| Answer is fewer than 50 words | RETRY |
| None of the above | PASS |

Returns: `{ "verdict": "PASS" | "RETRY", "reason": "..." }`

### Retry Behaviour

If verdict is `RETRY`, the `pipeline_rag_agent` instruction directs it to call `full_rag_query`
again with the question prefixed: `"Provide comprehensive detail on: <original question>"`.
Maximum 2 retry attempts — after that, pass through regardless.

**Why heuristic, not LLM?**
Small models (gemma, Qwen) are inconsistent at self-evaluating answer quality.
A deterministic check is faster, cheaper, and more reliable at catching the easy failure modes.

---

## Component 2 — `reasoning_agent` Sub-Agent

**New directory:** `GraphRAG_Factory/sub_agents/reasoning_agent/`

```
reasoning_agent/
├── __init__.py
├── agent.py
└── tools/
    ├── __init__.py
    └── reasoning_tools.py
```

### New Tool: `apply_reasoning`

Signature: `apply_reasoning(question, answer, citations_block) → dict`

Wraps the answer in a structured reasoning prompt and calls the LLM a second time to produce:

```
Summary: <1-2 sentence direct answer>

Key Insights:
• ...

Implications for the business:
• ...

Gaps / Limitations:
• (what the knowledge base does NOT cover)

Citations:
  [1] document.pdf, p.N
```

Returns: `{ "reasoned_answer": "...", "citations_block": "..." }`

> Input answer is truncated to ~800 tokens before passing to the LLM to avoid context overflow.

---

## Master Agent Routing (Updated)

| Query type | Route |
|---|---|
| Standard Q&A ("what", "how", "why") | pipeline_rag_agent only |
| Entity / comparison queries ("what suppliers", "compare X and Y") | search_rag_agent only |
| Analytical queries ("analyze", "implications", "strategic significance", "recommend") | pipeline_rag_agent → then reasoning_agent |

The master's `passthrough_citations` tool stays **unchanged**.

---

## Files Changed vs New

| File | Status | Change |
|---|---|---|
| `GraphRAG_Factory/sub_agents/pipeline_rag_agent/tools/quality_tools.py` | **NEW** | `check_answer_quality` heuristic tool |
| `GraphRAG_Factory/sub_agents/pipeline_rag_agent/agent.py` | **MODIFIED** | Register `check_answer_quality`; update instruction with retry logic |
| `GraphRAG_Factory/sub_agents/reasoning_agent/__init__.py` | **NEW** | Factory re-export |
| `GraphRAG_Factory/sub_agents/reasoning_agent/agent.py` | **NEW** | `create_reasoning_agent()` LlmAgent |
| `GraphRAG_Factory/sub_agents/reasoning_agent/tools/__init__.py` | **NEW** | Tool re-export |
| `GraphRAG_Factory/sub_agents/reasoning_agent/tools/reasoning_tools.py` | **NEW** | `apply_reasoning` tool |
| `GraphRAG_Factory/agent.py` | **MODIFIED** | Add `reasoning_agent` as 3rd AgentTool; update routing rules in instruction |
| `src/query/pipeline.py` | **UNCHANGED** | Core 10-step RAG pipeline — not touched |
| `GraphRAG_Factory/db_singletons.py` | **UNCHANGED** | reasoning_agent imports from here |
| All `search_rag_agent` files | **UNCHANGED** | |

---

## Call Flows

### Standard Query

```
User: "What EV strategies did Toyota adopt?"

Master Agent
  → detects standard Q&A → calls pipeline_rag_agent

    pipeline_rag_agent
      → full_rag_query(question)        → answer + citations
      → check_answer_quality(...)       → verdict: PASS
      → append_citations(...)
      → returns pipeline_rag_result

  → calls passthrough_citations(citations_block)
  → outputs: answer + Citations block
```

### Retry Flow

```
User: "What does Ford do?"

pipeline_rag_agent
  → full_rag_query("What does Ford do?")
     answer: "I don't have enough information..."
     citations: []
  → check_answer_quality(...)
     verdict: RETRY (empty citations + low-confidence phrase)
  → full_rag_query("Provide comprehensive detail on: What does Ford do?")
     answer: "Ford Motor Company is a major OEM that..." [1][2]
     citations: [{...}, {...}]
  → check_answer_quality(...)
     verdict: PASS
  → append_citations(...)
```

### Analytical Query (Full Agentic Loop)

```
User: "Analyze the strategic implications of Ford's EV investments"

Master Agent
  → detects "analyze" + "implications" → analytical route
  → calls pipeline_rag_agent(question)

    pipeline_rag_agent
      → full_rag_query(question)        → answer + citations
      → check_answer_quality(...)       → verdict: PASS
      → append_citations(...)
      → returns pipeline_rag_result

  → calls reasoning_agent(question, pipeline_rag_result)

    reasoning_agent
      → apply_reasoning(question, answer, citations_block)
         → LLM structures: Summary / Key Insights / Implications / Gaps
         → preserves all [N] markers + citations_block
      → returns reasoning_result

  → calls passthrough_citations(citations_block from reasoning_result)
  → outputs: structured analytical answer + Citations block
```

---

## Risks and Constraints

1. **Small LLM + long context**: `apply_reasoning` gives the LLM a second pass over the
   answer. Long answers can exceed the model's context or produce repetition.
   Mitigation: truncate input answer to ~800 tokens inside the tool before LLM call.

2. **Reasoning output quality**: Gemma/Qwen are poor at following multi-section templates.
   Mitigation: the `apply_reasoning` tool pre-structures a fill-in-the-blanks prompt
   rather than asking the LLM to freely format the output.

3. **Retry may not help if KB lacks data**: Broadening the prefix only helps when the
   original query was poorly formed. If the corpus has no information, 2 retries are still
   useless. After max retries the result is passed through with a low-confidence note.

4. **Master routing by keyword**: Small LLMs may not reliably detect "analytical" queries
   from free-text instructions. Routing keywords must be explicit and minimal
   (e.g., exact word list: "analyze", "implications", "recommend", "strategic") rather
   than relying on semantic judgment.
