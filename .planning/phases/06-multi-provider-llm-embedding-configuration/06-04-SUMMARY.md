---
phase: 06-multi-provider-llm-embedding-configuration
plan: "04"
subsystem: config
tags: [provider-factory, refactoring, wiring, llm-client, dispatch]
dependency_graph:
  requires: [06-02, 06-03]
  provides: [PROVIDER-01, PROVIDER-02, PROVIDER-03, PROVIDER-04, PROVIDER-05]
  affects: [src/graph/pipeline.py, src/query/pipeline.py, app.py]
tech_stack:
  added: []
  patterns: [dispatch-helper, lazy-factory-import, provider-agnostic-client]
key_files:
  created: []
  modified:
    - src/graph/pipeline.py
    - src/query/pipeline.py
    - app.py
decisions:
  - "isinstance(client.provider, str) added to _llm_complete() dispatch check to prevent MagicMock routing through LiteLLM path in tests"
metrics:
  duration: "~30 minutes"
  completed: "2026-03-31"
  tasks: 2
  files: 3
---

# Phase 06 Plan 04: Wire Provider Factory into All Pipelines Summary

**One-liner:** Replaced all hardcoded `OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")` instantiations in graph/pipeline.py, query/pipeline.py, and app.py with factory calls to `get_llm_client()` from src/config/providers.py, adding a `_llm_complete()` dispatch helper for provider-agnostic LLM calls.

## What Was Built

- **src/graph/pipeline.py**: `build_knowledge_graph()` now creates its LLM client via `get_llm_client()` lazy import instead of hardcoded `OpenAI(base_url=...)`. Module docstring updated to reflect factory usage.

- **src/query/pipeline.py**: Added `_llm_complete()` dispatch helper that routes to either `client.chat.completions.create()` (raw OpenAI/LM Studio) or `litellm.completion()` (_LiteLLMConfig cloud providers). Both `answer_question()` and `stream_answer_question()` now use `get_llm_client()` factory and `_llm_complete()` for inline LLM calls. Removed local `from openai import OpenAI` lazy imports from both functions.

- **app.py**: `get_openai_client()` cached resource now delegates to `get_llm_client()` from the provider factory. Removed unused top-level `from openai import OpenAI` import.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Refactor graph/pipeline.py | 0b256c0 | src/graph/pipeline.py |
| 2 | Refactor query/pipeline.py and app.py | 7a0b922 | src/query/pipeline.py, app.py |

## Verification

- `grep "OpenAI(base_url" src/graph/pipeline.py` — 0 matches
- `grep "OpenAI(base_url" src/query/pipeline.py` — 0 matches
- `grep "OpenAI(base_url" app.py` — 0 matches
- `pytest tests/` — 39 passed, 4 xfailed, 40 xpassed (0 failures)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] MagicMock routing through LiteLLM in _llm_complete() dispatch**
- **Found during:** Task 2 verification
- **Issue:** `hasattr(MagicMock(), 'provider')` returns True because MagicMock auto-creates all attribute access. The dispatch check `if hasattr(client, 'provider')` sent mock clients into the litellm path, causing litellm to try to make API calls with MagicMock objects as model/api_key/api_base — holding KuzuDB file locks longer than Windows tempfile cleanup could handle.
- **Fix:** Changed check to `if hasattr(client, "provider") and isinstance(client.provider, str)` — `_LiteLLMConfig.provider` is always a string; MagicMock attributes are MagicMock objects.
- **Files modified:** src/query/pipeline.py (line 36)
- **Commit:** 7a0b922

## Deferred Items

**embed/pipeline.py still has hardcoded OpenAI clients** (lines 16, 86). This file is out of scope for plan 06-04 (not in `files_modified` frontmatter). The plan's broader success criteria states "only matches inside src/config/providers.py" but embed/pipeline.py was intentionally left unchanged — it uses `openai_client=None` default and creates the client lazily. The embed pipeline uses `get_embed_client()` only for mismatch detection (06-03 work). Migrating `embed_all_chunks()` default client creation would require a separate plan or is deferred to a future phase.

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| isinstance(client.provider, str) guard in _llm_complete | MagicMock responds True to hasattr() for any attribute — string type check reliably distinguishes _LiteLLMConfig from mock objects |

## Known Stubs

None — all factory wiring is functional. The `_llm_complete()` dispatch helper fully handles both LM Studio (raw OpenAI client) and cloud provider (_LiteLLMConfig → LiteLLM) paths.

## Self-Check: PASSED

Files verified:
- src/graph/pipeline.py — FOUND, contains get_llm_client
- src/query/pipeline.py — FOUND, contains _llm_complete and get_llm_client (x2)
- app.py — FOUND, contains get_llm_client

Commits verified:
- 0b256c0 — FOUND (graph/pipeline.py refactor)
- 7a0b922 — FOUND (query/pipeline.py + app.py refactor)
