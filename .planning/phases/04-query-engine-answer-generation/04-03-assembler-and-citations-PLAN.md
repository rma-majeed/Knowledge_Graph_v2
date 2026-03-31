---
phase: 04-query-engine-answer-generation
plan: 03
type: execute
wave: 2
depends_on:
  - "04-01"
parallel_with:
  - "04-02"
files_modified:
  - src/query/assembler.py
autonomous: true
requirements:
  - QUERY-04

must_haves:
  truths:
    - "truncate_to_budget() sorts chunks with vector chunks (ascending distance) before graph chunks, then stops adding chunks once CONTEXT_TOKEN_BUDGET is exhausted; returns (context_str, included_chunks)"
    - "build_citations() assigns confidence='HIGH' when a (filename, page_num) pair appears in >= 3 included chunks; confidence='LOW' for 1-2 appearances; citations are ordered by _ctx_index"
    - "format_answer() returns LLM response text followed by a formatted Citations section listing each citation's index, filename, page number, and confidence"
    - "build_prompt() returns a two-message list [system_msg, user_msg] with the consulting-domain system prompt and the query + numbered context passages"
    - "test_query_assembler.py tests pass (no longer xfail)"
  artifacts:
    - path: "src/query/assembler.py"
      provides: "truncate_to_budget, build_citations, format_answer, build_prompt"
      exports:
        - truncate_to_budget
        - build_citations
        - format_answer
        - build_prompt
        - CONTEXT_TOKEN_BUDGET
        - CITATION_HIGH_CONFIDENCE_THRESHOLD
      min_lines: 80
  key_links:
    - from: "src/query/assembler.py"
      to: "tiktoken"
      via: "tiktoken.get_encoding('cl100k_base').encode(text)"
      pattern: "tiktoken.get_encoding"
    - from: "src/query/pipeline.py"
      to: "src/query/assembler.py"
      via: "truncate_to_budget(chunks) -> build_prompt(query, context_str) -> build_citations(included)"
      pattern: "from src.query.assembler import"
---

<objective>
Implement `src/query/assembler.py` with token-budgeted context assembly, citation confidence scoring, answer formatting, and prompt construction.

Purpose: This plan is parallel to 04-02 (no shared files). It delivers QUERY-04 (source citations with HIGH/LOW confidence). Plan 04-04 wires assembler output into the full pipeline.

Output: `src/query/assembler.py` fully implemented; `tests/test_query_assembler.py` stubs become passing.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/04-query-engine-answer-generation/04-RESEARCH.md
@.planning/phases/04-query-engine-answer-generation/04-01-SUMMARY.md

<interfaces>
<!-- tiktoken usage — approximate token counting for Qwen2.5 (BPE family) -->
```python
import tiktoken
_ENC = tiktoken.get_encoding("cl100k_base")
token_count = len(_ENC.encode(text))
```

<!-- Input chunk dict shape (from hybrid_retrieve() output) -->
# Each chunk dict has these keys (all optional except text):
{
    "chunk_id": "42",           # str (from vector) or int (from graph) — normalise to int
    "text": "...",              # chunk text — required for token counting
    "metadata": {               # present for vector chunks
        "filename": "report.pdf",
        "page_num": 3,
    },
    "filename": "report.pdf",   # present for graph chunks (flat, no metadata wrapper)
    "page_num": 3,              # present for graph chunks
    "source": "vector",         # "vector" or "graph"
    "distance": 0.12,           # lower = more relevant for vector; 1.0 for graph chunks
}

<!-- Context string format (numbered passages for LLM) -->
# Each passage:
f"[{i}] Source: {filename}, page {page}\n{text}"
# Joined with "\n\n"

<!-- System prompt (from 04-RESEARCH.md Pattern 4 — use verbatim) -->
_SYSTEM_PROMPT = """You are an expert automotive consulting analyst with access to a knowledge base of consulting documents.

Answer the consultant's question using ONLY the numbered source passages provided. Do not use any knowledge outside the provided sources.

Citation rules:
- Cite each source inline using [N] immediately after the relevant claim
- Every factual statement must have at least one citation
- If multiple sources support a claim, list all relevant citations: [1][3]
- If the sources do not contain enough information to answer, say: "The available documents do not contain sufficient information to answer this question." — do NOT fabricate an answer

Answer in professional consulting language. Be concise (3-6 sentences for most questions). Do not repeat the question."""

<!-- Citation table format for format_answer() output -->
# After the LLM response, append:
"\n\nCitations:\n"
# Then per citation:
f"  [{c['index']}] {c['filename']}, p.{c['page_num']}  ({c['confidence']})\n"
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement src/query/assembler.py</name>
  <files>src/query/assembler.py, tests/test_query_assembler.py</files>

  <read_first>
    - src/query/assembler.py (current stub — replace NotImplementedError with real implementation)
    - tests/test_query_assembler.py (current xfail stubs — remove xfail once tests pass)
    - .planning/phases/04-query-engine-answer-generation/04-RESEARCH.md (Pattern 3, Pattern 4, Pattern 5 code blocks — use these as the implementation reference)
  </read_first>

  <behavior>
    - test_assemble_context_respects_token_budget: given chunks whose combined tokens exceed CONTEXT_TOKEN_BUDGET=3000, truncate_to_budget() returns a context_str whose tiktoken token count is <= 3000, and included_chunks length < total input length; vector chunks appear before graph chunks
    - test_citation_confidence_high: build_citations([...]) where the same (filename, page_num) appears in 3 chunks returns citation with confidence='HIGH' for that source
    - test_citation_confidence_low: build_citations([...]) where a (filename, page_num) appears in 1 or 2 chunks returns citation with confidence='LOW'
    - test_format_answer_with_citations: format_answer("Answer text [1].", [{index:1, filename:"doc.pdf", page_num:5, confidence:"HIGH", source:"vector"}]) returns string containing "Answer text [1]." and "Citations:" and "[1] doc.pdf, p.5  (HIGH)"
  </behavior>

  <action>
