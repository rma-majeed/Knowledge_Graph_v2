---
phase: 04-query-engine-answer-generation
plan: "03"
subsystem: query-assembler
tags: [assembler, token-budget, citations, tiktoken, answer-formatting]
dependency_graph:
  requires: ["04-01"]
  provides: ["QUERY-04", "truncate_to_budget", "build_citations", "format_answer", "build_prompt"]
  affects: ["04-04"]
tech_stack:
  added: ["tiktoken cl100k_base encoder (module-level singleton)"]
  patterns: ["token-budgeted context window management", "citation confidence scoring", "numbered-passage prompting"]
key_files:
  created: []
  modified:
    - src/query/assembler.py
    - tests/test_query_assembler.py
decisions:
  - "Sort order: vector chunks (source='vector') before graph chunks, then ascending distance within each group"
  - "Token counting uses tiktoken cl100k_base at passage level (formatted string, not raw text) for accurate budget measurement"
  - "build_citations deduplicates per (filename, page_num) pair and sorts result by _ctx_index for stable ordering"
  - "format_answer falls back to '(No source citations available.)' when citations list is empty"
metrics:
  duration: "~8 minutes"
  completed: "2026-03-31"
  tasks_completed: 1
  files_modified: 2
---

# Phase 04 Plan 03: Assembler and Citations Summary

Implemented `src/query/assembler.py` with token-budgeted context assembly, HIGH/LOW citation confidence scoring, formatted answer output, and two-message prompt construction for the LM Studio chat API.

## Tasks Completed

| # | Task | Status | Commit |
|---|------|--------|--------|
| 1 | Implement src/query/assembler.py | DONE | 3c86cb4 |

## What Was Built

**`truncate_to_budget(chunks, token_budget=3000)`**
Sorts input chunks with vector chunks first (by ascending distance), then graph chunks. Iterates in sorted order and counts tokens per formatted passage using tiktoken cl100k_base. Stops before the budget is exhausted. Returns `(context_str, included_chunks)` where each included chunk carries a 1-based `_ctx_index`.

**`build_citations(included_chunks)`**
Counts `(filename, page_num)` pair appearances using `collections.Counter`. Assigns `confidence="HIGH"` when count >= 3 (`CITATION_HIGH_CONFIDENCE_THRESHOLD`), `"LOW"` otherwise. Returns one citation dict per included chunk, sorted by `_ctx_index`.

**`format_answer(llm_response, citations)`**
Appends a `Citations:` block to the LLM response text with lines formatted as `  [N] filename, p.PAGE  (CONFIDENCE)`. Returns the unchanged response when citations is empty, with a `(No source citations available.)` notice.

**`build_prompt(query, context_str)`**
Returns a two-element messages list `[system, user]`. System prompt is the automotive consulting domain prompt from 04-RESEARCH.md Pattern 4. User message is `"Question: {query}\n\nSources:\n{context_str}"`.

## Tests

All 4 previously xfail stubs in `tests/test_query_assembler.py` now pass:

- `test_assemble_context_respects_token_budget` — verifies truncation stops before 3000-token limit; vector chunks precede graph chunks; `_ctx_index` is 1-based sequential
- `test_citation_confidence_high` — same `(filename, page_num)` in 3 chunks yields `confidence="HIGH"`
- `test_citation_confidence_low` — sources appearing 1-2 times yield `confidence="LOW"`
- `test_format_answer_with_citations` — output contains `"Citations:"` and `"[1] doc.pdf, p.5  (HIGH)"`

Full suite result: **29 passed, 2 deselected, 2 xfailed, 37 xpassed** (0 failures).

## Deviations from Plan

**1. [Rule 1 - Bug] Test data token count too low**
- **Found during:** Task 1 (first test run)
- **Issue:** `long_text = "automotive consulting insight. " * 60` produced ~254 tokens per passage; 9 passages totalled 2286 tokens, fitting entirely within the 3000-token budget — the truncation assertion never triggered.
- **Fix:** Increased multiplier to `* 150` (764 tokens per passage); 5 vector passages alone total 3820 tokens, reliably exceeding the budget.
- **Files modified:** tests/test_query_assembler.py
- **Commit:** 3c86cb4 (included in main task commit)

## Known Stubs

None. All assembler functions are fully implemented. The context_str and citation list flow directly to the answer in plan 04-04.

## Self-Check: PASSED

- `src/query/assembler.py` — EXISTS, 130+ lines
- `tests/test_query_assembler.py` — EXISTS, 4 passing tests
- commit 3c86cb4 — FOUND in git log
- `CONTEXT_TOKEN_BUDGET == 3000` — VERIFIED
- `CITATION_HIGH_CONFIDENCE_THRESHOLD == 3` — VERIFIED
