---
phase: 06-multi-provider-llm-embedding-configuration
plan: 02
subsystem: config
tags: [litellm, python-dotenv, openai, providers, env-config, lm-studio]

# Dependency graph
requires:
  - phase: 06-01
    provides: "test infrastructure: 9 xfail stubs in test_config_providers.py, conftest provider fixtures"
provides:
  - "src/config/providers.py with get_llm_client(), get_embed_client(), load_provider_config(), get_current_embed_provider(), get_current_embed_model()"
  - ".env.example with all 5 LLM provider examples and 4 embed provider examples"
  - "requirements.txt updated with litellm>=1.45.0, python-dotenv>=1.0.0, streamlit>=1.30.0"
  - ".env git-ignored to prevent API key commits"
affects:
  - 06-03-mismatch-detection
  - 06-04-wire-providers

# Tech tracking
tech-stack:
  added: [litellm>=1.45.0, python-dotenv>=1.0.0]
  patterns:
    - "Provider factory pattern: get_llm_client()/get_embed_client() return OpenAI client for lm-studio, _LiteLLMConfig for cloud providers"
    - "_load_dotenv() called at import time; get_*_client() reads os.getenv() on each call (no module cache) so monkeypatch works in tests"
    - "_LiteLLMConfig lightweight container: callers check hasattr(client, 'provider') to distinguish OpenAI vs LiteLLM routing"

key-files:
  created:
    - src/config/providers.py
    - .env.example
  modified:
    - requirements.txt
    - tests/test_config_providers.py
    - .gitignore

key-decisions:
  - "_LiteLLMConfig is a config holder (not a LiteLLM client) — avoids importing litellm at startup when using lm-studio default"
  - "get_llm_client() reads os.getenv() on every call — no module-level caching — so pytest monkeypatch works correctly"
  - "httpx.URL.host strips port; fixed test assertions to use str(client.base_url) which includes :1234"

patterns-established:
  - "Provider selection pattern: check hasattr(client, 'provider') to route between OpenAI and LiteLLM call patterns"
  - ".env absent = lm-studio default; no exception, no warning — zero-friction startup"

requirements-completed: [PROVIDER-01, PROVIDER-02, PROVIDER-03, PROVIDER-04, PROVIDER-05]

# Metrics
duration: 15min
completed: 2026-03-31
---

# Phase 6 Plan 2: Provider Factory Module Summary

**Provider factory module (providers.py) with LM Studio fallback and LiteLLM routing for 5 LLM providers and 4 embed providers, configured entirely via .env**

## Performance

- **Duration:** 15 min
- **Started:** 2026-03-31T00:00:00Z
- **Completed:** 2026-03-31T00:15:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Implemented `src/config/providers.py` with factory functions: `get_llm_client()`, `get_embed_client()`, `load_provider_config()`, `get_current_embed_provider()`, `get_current_embed_model()`
- LM Studio remains the zero-config default when `.env` is absent — backward compatible with all existing pipeline code
- 8 of 9 provider config tests now PASSED (xfail markers removed); only PROVIDER-06 mismatch detection remains xfail (planned for 06-03)
- Created `.env.example` with documented examples for all 5 LLM providers + 4 embed providers including WARNING about re-embedding on model change
- Added `litellm>=1.45.0` and `python-dotenv>=1.0.0` to requirements.txt; `.env` added to `.gitignore`

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement src/config/providers.py** - `41b46a2` (feat)
2. **Task 2: Create .env.example and update requirements.txt** - `92610e6` (chore)

**Plan metadata:** _(docs commit follows)_

## Files Created/Modified

- `src/config/providers.py` - Provider factory module: get_llm_client(), get_embed_client(), load_provider_config(), helper functions
- `.env.example` - Template with 5 LLM + 4 embed provider examples, all commented out
- `requirements.txt` - Added litellm, python-dotenv, streamlit
- `tests/test_config_providers.py` - Removed xfail markers from 8 implemented tests; fixed base URL assertion to use str()
- `.gitignore` - Added .env to prevent API key commits

## Decisions Made

- **_LiteLLMConfig is a config holder, not a LiteLLM client**: Avoids importing litellm at startup when LM Studio default is in use. Callers check `hasattr(client, 'provider')` to distinguish routing path. This keeps lm-studio startup lightweight.
- **os.getenv() called fresh on each get_*_client() call**: No module-level caching so pytest monkeypatch (setenv/delenv) works correctly in tests.
- **Fixed test assertion bug**: `httpx.URL.host` returns "localhost" (no port), so `"1234" in host` always fails. Changed to `str(client.base_url)` which gives full URL including port.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed base URL assertion in test_config_providers.py**
- **Found during:** Task 1 (running pytest after implementation)
- **Issue:** `getattr(client.base_url, "host", None)` returns `"localhost"` (truthy), so the `or str(client.base_url)` fallback was never reached. `"1234" not in "localhost"` caused `test_llm_client_defaults_to_lmstudio` and `test_embed_client_defaults_to_lmstudio` to fail even with correct implementation.
- **Fix:** Changed assertion to `base = str(client.base_url)` which includes the port (`http://localhost:1234/v1/`).
- **Files modified:** tests/test_config_providers.py
- **Verification:** Both LM Studio default tests now PASS
- **Committed in:** `41b46a2` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in test assertion logic)
**Impact on plan:** Required to meet "all 9 tests PASSED" success criterion. Test intent was correct; assertion implementation had a subtle httpx.URL attribute bug.

## Issues Encountered

None beyond the test assertion bug documented above.

## User Setup Required

None — no external service configuration required for providers.py itself. Users who want cloud providers will edit `.env` with their API keys (documented in `.env.example`).

## Next Phase Readiness

- `src/config/providers.py` is ready for 06-03 (mismatch detection in embed pipeline)
- `src/config/providers.py` is ready for 06-04 (wire providers into all existing pipelines)
- Factory functions importable from any pipeline with `from src.config.providers import get_llm_client, get_embed_client`
- LM Studio default ensures no breaking change in 06-04 before provider wiring is complete

---
*Phase: 06-multi-provider-llm-embedding-configuration*
*Completed: 2026-03-31*