Implement `src/query/assembler.py` replacing all NotImplementedError stubs. Follow Patterns 3, 4, and 5 from 04-RESEARCH.md exactly.

Key implementation rules:

**Constants (already defined in stub — keep as-is):**
- `CONTEXT_TOKEN_BUDGET = 3000`
- `CITATION_HIGH_CONFIDENCE_THRESHOLD = 3`
- `_ENC = tiktoken.get_encoding("cl100k_base")` — module-level, initialised once
- `_SYSTEM_PROMPT` — use the verbatim string from Pattern 4 in the research doc

**truncate_to_budget(chunks, token_budget=CONTEXT_TOKEN_BUDGET):**
- Sort: `sorted(chunks, key=lambda c: (0 if c.get("source")=="vector" else 1, c.get("distance", 1.0)))`
- Iterate sorted chunks. For each chunk: count tokens with `len(_ENC.encode(chunk.get("text", "")))`. If tokens > budget_remaining, break. Otherwise: subtract from budget, format the passage line, append chunk to included with `_ctx_index` set to 1-based position counter.
- Context string is `"\n\n".join(parts)` where each part is `f"[{i}] Source: {filename}, page {page}\n{text}"`.
- Helper for filename/page: `chunk.get("metadata", {}).get("filename") or chunk.get("filename", "unknown")` — same pattern for page_num.
- Returns `(context_str, included_chunks)`.

**build_citations(included_chunks):**
- Count `(filename, page_num)` pairs using `collections.Counter`.
- For each chunk in included_chunks, construct citation dict: `{index: chunk["_ctx_index"], filename, page_num, confidence: "HIGH" if count >= CITATION_HIGH_CONFIDENCE_THRESHOLD else "LOW", source: chunk.get("source", "vector")}`.
- Sort by `index` and return.

**format_answer(llm_response, citations):**
- Returns `llm_response + "\n\nCitations:\n" + "".join(f"  [{c['index']}] {c['filename']}, p.{c['page_num']}  ({c['confidence']})\n" for c in citations)`.
- If citations is empty, append `"\n\n(No source citations available.)"` instead.

**build_prompt(query, context_str):**
- Returns `[{"role": "system", "content": _SYSTEM_PROMPT}, {"role": "user", "content": f"Question: {query}\n\nSources:\n{context_str}"}]`.

After implementing, update `tests/test_query_assembler.py`:
- Remove `@pytest.mark.xfail(strict=False, reason="not implemented yet")` from all 4 tests
- Replace `raise NotImplementedError` with real test bodies using synthetic chunk dicts (no external dependencies needed — assembler is pure Python with tiktoken)
  </action>

  <verify>
    <automated>cd "C:/Users/2171176/Documents/Python/Knowledge_Graph_v2" && python -m pytest tests/test_query_assembler.py -x -q --tb=short 2>&1 | tail -8</automated>
  </verify>

  <done>All 4 test_query_assembler tests pass (not xfail); assembler.py importable; CONTEXT_TOKEN_BUDGET=3000 and CITATION_HIGH_CONFIDENCE_THRESHOLD=3 accessible as module constants</done>
</task>

</tasks>

<verification>
```bash
# Assembler tests pass
pytest tests/test_query_assembler.py -x -q --tb=short

# Import and constant check
python -c "
from src.query.assembler import (
    truncate_to_budget, build_citations, format_answer, build_prompt,
    CONTEXT_TOKEN_BUDGET, CITATION_HIGH_CONFIDENCE_THRESHOLD
)
assert CONTEXT_TOKEN_BUDGET == 3000
assert CITATION_HIGH_CONFIDENCE_THRESHOLD == 3
print('assembler imports and constants OK')
"

# Full suite still green
pytest tests/ -x -q -k "not lm_studio" --tb=short 2>&1 | tail -5
```
</verification>

<success_criteria>
- tests/test_query_assembler.py: 4 tests PASS (not xfail, not ERROR)
- truncate_to_budget() enforces 3000-token budget; vector chunks prioritised over graph chunks
- build_citations() HIGH for >= 3 appearances of same doc+page; LOW for 1-2
- format_answer() output contains "Citations:" section with index, filename, page, confidence
- build_prompt() returns correctly structured two-message list for LM Studio chat API
- Full test suite green: pytest tests/ -x -q -k "not lm_studio" exits 0
</success_criteria>

<output>
After completion, create `.planning/phases/04-query-engine-answer-generation/04-03-SUMMARY.md`
</output>
