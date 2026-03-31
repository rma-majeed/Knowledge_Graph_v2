---
phase: 06-multi-provider-llm-embedding-configuration
plan: "01"
subsystem: config-test-infrastructure
tags: [test-infrastructure, provider-config, xfail-stubs, wave-0]
dependency_graph:
  requires: []
  provides: [test_config_providers, provider_env_fixtures, src_config_package]
  affects: [06-02-providers-implementation, 06-03-mismatch-detection]
tech_stack:
  added: []
  patterns: [xfail-stubs, monkeypatch-fixtures, pytest-collect]
key_files:
  created:
    - src/config/__init__.py
    - tests/test_config_providers.py
  modified:
    - tests/conftest.py
decisions:
  - "xfail(strict=False) stubs for Wave 0: keeps test intent visible; stubs automatically pass once implementation lands (same pattern as 01-01)"
  - "imports inside test functions (not at module level): allows collection even before src.config.providers exists"
metrics:
  duration: "~10 minutes"
  completed: "2026-03-31"
  tasks_completed: 3
  tasks_total: 3
  files_changed: 3
requirements:
  - PROVIDER-01
  - PROVIDER-02
  - PROVIDER-03
  - PROVIDER-04
  - PROVIDER-05
  - PROVIDER-06
---

# Phase 06 Plan 01: Provider Config Test Infrastructure Summary

**One-liner:** 9 xfail test stubs covering all 6 PROVIDER requirements with 5 env-mocking fixtures and src.config package marker.

## What Was Built

Wave 0 test infrastructure for Phase 6 multi-provider configuration:

1. **`src/config/__init__.py`** — Empty package marker enabling `import src.config` as a valid Python package. Prerequisite for `src.config.providers` module in 06-02.

2. **`tests/conftest.py`** (appended) — 5 new pytest fixtures for provider environment simulation:
   - `mock_env_lmstudio` — clears all provider env vars (default/fallback scenario)
   - `mock_env_openai` — sets OpenAI as both LLM + embed provider
   - `mock_env_ollama` — sets Ollama (local, no API key required)
   - `mock_env_gemini` — sets Google Gemini for LLM + embed
   - `mock_env_anthropic` — sets Anthropic for LLM only

3. **`tests/test_config_providers.py`** — 9 xfail test stubs:
   - `test_llm_client_defaults_to_lmstudio` (PROVIDER-01)
   - `test_llm_client_from_env_openai` (PROVIDER-02)
   - `test_llm_client_from_env_ollama` (PROVIDER-02)
   - `test_llm_client_from_env_gemini` (PROVIDER-02)
   - `test_llm_client_from_env_anthropic` (PROVIDER-02)
   - `test_embed_client_defaults_to_lmstudio` (PROVIDER-03)
   - `test_embed_client_from_env_openai` (PROVIDER-04)
   - `test_llm_provider_change_requires_only_env` (PROVIDER-05)
   - `test_embed_mismatch_warning_triggers` (PROVIDER-06)

## Verification

- `pytest tests/test_config_providers.py --collect-only -q` — 9 tests collected, 0 errors
- `pytest tests/test_config_providers.py -x --tb=short -q` — 9 xfailed (no SyntaxError, no ImportError)
- `python -c "import src.config; print('OK')"` — exits 0
- All 5 new conftest fixtures verified present via collection

## Commits

| Task | Description | Hash |
|------|-------------|------|
| 1 | Create src/config/__init__.py package marker | f32e488 |
| 2 | Add provider env fixtures to conftest.py | 8fcb533 |
| 3 | Create tests/test_config_providers.py with 9 xfail stubs | 550b4d1 |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

The 9 tests in `tests/test_config_providers.py` are intentional stubs (all marked `xfail`). They import from `src.config.providers` inside the test body (not at module level) to allow collection before the module exists. Plan 06-02 will implement `providers.py` to make these pass.

## Self-Check: PASSED

- `src/config/__init__.py` — FOUND
- `tests/test_config_providers.py` — FOUND
- `tests/conftest.py` — FOUND (fixtures appended)
- Commit f32e488 — FOUND
- Commit 8fcb533 — FOUND
- Commit 550b4d1 — FOUND
